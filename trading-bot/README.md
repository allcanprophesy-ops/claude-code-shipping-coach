# trading-bot — a refinable momentum/trend rotation bot

A small, honest, **iteratively refinable** scaffold for a rules-based trading bot,
built on the best-evidence setup from the research: **dual-momentum sector rotation
with a 200-day regime filter and a drawdown kill-switch.**

It is deliberately *not* a framework. Every layer is a plain, readable module you
can edit in one sitting, and **every tunable lives in `config.yaml`** so your
refinement loop is: edit config → `python run_backtest.py` → compare metrics.

> ⚠️ **Read first.** This is an educational scaffold, not a money printer. The
> research is blunt: >80% of active retail traders lose money, Robinhood has **no
> official equities API** (unofficial wrappers violate its ToS), and "consistent
> monthly growth" is not realistic — drawdowns are structural. Build to learn and
> survive; paper-trade for months; size tiny. See `../` report for the full picture.

---

## Quick start

```bash
cd trading-bot
pip install -r requirements.txt

python run_backtest.py --weights      # backtest + show today's target sleeves
python run_live.py --broker paper     # dry-run a rebalance, zero risk
python tests/test_strategy.py         # sanity checks (run after every edit)
```

No network? It automatically falls back to **deterministic synthetic data** so the
plumbing always runs (clearly labeled — never trade on synthetic results). With
network, it pulls real adjusted-close history via `yfinance` and caches it.

---

## What the strategy does

At each month-end (point-in-time — no look-ahead):
1. **Relative momentum** — rank the sector ETFs by blended trailing return, take the top N.
2. **Absolute momentum** — keep a winner only if it also beats cash (else go defensive).
3. **Regime filter** — keep it only if price > its 200-day SMA.
4. **Risk overlay** — equal-weight, cap per-position, and if portfolio drawdown breaches
   the kill-switch threshold, flatten to defensive until a new equity high is reclaimed.

The exact same `StrategyEngine` + `RiskManager` drive both the backtest and live
order planning — **what you test is what you trade.**

---

## How to refine it (the whole point)

**1. Tune parameters — just edit `config.yaml`:**

| Want to… | Change |
|---|---|
| Hold more/fewer sectors | `strategy.top_n` |
| Use a different momentum horizon | `strategy.momentum_lookbacks_days` / `momentum_weights` |
| Trade less / cut taxes & costs | `strategy.rebalance: month-end` (vs `week-end`) |
| Loosen/tighten the crash filter | `strategy.regime_sma_days`, `use_absolute_momentum` |
| Change the universe | `universe.risk_assets` (any liquid ETFs/stocks) |
| Adjust safety | `risk.max_drawdown_killswitch`, `risk.max_weight_per_position` |
| Stress-test costs | `costs.commission_bps`, `costs.slippage_bps` |

**2. Change the logic — edit one module:**

| File | Responsibility | Refine here to… |
|---|---|---|
| `botkit/strategy.py` | signal → target weights | add a new setup (mean-reversion satellite, vol-targeting) |
| `botkit/indicators.py` | pure indicator math | add RSI-2, ATR sizing, etc. |
| `botkit/risk.py` | sizing, caps, kill-switch | add per-trade stops, Kelly fraction |
| `botkit/backtest.py` | the rebalance simulation | add walk-forward / out-of-sample splits |
| `botkit/execution/` | broker adapters | add an `AlpacaBroker` (recommended for live) |

**Always re-run `tests/test_strategy.py` after a change** — it guards the invariants
(valid weights, **no look-ahead**, kill-switch behavior, dollar-conserving orders).

---

## Going live — read this

- **Robinhood (this session):** the `robinhood-mcp` broker emits a reviewable
  `order_plan.json`. Standalone Python *cannot* place Robinhood orders — by design,
  the agent executes each via `review_equity_order` → `place_equity_order` (MCP),
  human-in-the-loop. Robinhood's only *official* API is crypto.
- **Recommended for real equities automation:** add an **Alpaca** adapter — it has an
  official API and **free, permanent paper trading**. Copy `execution/paper.py`'s shape.
- **Before any real capital:** validate on out-of-sample data, model costs honestly,
  respect settlement (T+1, good-faith violations in cash accounts) and wash-sale rules,
  and keep the kill-switch on.

## Architecture

```
config.yaml ──► config.py ──► [ data.py ] ──► prices
                                  │
              strategy.py ◄───────┤   weights_on(date)  (point-in-time)
                  │               │
              risk.py  (sizing, caps, drawdown kill-switch)
                  │
        ┌─────────┴───────────┐
   backtest.py            execution/  ──► paper | robinhood-mcp | (your Alpaca)
 (metrics + equity)        plan_orders()
```

Known simplifications (honest limits): no intraday fills, partial fills, borrow
costs, taxes, or single-stock survivorship modeling. Results are an upper bound on
reality. That's a feature for a learning scaffold — and a line item on your TODO.
