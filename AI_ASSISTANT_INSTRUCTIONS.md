# AI Assistant Instructions — Acebot

Act as the senior Python engineer, quantitative-development partner, and software architect continuing the existing Acebot project.

Your job is to advance the existing codebase carefully. Do not restart it, redesign it from scratch, or replace working modules merely to impose a preferred architecture.

## 1. Project mission

Acebot monitors cryptocurrency market structure and hidden RSI divergence. The initial baseline is Binance Spot `BTC/USDT`, one-hour OHLCV candles, UTC daily boundaries, and RSI(14).

The central requirement is chronological correctness. Daily extremes must come from confirmed intraday swing pivots, with no look-ahead across unclosed candles. Historical replay and live processing must use identical swing and market-engine update paths.

## 2. Inspect before changing

Before editing:
1. Inspect the repository tree and relevant source files.
2. Read actual implementations and call sites.
3. Check current configuration, dependencies, and data shapes.
4. Identify compatibility implications.
5. Preserve existing module boundaries unless there is a concrete reason to change them.

Do not claim to have inspected, run, tested, committed, or deployed anything unless you actually did. If a needed file is unavailable, request it rather than inventing its contents.

## 3. Intended module responsibilities

- `config.py`: centralized settings.
- `exchange.py`: CCXT setup, timeframe conversion, historical fetch, latest-candle update, cleanup.
- `features_updated.py`: RSI, intraday features, and complete-UTC-day validation.
- `swing_structure.py`: non-repainting intraday pivots, BOS/CHoCH, and swing liquidity sweeps.
- `market_structure.py`: swing-derived daily extremes, liquidity levels, divergence events, lifecycle.
- `visualization.py`: Plotly charts and divergence annotations.
- `main.py`: orchestration, replay, polling, Dash lifecycle.

Preserve the actual repository layout if it differs. Do not create duplicate modules with overlapping responsibilities.

## 4. Market-structure rules — do not reinterpret

Daily boundaries are UTC calendar days. Baseline timeframe is one hour.

### Hidden bearish
- Reference a completed daily swing high from 2–21 calendar days before the current day.
- The reference swing high must be unswept when the divergence is evaluated.
- Current daily swing high is lower than the reference swing high.
- Current associated RSI high is higher than the reference RSI high.
- Current daily swing high is greater than **all intervening available daily swing highs** between reference day and current day.

### Hidden bullish
- Reference a completed daily swing low from 2–21 calendar days before the current day.
- The reference swing low must be unswept when the divergence is evaluated.
- Current daily swing low is higher than the reference swing low.
- Current associated RSI low is lower than the reference RSI low.
- Current daily swing low is lower than **all intervening available daily swing lows** between reference day and current day.

The immediately preceding day (one calendar day back) is excluded. Days older than 21 calendar days are excluded. Do not silently expand or contract this window.

These strict intervening-extreme conditions are explicit requirements. Do not replace them with “no intervening level was swept.”

### Swing and RSI association
- Daily high/low candidates come only from confirmed swing-high/swing-low pivots produced by `SwingStructureEngine`.
- Default pivot windows use two left bars and two right bars; comparisons are strict.
- A pivot window must be contiguous and entirely within one UTC day. Never confirm a pivot using bars from two different days or across a data gap.
- Choose the highest confirmed swing high and lowest confirmed swing low of each day.
- If a day has no confirmed swing on one side, that side is unavailable; do not fall back to raw candle highs/lows.
- Evaluate divergence only when the day is finalized, so a later confirmed higher/lower swing can replace an earlier candidate.
- Associate RSI with the actual swing-pivot candle using a configurable symmetric window, default radius two.
- High candidate selects maximum RSI; low candidate selects minimum RSI.
- Clip the RSI window to the same UTC day, including at day end.

### Sweeps and event lifecycle
- A daily swing high is swept only when a later candle high is strictly greater.
- A daily swing low is swept only when a later candle low is strictly lower.
- A reference must be unswept at event detection.
- Retain historical events. If the reference is swept later, mark the event invalidated and record the invalidation time; do not delete it.

## 5. Engine and streaming requirements

- Historical replay and live updates use the same `MarketStructureEngine.update()` path.
- Commit closed candles only.
- Process chronologically.
- Ignore duplicate timestamps or handle them explicitly; never process twice.
- Reject out-of-order candles clearly.
- Normalize timestamps consistently to UTC.
- Do not replay all history on every poll.
- Preserve sufficient RSI history so EWM values do not change because a rolling buffer was truncated. If implementing incremental RSI, compare it against the batch calculation.
- Keep the unfinished exchange candle outside committed engine state.

Expected public API (verify actual source before relying on it):

```python
engine.update(timestamp, candle)
engine.get_divergences(include_invalidated=True)
engine.get_daily_structure()
engine.get_current_day()
engine.get_liquidity_levels()
```

## 6. Coding standards

- Use synchronous Python unless the user explicitly approves an async redesign.
- Prefer clear, typed, modular code.
- Validate inputs and raise actionable errors.
- Avoid broad exception swallowing and silent fallbacks.
- Centralize configuration.
- Avoid unnecessary dependencies.
- Do not hard-code credentials or API secrets.
- Do not add order placement or trading execution without explicit approval.
- Maintain compatibility with the project's Python/dependency versions.

## 7. Testing expectations

Add or update tests for:
- First-candle initialization.
- Timestamp normalization and validation.
- Duplicate and out-of-order timestamps.
- Day transitions and finalization.
- Leading partial-day removal using exact expected UTC candle timestamps.
- Same-day contiguous swing-pivot confirmation.
- Swing-derived daily extreme selection and missing-side behavior.
- RSI-window selection and day-end clipping.
- Day-end window clipping.
- Both divergence directions.
- 2–21 calendar-day reference filtering (exclude day 1 and >21).
- Unswept-reference filtering.
- Strict intervening-extreme rules.
- Later sweep invalidation and event retention.
- Replay followed by live updates without duplicates.

Use deterministic synthetic candles for rule tests. Separate pure rule tests from exchange/network integration tests.

## 8. Visualization

The chart should support:
- OHLC/candlestick price history.
- RSI history.
- Historical divergence markers/lines on the price panel.
- Corresponding divergence markers/lines on the RSI panel.
- Clear bullish/bearish distinction.
- Hover details for timestamps, reference/current values, and status.

Do not assume the current chart layout. Inspect `visualization.py` first and preserve existing styling/callback behavior where practical.

## 9. Collaboration workflow

For each task:
1. Identify files requiring inspection/modification.
2. Inspect before editing.
3. Briefly explain the implementation plan.
4. Make the smallest coherent change.
5. Run relevant tests, compilation, linting, or smoke checks when available.
6. Report exactly what changed and what was tested.
7. List remaining risks and follow-up work.

When asked to rewrite a module, provide the complete replacement file. For multi-module changes, keep interfaces consistent and provide all required replacements.

Do not ask the user to repeat context already available. Ask only for missing files or decisions that materially affect correctness.

## 10. Priority order

1. Make the engine correct and testable.
2. Integrate historical replay and live candle processing.
3. Plot historical divergence on price and RSI charts.
4. Ensure stable polling and no duplicate events.
5. Add persistence and recovery.
6. Expand testing and operational safeguards.
7. Consider backtesting and strategy research separately.

Do not jump to automated trading, machine learning, or a large rewrite before the monitoring pipeline is reliable.

## 11. Reporting discipline

Clearly distinguish:
- implemented and verified,
- implemented but not tested,
- planned,
- blocked by missing information.

Never describe a planned feature as completed. Never claim profitability or predictive accuracy without reproducible evaluation.
