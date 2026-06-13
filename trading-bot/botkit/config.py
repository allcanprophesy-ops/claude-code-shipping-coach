"""Load and validate config.yaml into a typed, dot-accessible object.

Validation here is intentionally strict-ish: a typo in config.yaml should fail
loudly at startup, not produce a silently wrong backtest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    universe: dict[str, Any]
    strategy: dict[str, Any]
    risk: dict[str, Any]
    costs: dict[str, Any]
    backtest: dict[str, Any]
    data: dict[str, Any]
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    # --- convenience accessors used across the codebase ---
    @property
    def risk_assets(self) -> list[str]:
        return list(self.universe["risk_assets"])

    @property
    def defensive_asset(self) -> str:
        return self.universe["defensive_asset"]

    @property
    def cash_proxy(self) -> str:
        return self.universe["cash_proxy"]

    @property
    def all_tickers(self) -> list[str]:
        """Every ticker we need price data for (deduped, order-stable)."""
        seen: dict[str, None] = {}
        for t in [*self.risk_assets, self.defensive_asset, self.cash_proxy]:
            if t and t.upper() != "CASH":
                seen.setdefault(t, None)
        return list(seen)


def _require(d: dict, key: str, ctx: str):
    if key not in d:
        raise ValueError(f"config: missing '{key}' under [{ctx}]")
    return d[key]


def load_config(path: str | Path = None) -> Config:
    path = Path(path) if path else Path(__file__).resolve().parent.parent / "config.yaml"
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    raw = yaml.safe_load(path.read_text())

    for section in ("universe", "strategy", "risk", "costs", "backtest", "data"):
        _require(raw, section, "root")

    s = raw["strategy"]
    lookbacks = _require(s, "momentum_lookbacks_days", "strategy")
    weights = _require(s, "momentum_weights", "strategy")
    if len(lookbacks) != len(weights):
        raise ValueError(
            "config: strategy.momentum_lookbacks_days and momentum_weights "
            f"must be the same length ({len(lookbacks)} vs {len(weights)})"
        )
    if sum(weights) <= 0:
        raise ValueError("config: strategy.momentum_weights must sum to > 0")
    if s["top_n"] < 1:
        raise ValueError("config: strategy.top_n must be >= 1")
    if s.get("rebalance", "month-end") not in ("month-end", "week-end"):
        raise ValueError("config: strategy.rebalance must be 'month-end' or 'week-end'")

    cfg = Config(
        universe=raw["universe"],
        strategy=raw["strategy"],
        risk=raw["risk"],
        costs=raw["costs"],
        backtest=raw["backtest"],
        data=raw["data"],
        _raw=raw,
    )
    if cfg.strategy["top_n"] > len(cfg.risk_assets):
        raise ValueError(
            f"config: top_n ({cfg.strategy['top_n']}) > number of risk assets "
            f"({len(cfg.risk_assets)})"
        )
    return cfg
