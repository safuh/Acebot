# Acebot — Project Description

## Overview

Acebot is a modular cryptocurrency market-structure and divergence-monitoring application. It processes exchange OHLCV data chronologically to reconstruct daily liquidity structure and identify hidden RSI divergence events, then presents those events alongside price and RSI charts.

The initial target is Binance Spot `BTC/USDT`, using one-hour candles and RSI(14). The design should remain configurable for other symbols, timeframes, and exchanges.

## Problem

Historical intraday analysis can introduce look-ahead bias when an earlier candle is evaluated using the final high or low of its day. Acebot addresses this by replaying closed candles in order and maintaining the running daily high/low as each candle becomes available.

The same stateful processing path is intended for historical replay and subsequent live updates.

## Core capabilities

- Historical and recent OHLCV retrieval through CCXT.
- RSI and intraday feature calculation.
- Stateful daily running highs and lows.
- Completed daily liquidity reference levels.
- Hidden bearish and hidden bullish divergence detection.
- Configurable RSI association window around the price-extreme candle.
- Historical event retention and later invalidation after reference-level sweeps.
- Interactive price and RSI visualization.
- Incremental live polling without duplicate candle processing.

## Design principles

**Chronological correctness:** A signal may use only information available at its confirmation time.

**Modularity:** Exchange access, features, market structure, visualization, and orchestration remain separate responsibilities.

**Determinism:** Identical ordered candle input and configuration should produce identical engine output.

**Configurability:** Market, timeframe, RSI period, RSI window radius, and polling interval are centralized.

**Incremental operation:** New closed candles are processed once; the entire history should not be recalculated on every poll.

**Observability:** Events should retain timestamps, reference/current values, direction, and lifecycle status.

## Intended use

Acebot is intended for a developer or market analyst who wants to inspect historical and developing daily structure, review divergence events, and monitor newly confirmed events as candles close.

Automated order execution, portfolio management, and claims of strategy profitability are not current requirements.

## Current boundary

The stateful `MarketStructureEngine` has been written to support chronological replay and live updates. Integration of the wider application, comprehensive tests, persistence, and deployment still need verification. A planned module or dependency is not proof that its feature is complete.

## Expected outcome

A reliable local monitoring application that loads historical candles, reconstructs daily structure without look-ahead, displays historical divergence on price and RSI charts, and continues updating as new candles close.
