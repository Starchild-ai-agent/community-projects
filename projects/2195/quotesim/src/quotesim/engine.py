"""Asset-agnostic market-making simulator engine.

The engine is dumb on purpose: it builds the ladder from StrategyConfig, asks
the fill model what filled, updates inventory/avg-cost, and accrues PnL in three
buckets. Swap the asset (price path) or the config and nothing else changes.

PnL decomposition (the only output that matters):
  spread_capture  : Σ (oracle - fill_price) * signed_qty   [repeatable edge]
  directional     : Σ inventory * Δoracle                   [inventory risk]
  fees            : maker rebate earned - taker paid        [subsidy]
"""
import math
from dataclasses import dataclass, field
from .config import AssetConfig, StrategyConfig
from .fillmodels import Fill


def _ladder_bps(n, lo, hi):
    if n == 1:
        return [lo]
    r = (hi / lo) ** (1 / (n - 1))
    return [lo * (r ** i) for i in range(n)]


@dataclass
class State:
    inv: float = 0.0          # signed lots
    avg: float = 0.0          # avg cost of open inventory
    realized: float = 0.0
    spread_pnl: float = 0.0
    directional_pnl: float = 0.0
    fees: float = 0.0
    n_fills: int = 0
    gross_vol: float = 0.0
    peak_inv_usd: float = 0.0


class Engine:
    def __init__(self, asset: AssetConfig, strat: StrategyConfig):
        self.a = asset
        self.s = strat
        self._bps = _ladder_bps(strat.n_levels, strat.min_bps, strat.band_bps)
        self._lvl_notional = strat.side_notional_usd / strat.n_levels

    def _quotes(self, oracle: float, st: State):
        """Build the ladder we'd rest right now, applying inventory skew."""
        s = self.s
        inv_usd = st.inv * oracle
        skewed = abs(inv_usd) > s.inv_hard_usd
        close_skew_on = abs(st.inv) > s.close_skew_lots
        long_heavy = inv_usd > 0
        quotes = []
        for k in range(s.n_levels):
            off = self._bps[k] / 10000.0
            lot_qty = self._lvl_notional / oracle
            # BUY (bid) side
            bid_off = off
            if close_skew_on and long_heavy:        # adding side = bid when long
                bid_off *= s.close_skew_mult
            if not (skewed and long_heavy):          # suppressed when too long
                quotes.append(("BUY", oracle * (1 - bid_off), lot_qty))
            # SELL (ask) side
            ask_off = off
            if close_skew_on and not long_heavy:     # adding side = ask when short
                ask_off *= s.close_skew_mult
            if not (skewed and not long_heavy):
                quotes.append(("SELL", oracle * (1 + ask_off), lot_qty))
        return quotes

    def _apply(self, f: Fill, st: State):
        st.n_fills += 1
        st.gross_vol += f.price * f.qty
        # fees: every fill is maker in this model (resting quote)
        st.fees += -self.a.maker_fee_bps / 10000.0 * f.price * f.qty
        st.spread_pnl += (f.oracle - f.price) * (f.qty if f.side == "BUY" else -f.qty)
        if f.side == "BUY":
            if st.inv >= 0:
                new = st.inv + f.qty
                st.avg = (st.avg * st.inv + f.price * f.qty) / new if new else 0.0
                st.inv = new
            else:
                close = min(f.qty, -st.inv)
                st.realized += (st.avg - f.price) * close
                st.inv += f.qty
                st.avg = f.price if st.inv > 0 else (0.0 if st.inv == 0 else st.avg)
        else:  # SELL
            if st.inv <= 0:
                new = st.inv - f.qty
                st.avg = (st.avg * (-st.inv) + f.price * f.qty) / (-new) if new else 0.0
                st.inv = new
            else:
                close = min(f.qty, st.inv)
                st.realized += (f.price - st.avg) * close
                st.inv -= f.qty
                st.avg = f.price if st.inv < 0 else (0.0 if st.inv == 0 else st.avg)

    def run(self, events, fill_model, record=False, record_max=400):
        """events: iterable of {t,o,h,l,c}. Returns (State, summary dict).
        If record=True, summary['inv_path'] holds downsampled [(t, inv_usd)]."""
        st = State()
        events = list(events)
        path = []
        step = max(1, len(events) // record_max) if record else 1
        for i, ev in enumerate(events):
            oracle = ev["o"]
            if oracle <= 0:
                continue
            st.peak_inv_usd = max(st.peak_inv_usd, abs(st.inv * oracle))
            quotes = self._quotes(oracle, st)
            for f in fill_model.fills(ev, quotes, st):
                self._apply(f, st)
            st.directional_pnl += st.inv * (ev["c"] - ev["o"])
            if record and i % step == 0:
                path.append([ev["t"], round(st.inv * ev["c"])])

        end = events[-1]["c"]
        mtm = ((end - st.avg) * st.inv if st.inv > 0
               else (st.avg - end) * (-st.inv) if st.inv < 0 else 0.0)
        span = (events[-1]["t"] - events[0]["t"]) / 86400 or 1
        repeatable = st.spread_pnl + st.fees
        summary = {
            "trust_class": fill_model.trust_class,
            "span_days": round(span, 2),
            "n_fills": st.n_fills,
            "fills_per_day": round(st.n_fills / span, 1),
            "gross_vol_usd": round(st.gross_vol),
            "spread_capture": round(st.spread_pnl, 2),
            "fees": round(st.fees, 2),
            "repeatable": round(repeatable, 2),
            "repeatable_per_day": round(repeatable / span, 2),
            "directional": round(st.directional_pnl, 2),
            "directional_per_day": round(st.directional_pnl / span, 2),
            "total": round(repeatable + st.directional_pnl, 2),
            "total_per_day": round((repeatable + st.directional_pnl) / span, 2),
            "realized": round(st.realized, 2),
            "open_mtm": round(mtm, 2),
            "end_inv_lots": round(st.inv, 1),
            "peak_inv_usd": round(st.peak_inv_usd),
        }
        if record:
            summary["inv_path"] = path
        return st, summary


def realized_vol_annual(events, bars_per_day=288):
    cl = [e["c"] for e in events]
    rets = [math.log(cl[i] / cl[i - 1]) for i in range(1, len(cl)) if cl[i - 1] > 0]
    if not rets:
        return 0.0
    m = sum(rets) / len(rets)
    sd = (sum((r - m) ** 2 for r in rets) / len(rets)) ** 0.5
    return sd * math.sqrt(bars_per_day * 365) * 100
