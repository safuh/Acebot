import ccxt
import pandas as pd
from dash import Dash, dcc, html
from dash.dependencies import Input, Output

from config import (
    SYMBOL,
    TIMEFRAME,
    N,
    POLL_INTERVAL,
    RSI_PERIOD,
    SWING_LEFT_BARS,
    SWING_RIGHT_BARS,
    RSI_WINDOW_BARS,
    MIN_DIVERGENCE_LOOKBACK_DAYS,
    MAX_DIVERGENCE_LOOKBACK_DAYS,
)
from exchange import (
    fetch_initial_history,
    update_latest_candle,
    get_timeframe_ms,
)
from features_updated import add_intraday_features, drop_leading_partial_day
from market_structure import MarketStructureEngine
from swing_structure import SwingStructureEngine
from visualization import build_market_figure_with_divergence


def get_closed_candles(frame: pd.DataFrame, timeframe_ms: int) -> pd.DataFrame:
    """Return candles whose full timeframe has elapsed, using UTC wall time."""
    if frame.empty:
        return frame

    now = pd.Timestamp.now(tz="UTC")
    index = pd.DatetimeIndex(frame.index)
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")

    candle_close_times = index + pd.to_timedelta(timeframe_ms, unit="ms")
    return frame.loc[candle_close_times <= now]


print("Connecting to exchange...")
print("Loading historical candles...")

timeframe_ms = int(get_timeframe_ms())

# Calculate RSI before removing the leading partial day so its indicator
# warm-up uses all fetched candles. Replay/chart data then begins at a
# verified complete UTC day.
df = fetch_initial_history().tail(N)
df = add_intraday_features(df, rsi_period=RSI_PERIOD)
df = drop_leading_partial_day(df, timeframe_ms)

swing_engine = SwingStructureEngine(
    left_bars=SWING_LEFT_BARS,
    right_bars=SWING_RIGHT_BARS,
    timeframe_ms=timeframe_ms,
)
engine = MarketStructureEngine(
    rsi_window_bars=RSI_WINDOW_BARS,
    timeframe_ms=timeframe_ms,
    min_reference_days=MIN_DIVERGENCE_LOOKBACK_DAYS,
    max_reference_days=MAX_DIVERGENCE_LOOKBACK_DAYS,
)

# Replay historical candles through both engines in the same chronological
# order. A swing is forwarded only when its right-hand confirmation bars
# have closed; the market engine associates it with its actual pivot candle.
closed_df = get_closed_candles(df, timeframe_ms)
if closed_df.empty:
    raise RuntimeError(
        "No closed historical candles were selected. Check exchange timestamps "
        "and get_timeframe_ms()."
    )

for timestamp, candle in closed_df.iterrows():
    swing_events = swing_engine.update(timestamp, candle)
    engine.update(timestamp, candle, confirmed_swings=swing_events)

events = engine.get_divergences()
swing_snapshot = swing_engine.get_snapshot()
print(f"Historical candles replayed: {len(closed_df)}")
print(f"Confirmed swing points: {len(swing_snapshot['swings'])}")
print(f"Historical divergence events: {len(events)}")

for event in events:
    print(
        event["direction"],
        event["reference_day"],
        event["current_day"],
        event["detected_at"],
        event["status"],
    )

state = {
    "df": df,
    "engine": engine,
    "swing_engine": swing_engine,
    "events": events,
}

app = Dash(__name__)

app.layout = html.Div(
    [
        html.H2(f"{SYMBOL} Market Monitor"),
        html.Div(id="market-status", children="Connecting..."),
        dcc.Graph(
            id="market-chart",
            figure=build_market_figure_with_divergence(
                df,
                events,
                SYMBOL,
                TIMEFRAME,
                daily=engine.get_daily_structure(),
                swings=swing_snapshot,
            ),
            config={
                "scrollZoom": True,
                "displaylogo": False,
                "responsive": True,
            },
            style={"height": "90vh"},
        ),
        dcc.Interval(
            id="refresh-interval",
            interval=POLL_INTERVAL * 1000,
            n_intervals=0,
        ),
    ],
    style={"padding": "15px"},
)


@app.callback(
    Output("market-chart", "figure"),
    Output("market-status", "children"),
    Input("refresh-interval", "n_intervals"),
)
def refresh_market_chart(_n):
    try:
        updated = update_latest_candle(state["df"]).tail(N)
        updated = add_intraday_features(updated, rsi_period=RSI_PERIOD)
        # Keep the visible rolling frame aligned to a complete UTC day.
        # The stateful engines remain independent of this chart-window trim.
        updated = drop_leading_partial_day(updated, timeframe_ms)

        closed_df = get_closed_candles(updated, timeframe_ms)
        engine = state["engine"]
        swing_engine = state["swing_engine"]

        if engine.last_timestamp is None:
            new_candles = closed_df
        else:
            new_candles = closed_df.loc[closed_df.index > engine.last_timestamp]

        for timestamp, candle in new_candles.iterrows():
            swing_events = swing_engine.update(timestamp, candle)
            engine.update(timestamp, candle, confirmed_swings=swing_events)

        events = engine.get_divergences()
        daily = engine.get_daily_structure()
        swing_snapshot = swing_engine.get_snapshot()

        state["df"] = updated
        state["events"] = events

        figure = build_market_figure_with_divergence(
            updated,
            events,
            SYMBOL,
            TIMEFRAME,
            daily=daily,
            swings=swing_snapshot,
        )

        latest = updated.iloc[-1]
        status = (
            f"Last candle: {updated.index[-1]} | "
            f"Close: {latest['close']:.2f} | "
            f"RSI: {latest['rsi']:.2f} | "
            f"Bars: {len(updated)} | "
            f"Closed replay bars: {len(closed_df)} | "
            f"Swings: {len(swing_snapshot['swings'])} | "
            f"Divergences: {len(events)}"
        )
        return figure, status

    except ccxt.NetworkError as error:
        figure = build_market_figure_with_divergence(
            state["df"],
            state["events"],
            SYMBOL,
            TIMEFRAME,
            daily=state["engine"].get_daily_structure(),
            swings=state["swing_engine"].get_snapshot(),
        )
        return figure, f"Network error: {error}"

    except ccxt.ExchangeError as error:
        figure = build_market_figure_with_divergence(
            state["df"],
            state["events"],
            SYMBOL,
            TIMEFRAME,
            daily=state["engine"].get_daily_structure(),
            swings=state["swing_engine"].get_snapshot(),
        )
        return figure, f"Exchange error: {error}"

    except Exception as error:
        figure = build_market_figure_with_divergence(
            state["df"],
            state["events"],
            SYMBOL,
            TIMEFRAME,
            daily=state["engine"].get_daily_structure(),
            swings=state["swing_engine"].get_snapshot(),
        )
        return figure, f"Market processing error: {error}"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=False)
