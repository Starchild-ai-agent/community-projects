"""Configuration objects for the quote simulator.

Everything a user can tune lives here. Two configs:
  AssetConfig    — what you're quoting (symbol, oracle, tick/lot, fees)
  StrategyConfig — how you quote it (ladder, band, inventory risk)

Both build from a plain dict (or YAML), so the product surface is just a form.
"""
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class AssetConfig:
    symbol: str                       # display id, e.g. "PERP_VVV_USDC"
    # oracle sources are informational for the engine (the fill model supplies
    # the actual price path); kept so the product can render/validate them.
    oracle_sources: List[str] = field(default_factory=lambda: ["index"])
    oracle_weights: List[float] = field(default_factory=lambda: [1.0])
    tick_size: float = 0.0001
    lot_size: float = 1.0
    maker_fee_bps: float = -0.5       # negative = rebate earned
    taker_fee_bps: float = 2.0

    @classmethod
    def from_dict(cls, d: dict) -> "AssetConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})


@dataclass
class StrategyConfig:
    side_notional_usd: float = 30000.0   # total $ resting per side
    n_levels: int = 10                   # ladder depth per side
    min_bps: float = 5.0                 # tightest level offset from oracle
    band_bps: float = 200.0              # widest level (== ±band of mid)
    # inventory risk: when |inv_usd| crosses a cap, the ADDING side is pushed
    # out of reach (close side stays live = depth obligation honored).
    inv_soft_usd: float = 2000.0
    inv_hard_usd: float = 6000.0
    inv_panic_usd: float = 10000.0
    # close_skew: once |inv| exceeds this (lots), fatten/repel the adding leg.
    close_skew_lots: float = 1000.0
    close_skew_mult: float = 1.31        # widen adding-leg offset by this
    # soft-reset: adverse drift on avg cost beyond this tightens the lagging leg
    soft_reset_bps: float = 150.0

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})


def default_config() -> dict:
    """A starting template a user can edit in the product UI."""
    return {
        "asset": asdict(AssetConfig(symbol="PERP_ASSET_USDC")),
        "strategy": asdict(StrategyConfig()),
    }
