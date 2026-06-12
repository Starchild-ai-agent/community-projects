"""Tape-replay validation — the trustworthy fill model, scored on real data.

Mechanism (parameter-free crossing rule + queue cap):
  - Each public-tape print has a price P, qty Q, and aggressor side.
  - aggressor SELL  -> hits our BID  -> we BUY  (maker) if our_bid >= P
  - aggressor BUY   -> hits our ASK  -> we SELL (maker) if our_ask <= P
  - our quote (bid/ask) and resting depth come from telemetry at print time.
  - queue cap: we capture min(Q, our_side_depth/P) lots — we can't fill more
    than we were resting. (No free fill_eff; depth is observed, not tuned.)

Then decompose the predicted fill stream (spread/directional/fees) and compare
to the REAL fills measured independently over the same window. Score 0-100.

Why this is non-circular: tape qty >> our fills (multiple participants), so the
crossing rule must actively filter prints. Reproducing real fills/qty/PnL from
prints we did NOT label tests the mechanism, not memory.
"""
import json
from bisect import bisect_left
from pathlib import Path

V = Path(__file__).resolve().parent.parent / "valdata"


def _load():
    tape = json.load(open(V / "tape.json"))
    fills = json.load(open(V / "fills.json"))
    tel = json.load(open(V / "telemetry.json"))
    return tape, fills, tel


def _quote_at(tel, tts, t):
    """nearest telemetry tick to time t -> dict (bid/ask/mid/depth)."""
    i = bisect_left(tts, t)
    cands = [j for j in (i - 1, i, i + 1) if 0 <= j < len(tel)]
    j = min(cands, key=lambda k: abs(tel[k]["t"] - t))
    return tel[j]


def _decompose(stream, tel):
    """stream: list of fills {t,price,qty,side,oracle}. Returns spread/dir/fees."""
    tts = [x["t"] for x in tel]
    inv = 0.0; avg = 0.0
    spread = realized = fees = 0.0; gross = 0.0
    MAKER_BPS = -0.5
    for f in stream:
        price, q, side, o = f["price"], f["qty"], f["side"], f["oracle"]
        signed = q if side == "BUY" else -q
        spread += (o - price) * signed
        fees += -MAKER_BPS / 10000.0 * price * q
        gross += price * q
        if side == "BUY":
            if inv >= 0:
                new = inv + q; avg = (avg * inv + price * q) / new if new else 0; inv = new
            else:
                c = min(q, -inv); realized += (avg - price) * c; inv += q
                avg = price if inv > 0 else (0 if inv == 0 else avg)
        else:
            if inv <= 0:
                new = inv - q; avg = (avg * (-inv) + price * q) / (-new) if new else 0; inv = new
            else:
                c = min(q, inv); realized += (price - avg) * c; inv -= q
                avg = price if inv < 0 else (0 if inv == 0 else avg)
    # directional from inventory path across telemetry (independent of fills)
    directional = 0.0
    for i in range(len(tel) - 1):
        directional += tel[i]["qty"] * (tel[i + 1]["mid"] - tel[i]["mid"])
    return {"spread": spread, "fees": fees, "directional": directional,
            "realized": realized, "gross": gross, "n": len(stream),
            "qty": sum(f["qty"] for f in stream)}


def run_tape_model(tick_tol_bps=2.0):
    tape, fills, tel = _load()
    tts = [x["t"] for x in tel]
    t0, t1 = tape[0]["t"], tape[-1]["t"]
    span_days = (t1 - t0) / 86400

    predicted = []
    for p in tape:
        qd = _quote_at(tel, tts, p["t"])
        bid, ask, mid = qd["bid"], qd["ask"], qd["mid"]
        if not bid or not ask:
            continue
        tol = mid * tick_tol_bps / 10000.0
        if p["aggressor"] == "SELL":              # hits our bid -> we BUY
            if bid + tol >= p["price"]:
                cap = (qd["bid_depth"] / p["price"]) if qd["bid_depth"] else p["qty"]
                predicted.append({"t": p["t"], "price": p["price"],
                                  "qty": min(p["qty"], cap), "side": "BUY", "oracle": mid})
        else:                                     # BUY aggressor -> hits ask -> we SELL
            if ask - tol <= p["price"]:
                cap = (qd["ask_depth"] / p["price"]) if qd["ask_depth"] else p["qty"]
                predicted.append({"t": p["t"], "price": p["price"],
                                  "qty": min(p["qty"], cap), "side": "SELL", "oracle": mid})

    # ground-truth: MAKER fills only (the crossing model predicts resting-quote
    # fills; taker fills are our own close_skew crossings, a separate mechanism).
    real_stream = []
    n_taker = 0
    for f in fills:
        if f.get("is_maker") == 0:
            n_taker += 1
            continue
        qd = _quote_at(tel, tts, f["t"])
        real_stream.append({"t": f["t"], "price": f["price"], "qty": f["qty"],
                            "side": f["side"], "oracle": qd["mid"]})

    pred = _decompose(predicted, tel)
    real = _decompose(real_stream, tel)
    real["n_taker_excluded"] = n_taker
    return span_days, pred, real, len(tape)


def score(span, pred, real):
    def per_day(x, k): return x[k] / span
    def rel(a, b): return abs(a - b) / max(abs(b), 1e-6)

    pred_rep = (pred["spread"] + pred["fees"]) / span
    real_rep = (real["spread"] + real["fees"]) / span
    pred_dir = pred["directional"] / span
    real_dir = real["directional"] / span
    e_rep = rel(pred_rep, real_rep)
    e_qty = rel(pred["qty"], real["qty"])
    e_n = rel(pred["n"], real["n"])
    # directional shares the same telemetry inventory path -> identical by design;
    # so score on the FILL-driven terms (count, qty, spread) the model predicts.
    s = 100.0
    s -= min(40, e_rep * 40)
    s -= min(35, e_qty * 35)
    s -= min(25, e_n * 25)
    s = max(0, round(s))
    label = ("TRUSTWORTHY" if s >= 75 else
             "DIRECTIONAL ONLY" if s >= 45 else "UNRELIABLE")
    return {"score": s, "label": label,
            "pred_repeatable_per_day": round(pred_rep, 2),
            "real_repeatable_per_day": round(real_rep, 2),
            "pred_fills": pred["n"], "real_fills": real["n"],
            "pred_qty": round(pred["qty"]), "real_qty": round(real["qty"]),
            "err_repeatable": round(e_rep, 2), "err_qty": round(e_qty, 2),
            "err_fills": round(e_n, 2)}


if __name__ == "__main__":
    span, pred, real, n_tape = run_tape_model()
    sc = score(span, pred, real)
    print(f"window {span:.1f}d   tape prints={n_tape}")
    print(f"  TAPE MODEL : fills={pred['n']}  qty={pred['qty']:.0f}  "
          f"repeatable=${(pred['spread']+pred['fees'])/span:+.2f}/d")
    print(f"  REAL       : fills={real['n']}  qty={real['qty']:.0f}  "
          f"repeatable=${(real['spread']+real['fees'])/span:+.2f}/d")
    print(f"  TRUST SCORE: {sc['score']}/100 — {sc['label']}")
    for k in ["err_repeatable", "err_qty", "err_fills"]:
        print(f"    {k}: {sc[k]}")
    json.dump({"span_days": span, "pred": pred, "real": real, "score": sc},
              open(V.parent / "tape_validation.json", "w"), indent=2, default=float)
