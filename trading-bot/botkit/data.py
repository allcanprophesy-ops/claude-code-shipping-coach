"""Price history loader.

Returns a DataFrame of daily ADJUSTED close prices, indexed by date, one column
per ticker. Adjusted close handles splits/dividends so momentum is total-return
based (important — price-only momentum on dividend payers is biased).

Sources, in order of preference:
  1. yfinance (real data) — requires network.
  2. Synthetic fallback — deterministic geometric-Brownian-motion series so the
     backtest ALWAYS runs offline. Clearly labeled; never use for real decisions.

A local CSV cache avoids re-downloading on every run.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _stable_seed(name: str) -> int:
    """Deterministic 32-bit seed from a string. (Builtin hash() is randomized
    per-process via PYTHONHASHSEED, which would make synthetic runs irreproducible.)"""
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16)


def _log(msg: str):
    print(f"[data] {msg}", file=sys.stderr)


def load_prices(
    tickers: list[str],
    start: str,
    end: str | None,
    source: str = "auto",
    cache_dir: str | Path = ".cache",
) -> tuple[pd.DataFrame, str]:
    """Return (prices_df, source_used). source_used in {'yfinance','synthetic','cache'}."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = cache_dir / f"prices_{'-'.join(sorted(tickers))}_{start}_{end}.csv"

    if source in ("auto", "yfinance") and cache_key.exists():
        df = pd.read_csv(cache_key, index_col=0, parse_dates=True)
        if set(tickers).issubset(df.columns):
            _log(f"loaded {len(df)} rows from cache {cache_key.name}")
            return df[tickers].dropna(how="all"), "cache"

    if source in ("auto", "yfinance"):
        try:
            df = _load_yfinance(tickers, start, end)
            if df is not None and not df.empty:
                df.to_csv(cache_key)
                _log(f"downloaded {len(df)} rows via yfinance for {len(tickers)} tickers")
                return df, "yfinance"
            _log("yfinance returned no data")
        except Exception as e:  # noqa: BLE001 - we intentionally fall back on any failure
            _log(f"yfinance unavailable ({type(e).__name__}: {e}); falling back to synthetic")
        if source == "yfinance":
            raise RuntimeError("yfinance requested but unavailable and no usable cache")

    df = _synthetic_prices(tickers, start, end)
    _log(
        f"USING SYNTHETIC DATA ({len(df)} rows) — for plumbing/demo only, "
        "NOT real backtest results."
    )
    return df, "synthetic"


def _load_yfinance(tickers: list[str], start: str, end: str) -> pd.DataFrame | None:
    import yfinance as yf

    raw = yf.download(
        tickers, start=start, end=end, auto_adjust=True, progress=False, threads=True
    )
    if raw is None or len(raw) == 0:
        return None
    # yfinance returns a column MultiIndex (field, ticker) for multi-ticker pulls.
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    else:  # single ticker
        close = raw[["Close"]]
        close.columns = tickers
    close = close.reindex(columns=tickers)
    return close.dropna(how="all")


def _synthetic_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Deterministic GBM price paths. Same tickers -> same series (seeded by name)
    so runs are reproducible and tests are stable. Gives each ticker a distinct
    drift/vol so momentum ranking has something to chew on."""
    dates = pd.bdate_range(start=start, end=end)
    out = {}
    for t in tickers:
        seed = _stable_seed(t)
        rng = np.random.default_rng(seed)
        # Spread drift across tickers so the ranking is non-degenerate.
        ann_drift = 0.02 + (seed % 1000) / 1000 * 0.16   # ~2%..18% annual
        ann_vol = 0.10 + (seed % 777) / 777 * 0.22        # ~10%..32% annual
        # Defensive/cash-like tickers get near-zero vol.
        if t in ("BIL", "SHV", "SGOV"):
            ann_drift, ann_vol = 0.02, 0.005
        dt = 1 / 252
        shocks = rng.normal(
            (ann_drift - 0.5 * ann_vol**2) * dt,
            ann_vol * np.sqrt(dt),
            size=len(dates),
        )
        out[t] = 100 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(out, index=dates)
