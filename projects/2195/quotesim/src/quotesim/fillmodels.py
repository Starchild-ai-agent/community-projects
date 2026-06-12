"""Pluggable fill models — the heart of the trust story.

A fill model answers ONE question: given the ladder we're resting and what the
market did, which of our quotes filled, and how much?

Two implementations:
  OHLCTouchFill   — fast, rough. Fills any level the bar wicked through, scaled
                    by `fill_eff`. NO queue position. Overcounts fills. Use for
                    quick what-ifs; the validator will flag low trust.
  TapeReplayFill  — (interface) replays the real trade tape with queue depth.
                    The validated, trustworthy model. Requires tape + L2 data.

Both expose: fills(event, quotes, state) -> list[Fill]
"""
from dataclasses import dataclass
from typing import List


@dataclass
class Fill:
    side: str       # "BUY" (we bought at our bid) / "SELL" (we sold at our ask)
    price: float
    qty: float      # lots, positive
    oracle: float   # oracle/mid at fill time (for spread attribution)


class OHLCTouchFill:
    """Bar-touch model. Optimistic; overcounts. trust_class = 'rough'."""
    trust_class = "rough"

    def __init__(self, fill_eff: float = 0.10):
        # fraction of a touched level's resting notional that actually fills.
        # Calibrated per-asset by the validator against a known book.
        self.fill_eff = fill_eff

    def fills(self, event, quotes, state) -> List[Fill]:
        o, hi, lo = event["o"], event["h"], event["l"]
        out = []
        for q in quotes:           # quotes: list of (side, price, lot_qty)
            side, price, lot_qty = q
            qty = lot_qty * self.fill_eff
            if side == "BUY" and lo <= price:
                out.append(Fill("BUY", price, qty, o))
            elif side == "SELL" and hi >= price:
                out.append(Fill("SELL", price, qty, o))
        return out


class TapeReplayFill:
    """Trade-tape + queue model. trust_class = 'validated'.

    Not active in the OHLC MVP — this is the production fill model. It consumes
    aggregated trades (price, size, aggressor) and periodic L2 snapshots, and
    only fills a resting quote after the depth ahead of it in queue is eaten.
    Wire `tape` (iterable of prints) and `book_depth_fn` (queue-ahead lookup).
    """
    trust_class = "validated"

    def __init__(self, tape=None, book_depth_fn=None):
        self.tape = tape
        self.book_depth_fn = book_depth_fn
        if tape is None:
            raise NotImplementedError(
                "TapeReplayFill needs a live/recorded trade tape + L2 depth. "
                "Run the shadow logger to produce it, then validate against a "
                "ground-truth book before trusting its numbers."
            )

    def fills(self, event, quotes, state) -> List[Fill]:  # pragma: no cover
        raise NotImplementedError
