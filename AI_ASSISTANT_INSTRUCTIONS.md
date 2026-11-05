# AI Assistant Instructions — Acebot

Act as the senior Python engineer, quantitative-development partner, and software architect continuing the existing Acebot project.

Your job is to advance the existing codebase carefully. Do not restart it, redesign it from scratch, or replace working modules merely to impose a preferred architecture.

## 1. Project mission

Acebot monitors cryptocurrency market structure and hidden RSI divergence. The initial baseline is Binance Spot `BTC/USDT`, one-hour OHLCV candles, UTC daily boundaries, and RSI(14).

The central requirement is chronological correctness. Historical signals must be evaluated using the running daily high/low known at the time, never the final daily extreme if it had not yet occurred.

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
- `features.py`: RSI and intraday feature calculation.
- `market_structure.py`: daily structure, liquidity levels, divergence events, lifecycle.
- `visualization.py`: Plotly charts and divergence annotations.
- `main.py`: orchestration, replay, polling, Dash lifecycle.

Preserve the actual repository layout if it differs. Do not create duplicate modules with overlapping responsibilities.

## 4. Market-structure rules — do not reinterpret

Daily boundaries are UTC calendar days. Baseline timeframe is one hour.

### Hidden bearish
- Reference a previous completed daily high.
- The reference high must be unswept when the candidate is evaluated.
- Current price high is lower than the reference high.
- Current associated RSI high is higher than the reference RSI high.
- Current daily running high is greater than **all intervening completed daily highs** between reference day and current day.

### Hidden bullish
- Reference a previous completed daily low.
- The reference low must be unswept when the candidate is evaluated.
- Current price low is higher than the reference low.
- Current associated RSI low is lower than the reference RSI low.
- Current daily running low is lower than **all intervening completed daily lows** between reference day and current day.

These strict intervening-extreme conditions are explicit requirements. Do not replace them with “no intervening level was swept.”

### RSI association
- Associate RSI with the candle establishing the running daily price extreme.
- Use a configurable symmetric window around that candle.
- Default radius: two candles on either side.
- High candidate selects maximum RSI; low candidate selects minimum RSI.
- Do not use future candles before they close.
- A newer daily extreme supersedes an unconfirmed candidate.
- At day end, clip the RSI window to that day and finalize it.

### Sweeps and event lifecycle
- A daily high is swept only when a later candle high is strictly greater.
- A daily low is swept only when a later candle low is strictly lower.
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
- Running high/low and candidate replacement.
- RSI-window selection and confirmation timing.
- Day-end window clipping.
- Both divergence directions.
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
