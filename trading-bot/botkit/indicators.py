"""Pure indicator functions. No state, no I/O — trivial to unit-test and refine.

Everything operates on pandas Series/DataFrames of prices indexed by date.
All functions are POINT-IN-TIME safe: the value at row t uses only data <= t.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def total_return(prices: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    """Trailing simple return over `lookback_days` rows. NaN until enough history."""
    return prices / prices.shift(lookback_days) - 1.0


def blended_momentum(
    prices: pd.DataFrame,
    lookbacks: list[int],
    weights: list[float],
) -> pd.DataFrame:
    """Weighted average of trailing returns over several horizons.

    Blending horizons (Carver's 'parameter diversification') makes the signal
    far less sensitive to any single lookback choice — a key overfitting defense.
    """
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    acc = None
    for lb, w in zip(lookbacks, weights):
        r = total_return(prices, lb) * w
        acc = r if acc is None else acc + r
    return acc


def sma(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    return prices.rolling(window, min_periods=window).mean()


def above_sma(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """Boolean regime filter: is price above its `window`-day SMA?"""
    return prices > sma(prices, window)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average True Range — used for volatility-based sizing/stops (optional).

    When only close prices are available, pass close for all three and you get a
    close-to-close volatility proxy.
    """
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()


def drawdown(equity: pd.Series) -> pd.Series:
    """Drawdown from running peak, as a negative fraction (e.g. -0.18 = -18%)."""
    peak = equity.cummax()
    return equity / peak - 1.0
