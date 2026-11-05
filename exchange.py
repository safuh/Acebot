
import time

import ccxt
import pandas as pd

from config import (
    EXCHANGE_ID,
    EXCHANGE_OPTIONS,
    SYMBOL,
    TIMEFRAME,
    N,
    OHLCV_LIMIT,
)


_exchange = None


# ==========================================
# EXCHANGE INITIALIZATION
# ==========================================

def get_exchange():
    """
    Lazily initialize and reuse one CCXT instance.
    """

    global _exchange

    if _exchange is None:
        exchange_class = getattr(ccxt, EXCHANGE_ID)
        _exchange = exchange_class(EXCHANGE_OPTIONS)

    return _exchange


def initialize_exchange():
    """
    Load markets and validate exchange configuration.
    """

    exchange = get_exchange()

    try:
        exchange.load_markets()

        if SYMBOL not in exchange.markets:
            raise ValueError(
                f"{SYMBOL} is not available on {EXCHANGE_ID}"
            )

        if not exchange.has.get("fetchOHLCV"):
            raise RuntimeError(
                f"{EXCHANGE_ID} does not support fetchOHLCV"
            )

        return exchange

    except Exception:
        close_exchange()
        raise


def get_timeframe_ms():
    exchange = get_exchange()

    return exchange.parse_timeframe(TIMEFRAME) * 1000


# ==========================================
# DATAFRAME CONVERSION
# ==========================================

def ohlcv_to_dataframe(ohlcv):

    columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    if not ohlcv:
        return pd.DataFrame(
            columns=columns[1:],
            index=pd.DatetimeIndex(
                [],
                tz="UTC",
                name="timestamp"
            )
        )

    df = pd.DataFrame(ohlcv, columns=columns)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="ms",
        utc=True
    )

    df.set_index("timestamp", inplace=True)

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    df[numeric_columns] = df[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce"
    )

    df.dropna(
        subset=numeric_columns,
        inplace=True
    )

    df = df[
        ~df.index.duplicated(keep="last")
    ]

    return df.sort_index()


# ==========================================
# HISTORICAL DATA FETCHING
# ==========================================

def fetch_ohlcv_history(
    since,
    limit=OHLCV_LIMIT
):
    """
    Fetch historical candles using pagination.
    """

    exchange = get_exchange()

    all_candles = []

    timeframe_ms = get_timeframe_ms()

    while True:

        batch = exchange.fetch_ohlcv(
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            since=since,
            limit=limit
        )

        if not batch:
            break

        all_candles.extend(batch)

        last_timestamp = batch[-1][0]

        next_since = last_timestamp + timeframe_ms

        if next_since <= since:
            break

        since = next_since

        if len(batch) < limit:
            break

        time.sleep(0.1)

    return ohlcv_to_dataframe(all_candles)


def fetch_initial_history():
    """
    Fetch the initial N historical candles.
    """

    exchange = get_exchange()

    print(
        f"Fetching {N} candles of "
        f"{SYMBOL} ({TIMEFRAME})..."
    )

    timeframe_ms = get_timeframe_ms()

    now_ms = exchange.milliseconds()

    since = now_ms - (N * timeframe_ms)

    df = fetch_ohlcv_history(
        since=since,
        limit=OHLCV_LIMIT
    )

    if df.empty:
        raise RuntimeError(
            "No historical OHLCV data received."
        )

    return df.tail(N)


# ==========================================
# INCREMENTAL CANDLE UPDATES
# ==========================================

def update_latest_candle(df):
    """
    Update the latest candle and recover missing candles.

    Existing timestamps are replaced with fresh exchange data.
    """

    if df.empty:
        raise ValueError(
            "Cannot update an empty DataFrame."
        )

    last_timestamp = df.index[-1]

    since = int(
        last_timestamp.timestamp() * 1000
    )

    latest_data = fetch_ohlcv_history(
        since=since,
        limit=OHLCV_LIMIT
    )

    if latest_data.empty:
        return df

    updated = pd.concat([
        df,
        latest_data
    ])

    updated = updated[
        ~updated.index.duplicated(keep="last")
    ]

    return updated.sort_index()


# ==========================================
# EXCHANGE SHUTDOWN
# ==========================================

def close_exchange():
    """
    Release exchange resources.
    """

    global _exchange

    if _exchange is not None:
        _exchange.close()
        _exchange = None
