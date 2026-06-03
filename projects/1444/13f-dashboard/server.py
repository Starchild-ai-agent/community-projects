"""13F Dashboard backend — reads from output/13f/, serves JSON + static,
and orchestrates background fund downloads + baseline price fetching."""
from __future__ import annotations
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
from datetime import date
from flask import Flask, jsonify, request, send_from_directory, abort

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("F13_DATA_DIR", "/data/workspace/output/13f"))
STATIC_DIR = ROOT / "static"
SKILL_DIR = Path("/data/workspace/skills/sec-13f")
DOWNLOAD_SCRIPT = SKILL_DIR / "scripts" / "download_13f.py"

# Baselines (rebased to fund's first period)
BASELINES = {
    "SPY":  {"label": "S&P 500 (SPY)",       "color": "#5cd4ff"},
    "QQQ":  {"label": "Nasdaq 100 (QQQ)",    "color": "#c44dff"},
    "IWM":  {"label": "Russell 2000 (IWM)",  "color": "#7af0a8"},
    "GLD":  {"label": "Gold (GLD)",          "color": "#ffb84d"},
}
BASELINE_CACHE_PATH = ROOT / "baselines_cache.json"
BASELINE_TTL = 24 * 3600

UA = os.environ.get("SEC_USER_AGENT", "Starchild 13F dashboard contact@iamstarchild.com")

app = Flask(__name__, static_folder=None)


# ============ helpers ============

def _read_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _read_csv(p: Path):
    if not p.exists():
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def _fund_dirs():
    if not DATA_DIR.exists():
        return []
    out = []
    for d in sorted(DATA_DIR.iterdir()):
        if d.is_dir() and d.name.split("-")[0].isdigit():
            out.append(d)
    return out


def _fund_summary(d: Path):
    mgr = _read_json(d / "manager.json") or {}
    filings = _read_csv(d / "filings.csv")
    valid = [f for f in filings if f.get("period")]
    valid.sort(key=lambda r: r["period"], reverse=True)
    latest_val = 0
    latest_count = 0
    if valid:
        try: latest_val = int(valid[0].get("total_value_usd") or 0)
        except: pass
        try: latest_count = int(valid[0].get("holdings_count") or 0)
        except: pass
    return {
        "cik": mgr.get("cik") or d.name.split("-")[0],
        "name": mgr.get("name") or mgr.get("sec_name") or d.name,
        "slug": d.name,
        "filings_count": len(valid),
        "latest_period": valid[0]["period"] if valid else "",
        "latest_value_usd": latest_val,
        "latest_holdings_count": latest_count,
    }


def _fund_dir_by_slug(slug: str) -> Path:
    d = DATA_DIR / slug
    if not d.exists() or not d.is_dir():
        abort(404)
    return d


# ============ fund APIs ============

@app.route("/api/funds")
def api_funds():
    return jsonify({"funds": [_fund_summary(d) for d in _fund_dirs()]})


@app.route("/api/funds/<slug>")
def api_fund_detail(slug):
    d = _fund_dir_by_slug(slug)
    mgr = _read_json(d / "manager.json") or {}
    filings = _read_csv(d / "filings.csv")
    valid = [f for f in filings if f.get("period")]
    for f in valid:
        try: f["total_value_usd"] = int(f.get("total_value_usd") or 0)
        except: f["total_value_usd"] = 0
        try: f["holdings_count"] = int(f.get("holdings_count") or 0)
        except: f["holdings_count"] = 0
    deduped = sorted(_dedupe_filings(valid).values(), key=lambda r: r["period"])
    return jsonify({
        "manager": {
            "cik": mgr.get("cik") or d.name.split("-")[0],
            "name": mgr.get("name") or d.name,
            "address": mgr.get("address"),
        },
        "filings": deduped,
    })


def _dedupe_filings(filings: list[dict]) -> dict[str, dict]:
    """When multiple filings share a period (e.g. 13F-HR plus 13F-HR/A),
    SEC allows the amendment to either replace OR add to the original.
    Confidential-treatment amendments often add only a few items, so
    'latest filed' can collapse total value to a few %.

    Heuristic: keep the row with the highest total_value_usd. If tied,
    take the latest filed."""
    by_period: dict[str, dict] = {}
    for f in filings:
        p = f.get("period")
        if not p: continue
        cur = by_period.get(p)
        if cur is None:
            by_period[p] = f
            continue
        cv = _safe_int(f.get("total_value_usd"))
        pv = _safe_int(cur.get("total_value_usd"))
        if cv > pv or (cv == pv and f.get("filed", "") > cur.get("filed", "")):
            by_period[p] = f
    return by_period


def _safe_int(v) -> int:
    try: return int(v or 0)
    except: return 0


@app.route("/api/funds/<slug>/holdings/<period>")
def api_holdings(slug, period):
    d = _fund_dir_by_slug(slug)
    p = d / period / "holdings.json"
    if not p.exists():
        abort(404)
    holdings = _read_json(p) or []
    for h in holdings:
        try: h["value_usd"] = int(h.get("value_usd") or 0)
        except: h["value_usd"] = 0
        try: h["sshPrnamt"] = int(h.get("sshPrnamt") or 0)
        except: h["sshPrnamt"] = 0
    holdings.sort(key=lambda h: -h["value_usd"])

    total_count = len(holdings)
    total_value = sum(h["value_usd"] for h in holdings)
    # Pagination: protect the browser. Default top 200, hard-capped at 1000.
    try: limit = min(int(request.args.get("limit", "200")), 1000)
    except: limit = 200
    try: offset = max(int(request.args.get("offset", "0")), 0)
    except: offset = 0
    sliced = holdings[offset : offset + limit]

    # For the treemap, always send a compact top-40-by-value summary regardless of pagination,
    # so the chart doesn't re-render as the table paginates.
    top40 = holdings[:40]
    others = holdings[40:]
    other_value = sum(h["value_usd"] for h in others)
    treemap = [{
        "name": h.get("ticker") or h.get("nameOfIssuer") or h.get("cusip"),
        "full": h.get("nameOfIssuer", ""),
        "value": h["value_usd"],
        "putCall": h.get("putCall", ""),
    } for h in top40]
    if other_value > 0:
        treemap.append({"name": f"+{len(others)} more", "full": "Other holdings", "value": other_value, "putCall": ""})

    return jsonify({
        "holdings": sliced,
        "treemap": treemap,
        "total_count": total_count,
        "total_value_usd": total_value,
        "returned": len(sliced),
        "offset": offset,
        "limit": limit,
        "meta": _read_json(d / period / "meta.json") or {},
    })


@app.route("/api/funds/<slug>/diff/<prev>/<curr>")
def api_diff(slug, prev, curr):
    d = _fund_dir_by_slug(slug)
    p = d / "diffs" / f"{prev}_to_{curr}.csv"
    if not p.exists():
        return jsonify({"diff": [], "available": False})
    rows = _read_csv(p)
    for r in rows:
        for k in ("prev_shares","curr_shares","shares_delta","prev_value_usd","curr_value_usd","value_delta_usd"):
            try: r[k] = int(r[k] or 0)
            except: r[k] = 0
        try:
            r["shares_pct_change"] = float(r["shares_pct_change"]) if r["shares_pct_change"] not in ("", None) else None
        except:
            r["shares_pct_change"] = None
    return jsonify({"diff": rows, "available": True})


# ============ SEC search & download ============

@app.route("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"candidates": []})
    try:
        # EDGAR full-text search — bump hits so recent filings aren't lost to relevance ranking
        url = "https://efts.sec.gov/LATEST/search-index"
        r = requests.get(url, params={"q": f'"{q}"', "forms": "13F-HR", "hits": 100},
                         headers={"User-Agent": UA, "Accept-Encoding": "gzip"}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return jsonify({"candidates": [], "error": str(e)}), 200
    hits = data.get("hits", {}).get("hits", [])
    by_cik = {}
    for hit in hits:
        src = hit.get("_source", {})
        filed = src.get("file_date", "")
        for cik, name in zip(src.get("ciks", []), src.get("display_names", [])):
            cik = cik.lstrip("0") or "0"
            clean = re.sub(r"\s*\(CIK\s*\d+\)\s*$", "", name).strip()
            if cik not in by_cik:
                by_cik[cik] = {"cik": cik, "name": clean, "hits": 0, "last_filed": filed}
            by_cik[cik]["hits"] += 1
            if filed > by_cik[cik]["last_filed"]:
                by_cik[cik]["last_filed"] = filed
    # Rank: active filers (filed within ~2 years) first, then most-recent, then hit-count
    cutoff = f"{date.today().year - 2}-01-01"
    def _date_key(s):
        try: return int(s.replace("-",""))
        except: return 0
    ranked = sorted(by_cik.values(), key=lambda r: (
        0 if r["last_filed"] >= cutoff else 1,
        -_date_key(r["last_filed"]),
        -r["hits"],
    ))[:15]
    # Best-effort detection of already-downloaded — also scan disk
    existing = {d.name.split("-")[0] for d in _fund_dirs()}
    cutoff = f"{date.today().year - 2}-01-01"
    # Authoritative last-filed: hit submissions JSON for the top candidates.
    # FTS hits=100 may still miss a very-active filer's most-recent quarter.
    for r in ranked[:8]:
        try:
            sub = requests.get(
                f"https://data.sec.gov/submissions/CIK{r['cik'].zfill(10)}.json",
                headers={"User-Agent": UA}, timeout=8,
            ).json()
            forms = sub.get("filings", {}).get("recent", {}).get("form", [])
            dates = sub.get("filings", {}).get("recent", {}).get("filingDate", [])
            latest = ""
            for f, d2 in zip(forms, dates):
                if f.startswith("13F-HR") and d2 > latest:
                    latest = d2
            if latest > r["last_filed"]:
                r["last_filed"] = latest
        except Exception:
            pass
    # Re-sort with corrected dates
    def _date_key(s):
        try: return int(s.replace("-",""))
        except: return 0
    ranked = sorted(ranked, key=lambda r: (
        0 if r["last_filed"] >= cutoff else 1,
        -_date_key(r["last_filed"]),
        -r["hits"],
    ))
    for r in ranked:
        r["already_downloaded"] = r["cik"] in existing
        r["active"] = r["last_filed"] >= cutoff
    return jsonify({"candidates": ranked})


def _slug_for(cik: str, name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()[:60] or "fund"
    return f"{cik}-{s}"


# ---- background download jobs ----

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _run_download(job_id: str, cik: str, limit: int):
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started_at"] = time.time()
    cmd = [
        sys.executable, str(DOWNLOAD_SCRIPT),
        "--cik", cik,
        "--enrich-tickers", "--with-diffs",
    ]
    if limit:
        cmd += ["--limit", str(limit)]
    try:
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=env, cwd="/data/workspace", text=True, bufsize=1)
        with _jobs_lock:
            _jobs[job_id]["pid"] = proc.pid
        log_lines: list[str] = []
        slug_out = None
        for line in proc.stdout:
            line = line.rstrip()
            log_lines.append(line)
            with _jobs_lock:
                _jobs[job_id]["log"] = log_lines[-60:]
                # parse progress
                m = re.match(r"\[(\d+)/(\d+)\]", line)
                if m:
                    _jobs[job_id]["progress"] = {
                        "current": int(m.group(1)),
                        "total": int(m.group(2)),
                    }
                if line.startswith("Resolved:"):
                    _jobs[job_id]["resolved_name"] = line.replace("Resolved:", "").strip()
                if line.startswith("output/13f/"):
                    slug_out = line.replace("output/13f/", "").strip().split("/")[0]
                if "Found" in line and "13F filings" in line:
                    mm = re.search(r"Found (\d+)", line)
                    if mm:
                        _jobs[job_id]["filings_total"] = int(mm.group(1))
                if "OpenFIGI:" in line:
                    _jobs[job_id]["phase"] = "Resolving tickers"
                elif "diffs..." in line:
                    _jobs[job_id]["phase"] = "Building diffs"
                elif line.startswith("[") and "13F-HR" in line:
                    _jobs[job_id]["phase"] = f"Downloading filings"
        rc = proc.wait()
        with _jobs_lock:
            _jobs[job_id]["status"] = "ok" if rc == 0 else "error"
            _jobs[job_id]["return_code"] = rc
            _jobs[job_id]["finished_at"] = time.time()
            if slug_out:
                _jobs[job_id]["slug"] = slug_out
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
            _jobs[job_id]["finished_at"] = time.time()


@app.route("/api/download", methods=["POST"])
def api_download():
    body = request.get_json(silent=True) or {}
    cik = str(body.get("cik", "")).strip()
    if not cik.isdigit():
        return jsonify({"error": "valid CIK required"}), 400
    limit = int(body.get("limit", 8) or 0) or None
    job_id = uuid.uuid4().hex[:10]
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id, "cik": cik, "limit": limit,
            "status": "queued", "log": [], "phase": "Queued",
            "queued_at": time.time(),
        }
    t = threading.Thread(target=_run_download, args=(job_id, cik, limit), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/api/download/<job_id>")
def api_download_status(job_id):
    with _jobs_lock:
        j = _jobs.get(job_id)
    if not j:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(j)


# ============ baselines ============

def _load_baseline_cache() -> dict:
    if BASELINE_CACHE_PATH.exists():
        try:
            return json.loads(BASELINE_CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_baseline_cache(c: dict):
    BASELINE_CACHE_PATH.write_text(json.dumps(c, indent=2))


def _fetch_baseline_monthly(ticker: str) -> dict[str, float]:
    """Return {YYYY-MM-DD: close} for monthly bars, cached for BASELINE_TTL."""
    cache = _load_baseline_cache()
    entry = cache.get(ticker)
    if entry and (time.time() - entry.get("fetched_at", 0)) < BASELINE_TTL:
        return entry["data"]
    sys.path.insert(0, "/data/workspace/skills/twelvedata")
    try:
        from exports import twelvedata_time_series  # type: ignore
    except Exception as e:
        return entry["data"] if entry else {}
    try:
        r = twelvedata_time_series(symbol=ticker, interval="1month", outputsize=300)
        values = r.get("values") or []
    except Exception:
        return entry["data"] if entry else {}
    data = {}
    for v in values:
        d = v.get("datetime")
        c = v.get("close")
        if d and c:
            try: data[d] = float(c)
            except: pass
    cache[ticker] = {"fetched_at": time.time(), "data": data}
    _save_baseline_cache(cache)
    return data


def _quarter_close_for_period(monthly: dict[str, float], period: str) -> float | None:
    """Period is like '2024-09-30'. Return close of that month (or nearest prior month)."""
    if not monthly:
        return None
    # twelvedata monthly bars use the first-of-month date convention. Try both.
    y, m, _ = period.split("-")
    candidates = [
        f"{y}-{m}-01",
        f"{y}-{m}-28",
        f"{y}-{m}-30",
        f"{y}-{m}-31",
    ]
    for c in candidates:
        if c in monthly: return monthly[c]
    # Fall back to closest date in that month
    ym = period[:7]
    same_month = [d for d in monthly if d.startswith(ym)]
    if same_month:
        return monthly[sorted(same_month)[-1]]
    return None


@app.route("/api/funds/<slug>/baselines")
def api_baselines(slug):
    d = _fund_dir_by_slug(slug)
    filings = _read_csv(d / "filings.csv")
    valid = [f for f in filings if f.get("period")]
    for f in valid:
        f["total_value_usd"] = _safe_int(f.get("total_value_usd"))
    by_period = _dedupe_filings(valid)
    periods = sorted(by_period.keys())
    if not periods:
        return jsonify({"periods": [], "baselines": {}, "fund": []})

    fund_aum = []
    for p in periods:
        try:
            fund_aum.append(int(by_period[p].get("total_value_usd") or 0))
        except:
            fund_aum.append(0)

    baselines = {}
    for ticker, meta in BASELINES.items():
        monthly = _fetch_baseline_monthly(ticker)
        closes = [_quarter_close_for_period(monthly, p) for p in periods]
        baselines[ticker] = {**meta, "ticker": ticker, "closes": closes}

    return jsonify({"periods": periods, "baselines": baselines, "fund_aum": fund_aum})


# ============ static ============

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:fname>")
def static_files(fname):
    if (STATIC_DIR / fname).exists():
        return send_from_directory(STATIC_DIR, fname)
    abort(404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    print(f"13F dashboard serving from {DATA_DIR} on http://127.0.0.1:{port}", flush=True)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
