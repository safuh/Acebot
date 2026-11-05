# Acebot — Market Structure & Divergence Monitor

Acebot is a modular Python cryptocurrency market-analysis application for monitoring daily market structure, liquidity levels, and hidden RSI divergences from intraday OHLCV data.

**Initial baseline:** Binance Spot, `ETH/USDT`, 1-hour candles, RSI(14), UTC daily boundaries.

> **Status:** The stateful market-structure engine has been implemented as a first development pass. End-to-end integration, comprehensive automated tests, persistence, and deployment still need to be completed. This is an analysis/monitoring project, not a production trading system.

## Goals

- Retrieve OHLCV data through CCXT.
- Calculate RSI and intraday features.
- Replay closed candles chronologically through a non-repainting swing engine.
- Derive each UTC day's high/low only from confirmed intraday swing highs/lows; a side with no confirmed swing remains unavailable rather than falling back to raw candle extremes.
- Track completed swing-derived daily extremes as liquidity reference levels.
- Drop leading history until the first complete UTC day, validating expected candle timestamps and continuity.
- Detect hidden bearish and hidden bullish RSI divergence.
- Retain historical events and mark them invalidated if their reference liquidity is swept later.
- Plot historical divergence on both price and RSI charts.
- Continue from historical replay into live updates without processing candles twice.

## Signal rules

### Hidden bearish
A candidate requires an unswept previous completed daily swing high, a lower current swing high, a higher associated RSI high, and a current daily swing high greater than **all intervening available daily swing highs**.

### Hidden bullish
A candidate requires an unswept previous completed daily swing low, a higher current swing low, a lower associated RSI low, and a current daily swing low lower than **all intervening available daily swing lows**.

The strict intervening-extreme conditions are intentional project requirements. Do not reinterpret them as a generic “no intervening level swept” rule.

### Swing and RSI association
Daily extremes are selected from confirmed intraday swing pivots. Swing pivots use strict left/right comparisons (default two bars on each side), and their complete pivot window must be contiguous and remain within one UTC day. Divergence is evaluated only when the day is finalized, so a later higher/lower confirmed swing can replace an earlier candidate.

The RSI value is selected from a configurable symmetric window around the actual swing-pivot candle:
- High: maximum RSI in the window.
- Low: minimum RSI in the window.
- Default radius: two candles on either side.
- The pivot is not available until its right-hand confirmation candles have closed.
- At day end, the RSI window is clipped to that day.
- The selected daily high/low is the highest/lowest confirmed swing of that day.

### Reference window
Only completed reference days **2 through 21 calendar days** before the current day are eligible. The immediately preceding day is deliberately excluded; days older than 21 are ignored.

Only closed candles are committed to the engine. The latest day remains developing until a candle from the next UTC day triggers finalization.

## Intended architecture

```text
Acebot/
├── main.py                 # Application orchestration and polling
├── config.py               # Centralized settings
├── exchange.py             # CCXT initialization and OHLCV access
├── features.py              # RSI and intraday features
├── swing_structure.py      # Non-repainting intraday swings, BOS/CHoCH, sweeps
├── market_structure.py     # Swing-derived daily structure and divergence engine
├── visualization.py        # Plotly price/RSI charts
├── tests/                   # Automated tests
├── requirements.txt
└── README.md
```

This is the intended module layout, not a claim that every module is currently complete. Inspect the repository before changing its structure.

## Data flow

```text
CCXT exchange -> OHLCV -> RSI/features -> closed-candle replay
    -> MarketStructureEngine -> daily levels + divergence events
    -> price/RSI visualization -> dashboard/live polling
```

Historical replay and live processing must use the same engine instance and `update()` path.

## Technology

- Python 3
- CCXT
- pandas
- NumPy
- Plotly
- Dash

## Configuration baseline

| Setting | Baseline |
|---|---|
| Exchange | `binance` |
| Symbol | `BTC/USDT` |
| Market type | Spot |
| Timeframe | `1h` |
| RSI period | `14` |
| RSI window radius | `2` candles |
| Poll interval | `10` seconds |
| Daily timezone | UTC |
| Dashboard host | `127.0.0.1` |
| Dashboard port | `8050` |

Keep settings centralized in `config.py`.

## Installation

On Kali Linux, use a virtual environment; do not install packages into the externally managed system Python.

```bash
git clone <repository-url>
cd Acebot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Running

The intended entry point is `main.py`:

```bash
source .venv/bin/activate
python main.py
```

Confirm the actual startup behavior against the current `main.py`; dashboard integration must not be assumed.

## Engine API

```python
from market_structure import MarketStructureEngine

engine = MarketStructureEngine(
    rsi_window_bars=2,
    timeframe_ms=3_600_000,
)

new_events = engine.update(timestamp, candle)
events = engine.get_divergences(include_invalidated=True)
active_events = engine.get_divergences(include_invalidated=False)
daily = engine.get_daily_structure()
current_day = engine.get_current_day()
levels = engine.get_liquidity_levels()
```

Each candle must contain `high`, `low`, `close`, and `rsi`. The timestamp is the candle opening timestamp. Naive timestamps are interpreted as UTC; aware timestamps are converted to UTC. Duplicate timestamps are ignored; older timestamps raise `ValueError`.

## Engineering constraints

1. No look-ahead: evaluate only information available at the time.
2. Commit closed candles only.
3. Preserve enough RSI history; truncating EWM input can change values.
4. Replay and live updates share one chronological processing path.
5. Never process the same candle twice.
6. Normalize timestamps consistently to UTC.
7. Preserve the specified divergence and intervening-extreme rules.
8. Do not add order execution unless explicitly requested and separately designed.

## Testing priorities

Test first-candle initialization, UTC handling, duplicate/out-of-order timestamps, day finalization, running extremes, RSI confirmation and clipping, both divergence directions, unswept references, intervening-extreme rules, sweep invalidation, event retention, and replay-to-live continuation.

## Limitations

Exchange data may be delayed, incomplete, revised, or unavailable. The first retained UTC day is validated as complete; subsequent data gaps can still affect swing confirmation. Candle-close polling does not capture every intrabar movement. Technical-analysis events are not guaranteed trading signals or financial advice. Validate calculations and data quality before relying on outputs.

## Documentation

- [Project description](PROJECT_DESCRIPTION.md)
- [AI assistant instructions](AI_ASSISTANT_INSTRUCTIONS.md)
- [Milestone tracker](MILESTONE_TRACKER.md)
