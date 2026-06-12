"""Trust gate — the product's integrity layer.

A simulator that can't reproduce a book we DO have truth for cannot be trusted
on a book we don't. So before showing any number, the product:

  1. calibrate(): tune the fill model's free param (fill_eff) on a
     ground-truth asset so simulated fills/day match the real bot's fills/day.
  2. trust_score(): after calibration, compare simulated repeatable & directional
     PnL/day against the measured truth. Returns 0-100 + a label. Low score =>
     the OHLC model can't pin exact dollars for this regime; route the user to
     real-tape validation (the quotesim-tape-validation skill) instead.

Ground-truth reference (measured live, NATGAS, 7d):
    repeatable ≈ +$28/day   directional ≈ +$26/day   fills ≈ 23/day
"""
from .engine import Engine
from .fillmodels import OHLCTouchFill


def calibrate(asset, strat, gt_events, target_fills_per_day, lo=0.01, hi=0.5):
    """Binary-search fill_eff so sim fills/day ~ target. Returns (fe, summary)."""
    best = None
    for _ in range(22):
        fe = (lo + hi) / 2
        _, s = Engine(asset, strat).run(gt_events, OHLCTouchFill(fill_eff=fe))
        if best is None or abs(s["fills_per_day"] - target_fills_per_day) < abs(best[1]["fills_per_day"] - target_fills_per_day):
            best = (fe, s)
        if s["fills_per_day"] > target_fills_per_day:
            hi = fe
        else:
            lo = fe
    return best


def trust_score(sim_summary, truth):
    """Compare sim vs measured truth on a ground-truth asset. 0-100 + label.

    truth: {'repeatable_per_day','directional_per_day','fills_per_day'}
    """
    def rel_err(a, b):
        denom = max(abs(b), 1e-6)
        return abs(a - b) / denom

    e_rep = rel_err(sim_summary["repeatable_per_day"], truth["repeatable_per_day"])
    e_dir = rel_err(sim_summary["directional_per_day"], truth["directional_per_day"])
    e_fill = rel_err(sim_summary["fills_per_day"], truth["fills_per_day"])
    # sign agreement matters most for directional
    sign_ok = (sim_summary["directional_per_day"] >= 0) == (truth["directional_per_day"] >= 0)

    # score: start 100, penalize each relative error, hard hit if sign flips
    score = 100.0
    score -= min(40, e_rep * 40)
    score -= min(30, e_dir * 30)
    score -= min(15, e_fill * 15)
    if not sign_ok:
        score -= 40
    score = max(0, round(score))

    if score >= 75:
        label = "Dollar-accurate — checked against a live book"
    elif score >= 45:
        label = "Shape-accurate — directional read solid; validate for exact $"
    else:
        label = "Fast preview — risk shape is real; validate for exact $"
    return {
        "score": score, "label": label, "sign_ok": sign_ok,
        "err_repeatable": round(e_rep, 2),
        "err_directional": round(e_dir, 2),
        "err_fills": round(e_fill, 2),
    }
