# Acebot — Project Description

## Overview

Acebot is a modular cryptocurrency market-structure and divergence-monitoring application. It processes exchange OHLCV data chronologically to reconstruct daily liquidity structure and identify hidden RSI divergence events, then presents those events alongside price and RSI charts.

The initial target is Binance Spot `BTC/USDT`, using one-hour candles and RSI(14). The design should remain configurable for other symbols, timeframes, and exchanges.

## Problem

Historical intraday analysis can introduce look-ahead bias when an earlier candle is evaluated using a final daily extreme before that extreme was confirmed. Acebot addresses this by replaying closed candles in order, confirming intraday swing pivots only after their right-hand bars close, and deriving each day's high/low from its confirmed swings. Swing windows cannot cross UTC midnight or candle-data gaps.

The first retained day must be a complete UTC day. The same swing and market-structure processing path is used for historical replay and subsequent live updates.

## Core capabilities

- Historical and recent OHLCV retrieval through CCXT.
- RSI and intraday feature calculation.
- Non-repainting intraday swing highs/lows with configurable left/right confirmation windows.
- Daily high/low structure derived only from confirmed swing pivots.
- Completed daily swing-liquidity reference levels.
- Leading partial-day removal using exact expected UTC candle timestamps.
- Hidden bearish and hidden bullish divergence detection.
- Configurable RSI association window around the actual swing-pivot candle.
- Divergence reference window of 2–21 calendar days; the immediately preceding day and references older than 21 days are excluded.
- Historical event retention and later invalidation after reference-level sweeps.
- Interactive price and RSI visualization.
- Incremental live polling without duplicate candle processing.

## Design principles

**Chronological correctness:** A signal may use only information available at its confirmation time.

**Modularity:** Exchange access, features, market structure, visualization, and orchestration remain separate responsibilities.

**Determinism:** Identical ordered candle input and configuration should produce identical engine output.

**Configurability:** Market, timeframe, RSI period, RSI window radius, and polling interval are centralized.

**Incremental operation:** New closed candles are processed once by both engines; the entire history should not be replayed on every poll.

**Observability:** Events should retain timestamps, reference/current values, direction, and lifecycle status.

## Intended use

Acebot is intended for a developer or market analyst who wants to inspect historical and developing daily structure, review divergence events, and monitor newly confirmed events as candles close.

Automated order execution, portfolio management, and claims of strategy profitability are not current requirements.

## Current boundary

The stateful `MarketStructureEngine` has been written to support chronological replay and live updates. Integration of the wider application, comprehensive tests, persistence, and deployment still need verification. A planned module or dependency is not proof that its feature is complete.

## Expected outcome

A reliable local monitoring application that loads historical candles, reconstructs daily structure without look-ahead, displays historical divergence on price and RSI charts, and continues updating as new candles close.
