# Acebot — Project Milestone Tracker

**Baseline date:** 2 November 2026

Statuses are conservative. A feature is not complete merely because it has been discussed or planned.

## Status key

- `[x]` Implemented and verified in the current development context.
- `[~]` Partially implemented, or implementation exists but broader integration/testing is pending.
- `[ ]` Not yet verified as implemented.

## Overview

| ID | Milestone | Status |
|---|---|---|
| M0 | Project foundation and configuration | `[~]` |
| M1 | Exchange data layer | `[~]` |
| M2 | Feature calculation | `[~]` |
| M3 | Stateful market-structure engine | `[~]` |
| M4 | Historical replay and live continuation | `[ ]` |
| M5 | Historical divergence visualization | `[ ]` |
| M6 | Dashboard and polling reliability | `[ ]` |
| M7 | Persistence and recovery | `[ ]` |
| M8 | Quality, performance and operational hardening | `[ ]` |
| M9 | Research and evaluation | `[ ]` |
| M10 | Optional deployment | `[ ]` |

## M0 — Foundation and configuration `[~]`

- [ ] Confirm repository tree and default branch.
- [ ] Verify dependencies and supported Python version.
- [ ] Centralize exchange, symbol, timeframe, RSI, polling, and dashboard settings.
- [ ] Document Kali Linux virtual-environment setup.
- [ ] Add `.gitignore` entries for virtual environments, caches, logs, local databases, and secrets.

**Exit criteria:** Clean environment installs dependencies and imports all application modules.

## M1 — Exchange data layer `[~]`

- [ ] Verify CCXT Spot configuration.
- [ ] Verify timeframe-to-milliseconds conversion.
- [ ] Fetch historical OHLCV with pagination/limits handled.
- [ ] Refresh latest candles without duplicate rows.
- [ ] Normalize timestamps to UTC.
- [ ] Exclude the still-forming candle from engine processing.
- [ ] Handle rate limits, network errors, downtime, and missing candles.
- [ ] Test ordering, duplicate timestamps, and OHLC validity.

**Exit criteria:** Historical fetch and incremental refresh produce clean chronological data.

## M2 — Feature calculation `[~]`

- [ ] Verify RSI(14) and warm-up behavior.
- [ ] Compare RSI with a trusted reference calculation.
- [ ] Preserve index/time alignment.
- [ ] Ensure live refresh does not unexpectedly change prior RSI values.
- [ ] Document minimum RSI warm-up history.

**Exit criteria:** Batch and live feature values agree for identical candle history.

## M3 — Stateful market-structure engine `[~]`

- [x] Implement `MarketStructureEngine` and public query/update methods.
- [x] Initialize daily state on the first valid candle.
- [x] Track running daily high/low.
- [x] Track pending price-extreme RSI candidates.
- [x] Confirm candidates after subsequent bars close.
- [x] Clip RSI windows at day finalization.
- [x] Store completed daily liquidity levels.
- [x] Track strict high/low liquidity sweeps.
- [x] Retain events and mark later-invalidated events.
- [ ] Add comprehensive deterministic unit tests.
- [ ] Verify edge cases against independently specified expected outcomes.

**Exit criteria:** Tests prove divergence, RSI-window, sweep, and lifecycle rules.

## M4 — Historical replay and live continuation `[ ]`

- [ ] Load enough candles for RSI warm-up and chart history.
- [ ] Calculate features over stable history.
- [ ] Exclude the unfinished candle.
- [ ] Replay closed candles chronologically through one engine instance.
- [ ] Track last committed candle timestamp.
- [ ] Process only newly closed candles on each poll.
- [ ] Handle multiple candles arriving between polls.
- [ ] Compare replay-then-stream output with uninterrupted replay.

**Exit criteria:** No duplicate events or state drift when switching from replay to live updates.

## M5 — Historical divergence visualization `[ ]`

- [ ] Inspect and preserve existing `visualization.py` layout.
- [ ] Plot all historical events, not only the latest day.
- [ ] Draw divergence markers/lines on price panel.
- [ ] Draw corresponding lines/markers on RSI panel.
- [ ] Distinguish bullish and bearish events.
- [ ] Add hover details for timestamps, reference/current values, and status.
- [ ] Visually distinguish invalidated events.
- [ ] Verify price and RSI timestamps align.

**Exit criteria:** Historical events can be inspected consistently on both panels.

## M6 — Dashboard and polling reliability `[ ]`

- [ ] Inspect `main.py` and current Dash callbacks.
- [ ] Integrate replay and live updates without duplicate processing.
- [ ] Avoid reinitializing the engine during chart refresh.
- [ ] Handle transient fetch failures without corrupting engine state.
- [ ] Add structured logs for fetches, processed candles, events, and errors.
- [ ] Verify graceful shutdown and exchange cleanup.

**Exit criteria:** Dashboard runs continuously and recovers from transient fetch failures.

## M7 — Persistence and recovery `[ ]`

- [ ] Select persistence format; SQLite is a reasonable initial option.
- [ ] Persist processed timestamp, engine state, events, daily levels, and sweeps.
- [ ] Define schema versioning/migrations.
- [ ] Restore state or deterministically rebuild it from stored candles.
- [ ] Test restart and duplicate prevention.

**Exit criteria:** Restart does not lose or duplicate confirmed events.

## M8 — Quality and operational hardening `[ ]`

- [ ] Unit tests for engine rules.
- [ ] Mocked exchange adapter tests.
- [ ] Integration/smoke tests for replay, charts, and dashboard.
- [ ] Actionable logging and errors.
- [ ] Measure memory and processing time over long histories.
- [ ] Handle missing intervals and exchange data corrections.
- [ ] Document configuration and troubleshooting.

**Exit criteria:** Repeatable test and operational checklist passes.

## M9 — Research and evaluation `[ ]`

- [ ] Define signal event and confirmation time precisely.
- [ ] Build a no-look-ahead historical evaluation harness.
- [ ] Measure signal frequency by direction and market regime.
- [ ] Evaluate forward returns over defined horizons.
- [ ] Include fees/slippage only for explicit strategy evaluation.
- [ ] Avoid tuning on the final evaluation period.
- [ ] Report sample size, uncertainty, and limitations.

**Exit criteria:** Reproducible descriptive evaluation exists; no profitability claims without robust evidence.

## M10 — Optional deployment `[ ]`

- [ ] Decide whether local monitoring is sufficient.
- [ ] Add environment-based deployment configuration.
- [ ] Keep secrets outside source control.
- [ ] Add process supervision/restart policy if needed.
- [ ] Add health checks and operational logs.
- [ ] Document deployment and rollback.

**Exit criteria:** Deployment is reproducible and maintainable.

## Immediate next actions

1. Inspect actual `main.py`, `visualization.py`, `features.py`, `exchange.py`, and `config.py`.
2. Add focused tests for `MarketStructureEngine`.
3. Integrate chronological historical replay and incremental closed-candle updates.
4. Plot historical divergence on price and RSI charts while preserving existing chart design.

## Decision log

| Date | Decision |
|---|---|
| 2026-11-02 | One stateful engine handles historical replay and live updates. |
| 2026-11-02 | Daily market-structure boundaries use UTC calendar days. |
| 2026-11-02 | Default RSI association radius is two candles either side of the price-extreme candle. |
| 2026-11-02 | Candidates confirm after subsequent candles close; day-end windows are clipped. |
| 2026-11-02 | Bearish current high must exceed all intervening highs; bullish current low must undercut all intervening lows. |
| 2026-11-02 | Retain events after later reference sweeps and mark them invalidated. |
| 2026-11-02 | Keep implementation synchronous unless explicitly changed for a demonstrated need. |
