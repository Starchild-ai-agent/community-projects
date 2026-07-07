#!/usr/bin/env python3
"""
earnings-surprise-detector: verify_earnings.py
Pulls actual quarterly earnings growth via mx-data (东方财富) and compares
to expected/research-claimed growth. Outputs a verdict: PASS / WARN / FAIL.

Usage:
  python3 verify_earnings.py --stock "太辰光" --code 300570 \
      --expected-min 80 --expected-max 120 --metric 扣非归母净利润同比

Requires: MX_APIKEY environment variable (from workspace/.env)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────

MX_DATA_SCRIPT = Path(__file__).parent.parent.parent / "mx-data" / "mx_data.py"

METRIC_QUERIES = {
    "扣非归母净利润同比": "{stock} 扣非归母净利润同比 最新报告期",
    "营收同比": "{stock} 营业收入同比 最新报告期",
    "净利润同比": "{stock} 净利润同比 最新报告期",
    "EPS": "{stock} 每股收益 最新报告期",
}

# Warn zone: actual is within 20% below expected-min
WARN_THRESHOLD = 0.80  # actual >= expected_min * 0.80 → WARN; below → FAIL


# ── Helpers ────────────────────────────────────────────────────────────────

def run_mx_data(query: str) -> dict:
    """Call mx_data.py and parse the JSON output."""
    if not MX_DATA_SCRIPT.exists():
        return {"error": f"mx-data script not found at {MX_DATA_SCRIPT}"}

    cmd = [sys.executable, str(MX_DATA_SCRIPT), query]
    env = os.environ.copy()
    if "MX_APIKEY" not in env:
        return {"error": "MX_APIKEY not set in environment. Cannot query mx-data."}

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, env=env
        )
    except subprocess.TimeoutExpired:
        return {"error": "mx-data query timed out (60s)"}
    except Exception as e:
        return {"error": f"mx-data execution failed: {e}"}

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "113" in stderr or "调用次数已达上限" in stderr:
            return {"error": "mx-data API quota exhausted (status 113). Use linqi-data as backup."}
        return {"error": f"mx-data failed: {stderr[:500]}"}

    # mx_data.py prints preview to stdout and saves raw JSON to file
    stdout = result.stdout.strip()

    # Try to find the raw JSON file
    raw_json_path = None
    for line in stdout.split("\n"):
        if "raw" in line.lower() and ".json" in line.lower():
            match = re.search(r'(/[\w/.]+_raw\.json)', line)
            if match:
                raw_json_path = match.group(1)
                break

    # Also check default output dir
    if not raw_json_path:
        default_dir = Path("/root/.openclaw/workspace/mx_data/output")
        if default_dir.exists():
            raw_files = sorted(default_dir.glob("*_raw.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if raw_files:
                raw_json_path = str(raw_files[0])

    # Parse from stdout if we can find JSON-like content
    parsed = parse_stdout(stdout)
    if parsed:
        return parsed

    if raw_json_path and Path(raw_json_path).exists():
        try:
            with open(raw_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {"error": "Could not parse mx-data output", "raw_stdout": stdout[:2000]}


def parse_stdout(stdout: str) -> dict | None:
    """Try to extract growth data from mx_data.py stdout preview.
    Only use as fallback if JSON parsing fails. Look for percentage values
    in data rows (not date rows) — avoid matching year numbers like 2025/2026."""
    if not stdout:
        return None

    lines = stdout.split("\n")
    data_lines = []
    in_table = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Table rows have | separators
        if "|" in line and not line.startswith("|---"):
            in_table = True
            data_lines.append(line)
        elif in_table and "|" not in line:
            break  # End of table

    if not data_lines:
        return None

    # Skip header row (contains column names like "date", "同比增长率")
    # Data rows have dates like "2026一季报" and values like "-21.23%"
    for line in data_lines:
        if "date" in line.lower() or "同比增长" in line:
            continue  # Skip header
        # Match percentage values specifically: -21.23% or 12.61%
        pct_matches = re.findall(r'(-?\d+\.?\d*)\s*%', line)
        for m in pct_matches:
            try:
                val = float(m)
                # Reasonable growth range: -500% to +5000%
                if -500 <= val <= 5000:
                    return {
                        "parsed_from_stdout": True,
                        "growth_value": val,
                        "raw_line": line,
                        "all_data_lines": data_lines[:10],
                    }
            except ValueError:
                continue

    return None


def extract_growth_from_json(data: dict, metric: str) -> dict:
    """Extract the growth value from mx-data JSON response."""
    if "error" in data:
        return data

    # Check for API error status
    if isinstance(data, dict) and data.get("status") == 113:
        return {"error": "mx-data API quota exhausted (status 113). Use linqi-data as backup."}

    # Navigate the mx-data response structure:
    # data.data.searchDataResultDTO.dataTableDTOList[]
    # (some responses nest as data.data, others as data directly)
    inner = data.get("data", data)
    if isinstance(inner, dict):
        if inner.get("status") == 113:
            return {"error": "mx-data API quota exhausted."}
        # Try nested path: data.data.searchDataResultDTO.dataTableDTOList
        nested = inner.get("data", {})
        if isinstance(nested, dict) and nested.get("searchDataResultDTO"):
            table_list = nested["searchDataResultDTO"].get("dataTableDTOList") or \
                         nested["searchDataResultDTO"].get("rawDataTableDTOList") or []
        else:
            # Fallback: data.dataTableDTOList or data.searchDataResultDTO.dataTableDTOList
            if inner.get("searchDataResultDTO"):
                table_list = inner["searchDataResultDTO"].get("dataTableDTOList") or []
            else:
                table_list = inner.get("dataTableDTOList") or inner.get("rawDataTableDTOList") or []
    elif isinstance(inner, list):
        table_list = inner
    else:
        table_list = []

    if not table_list:
        # Try the stdout-parsed format
        if "growth_value" in data:
            return {
                "growth_value": data["growth_value"],
                "source": "mx-data stdout (parsed)",
                "raw_line": data.get("raw_line", ""),
            }
        return {"error": "No data tables returned from mx-data", "raw": str(data)[:500]}

    results = []
    for block in table_list:
        if not isinstance(block, dict):
            continue

        title = block.get("title", "")
        entity_name = block.get("entityName", "")
        table = block.get("table") or block.get("rawTable") or {}
        name_map = block.get("nameMap", {})

        # Extract values from table structure
        # table format: { "headName": [dates...], "indicator_code": [values...] }
        head_names = table.get("headName", [])
        if not isinstance(head_names, list):
            head_names = [head_names]

        for key, values in table.items():
            if key == "headName":
                continue
            if not isinstance(values, list):
                values = [values]

            # Get human-readable column name
            col_name = ""
            if isinstance(name_map, dict):
                mapped = name_map.get(key)
                if mapped is None and str(key).isdigit():
                    mapped = name_map.get(int(key))
                if mapped:
                    col_name = str(mapped)

            for i, val in enumerate(values):
                date = head_names[i] if i < len(head_names) else ""
                val_str = str(val).strip() if val is not None else ""
                # Try to parse as float
                num_val = None
                try:
                    # Remove % and commas
                    cleaned = re.sub(r'[%\',]', '', val_str)
                    num_val = float(cleaned) if cleaned else None
                except (ValueError, TypeError):
                    pass

                results.append({
                    "title": title,
                    "entity": entity_name,
                    "column": col_name or key,
                    "date": str(date),
                    "value": val_str,
                    "numeric": num_val,
                })

    if not results:
        return {"error": "Could not extract values from mx-data response", "raw": str(data)[:500]}

    # Find the most relevant growth value
    # Prefer entries with "同比" or "增长" in the column name, latest date
    growth_entries = [r for r in results if r["numeric"] is not None]
    if not growth_entries:
        return {
            "error": "No numeric values found in mx-data response",
            "raw_results": results[:5],
        }

    # Sort by date descending (latest first) — assume date strings sort correctly
    growth_entries.sort(key=lambda r: r["date"], reverse=True)

    # Prefer entries whose column name contains 同比 or 增长
    preferred = [r for r in growth_entries if "同比" in r["column"] or "增长" in r["column"]]
    best = preferred[0] if preferred else growth_entries[0]

    return {
        "growth_value": best["numeric"],
        "value_str": best["value"],
        "date": best["date"],
        "column": best["column"],
        "entity": best["entity"],
        "source": "mx-data (东方财富)",
        "all_results": results[:10],
    }


def compute_verdict(actual: float, expected_min: float, expected_max: float) -> dict:
    """Compute PASS/WARN/FAIL verdict."""
    if actual < 0 and expected_min > 0:
        return {
            "verdict": "FAIL",
            "reason": f"Actual is negative ({actual}%) while positive growth was expected.",
            "action": "Exclude or downweight. Do not recommend entry. Thesis is broken at earnings level.",
        }

    if actual >= expected_min:
        return {
            "verdict": "PASS",
            "reason": f"Actual ({actual}%) ≥ expected minimum ({expected_min}%).",
            "action": "Proceed with recommendation. Earnings confirm the thesis.",
        }

    # WARN zone: actual is below expected_min but within 20% of it.
    # For positive expected_min: warn_floor = expected_min * 0.80 (e.g., 80→64)
    # For negative expected_min: warn_floor = expected_min * 1.20 (e.g., -18→-21.6)
    if expected_min > 0:
        warn_floor = expected_min * WARN_THRESHOLD
    else:
        warn_floor = expected_min * (2.0 - WARN_THRESHOLD)  # 1.20 for 0.80 threshold

    if actual >= warn_floor:
        return {
            "verdict": "WARN",
            "reason": f"Actual ({actual}%) is below expected min ({expected_min}%) but above warn floor ({warn_floor:.1f}%).",
            "action": "Size down 50%. Thesis partially confirmed but momentum weaker than expected.",
        }

    return {
        "verdict": "FAIL",
        "reason": f"Actual ({actual}%) is well below expected min ({expected_min}%).",
        "action": "Exclude or downweight. Do not generate entry prices or execution tables.",
    }


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Verify actual earnings growth vs expectations using mx-data"
    )
    parser.add_argument("--stock", required=True, help="Stock name (e.g. 太辰光)")
    parser.add_argument("--code", required=True, type=int, help="Stock code (e.g. 300570)")
    parser.add_argument("--expected-min", required=True, type=float,
                        help="Expected minimum growth %% (e.g. 80)")
    parser.add_argument("--expected-max", required=True, type=float,
                        help="Expected maximum growth %% (e.g. 120)")
    parser.add_argument("--metric", default="扣非归母净利润同比",
                        choices=list(METRIC_QUERIES.keys()),
                        help="Metric to verify (default: 扣非归母净利润同比)")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  EARNINGS VERIFICATION: {args.stock} ({args.code})")
    print(f"  Metric: {args.metric}")
    print(f"  Expected range: {args.expected_min}% ~ {args.expected_max}%")
    print(f"{'='*70}\n")

    # Build query
    query = METRIC_QUERIES[args.metric].format(stock=args.stock)
    print(f"[1/3] Querying mx-data: {query}")

    # Pull data
    raw = run_mx_data(query)
    if "error" in raw:
        print(f"\n❌ ERROR: {raw['error']}")
        if "quota" in raw["error"].lower():
            print("   → Backup: try linqi-data skill or manual verification via:")
            print(f"     python3 skills/mx-data/mx_data.py \"{query}\"")
        sys.exit(1)

    # Extract growth value
    print(f"[2/3] Parsing response...")
    extracted = extract_growth_from_json(raw, args.metric)
    if "error" in extracted:
        print(f"\n❌ ERROR: {extracted['error']}")
        print(f"   Raw response preview: {str(raw)[:500]}")
        sys.exit(1)

    actual = extracted["growth_value"]
    date = extracted.get("date", "unknown")
    source = extracted.get("source", "mx-data")

    print(f"   Actual {args.metric}: {actual}% (report date: {date})")

    # Compute verdict
    print(f"[3/3] Computing verdict...")
    verdict = compute_verdict(actual, args.expected_min, args.expected_max)

    # Output
    print(f"\n{'─'*70}")
    print(f"  VERDICT: {verdict['verdict']}")
    print(f"{'─'*70}")
    print(f"  Stock:          {args.stock} ({args.code})")
    print(f"  Metric:         {args.metric}")
    print(f"  Expected:       {args.expected_min}% ~ {args.expected_max}%")
    print(f"  Actual:         {actual}%")
    print(f"  Report date:    {date}")
    print(f"  Source:         {source}")
    print(f"  Reason:         {verdict['reason']}")
    print(f"  Action:         {verdict['action']}")
    print(f"{'─'*70}\n")

    # JSON output for programmatic use
    output = {
        "stock": args.stock,
        "code": args.code,
        "metric": args.metric,
        "expected_min": args.expected_min,
        "expected_max": args.expected_max,
        "actual": actual,
        "report_date": date,
        "source": source,
        "verdict": verdict["verdict"],
        "reason": verdict["reason"],
        "action": verdict["action"],
    }
    print("JSON:")
    print(json.dumps(output, ensure_ascii=False, indent=2))

    # Exit code: 0=PASS, 1=WARN, 2=FAIL
    exit_codes = {"PASS": 0, "WARN": 1, "FAIL": 2}
    sys.exit(exit_codes.get(verdict["verdict"], 0))


if __name__ == "__main__":
    main()
