
import pandas as pd


def calculate_rsi(df, period=14):
    """
    Calculate Wilder's RSI using closing prices.
    """

    delta = df["close"].diff()
    #tp = (df["high"] + df["low"] + df["close"]) / 3
    #delta = tp.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    # Handle zero-loss and zero-gain cases.
    rsi = rsi.mask(avg_loss == 0, 100)
    rsi = rsi.mask(
        (avg_gain == 0) & (avg_loss == 0),
        50
    )

    return rsi


def add_intraday_features(df, rsi_period=14):
    """
    Add UTC day markers, running daily extremes and RSI
    to the intraday OHLCV DataFrame.
    """

    df = df.copy()

    # Ensure UTC-aware timestamps.
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    df = df.sort_index()

    # UTC date identifier.
    df["day"] = df.index.normalize()

    # True only for candles timestamped exactly 00:00 UTC.
    df["day_start"] = df.index == df.index.normalize()

    # Running daily extremes (no future data leakage).
    df["day_high"] = (
        df.groupby("day")["high"].cummax()
    )

    df["day_low"] = (
        df.groupby("day")["low"].cummin()
    )

    # RSI.
    df["rsi"] = calculate_rsi(
        df,
        period=rsi_period
    )

    return df



import pandas as pd


import pandas as pd


def build_daily_structure(df, rsi_window_bars=2):
    """
    Build daily OHLCV structure, associate RSI with daily
    price extremes, and identify subsequent liquidity sweeps.

    RSI association:
        Daily high -> maximum RSI within the surrounding window.
        Daily low  -> minimum RSI within the surrounding window.

    rsi_window_bars=2:
        Two candles before and after the price-extreme candle,
        constrained to the same day.
    """

    required = {
        "open", "high", "low", "close", "volume", "rsi", "day"
    }

    missing = required.difference(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    if rsi_window_bars < 0:
        raise ValueError("rsi_window_bars cannot be negative.")

    if not df.index.is_unique:
        raise ValueError("DataFrame index must be unique.")

    df = df.sort_index()

    daily = (
        df.groupby("day")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .sort_index()
    )

    # RSI values associated with the daily extremes.
    for column in [
        "rsi_at_high",
        "rsi_at_low",
        "rsi_near_high",
        "rsi_near_low",
    ]:
        daily[column] = float("nan")

    # Timestamps of price extremes.
    # Use the same datetime dtype as the candle index.
    timestamp_columns = [
        "high_timestamp",
        "low_timestamp",
        "rsi_near_high_timestamp",
        "rsi_near_low_timestamp",
    ]

    for column in timestamp_columns:
        daily[column] = pd.Series(
            pd.NaT,
            index=daily.index,
            dtype=df.index.dtype,
        )

    # Associate RSI with each daily extreme.
    for day, group in df.groupby("day", sort=True):

        if group.empty:
            continue

        high_timestamp = group["high"].idxmax()
        low_timestamp = group["low"].idxmin()

        high_position = group.index.get_loc(high_timestamp)
        low_position = group.index.get_loc(low_timestamp)

        daily.at[day, "high_timestamp"] = high_timestamp
        daily.at[day, "low_timestamp"] = low_timestamp

        daily.at[day, "rsi_at_high"] = group.at[
            high_timestamp, "rsi"
        ]

        daily.at[day, "rsi_at_low"] = group.at[
            low_timestamp, "rsi"
        ]

        # Window around daily high.
        high_start = max(0, high_position - rsi_window_bars)
        high_end = min(
            len(group),
            high_position + rsi_window_bars + 1,
        )

        high_window = group["rsi"].iloc[
            high_start:high_end
        ].dropna()

        if not high_window.empty:
            rsi_high_timestamp = high_window.idxmax()

            daily.at[day, "rsi_near_high"] = (
                high_window.loc[rsi_high_timestamp]
            )

            daily.at[day, "rsi_near_high_timestamp"] = (
                rsi_high_timestamp
            )

        # Window around daily low.
        low_start = max(0, low_position - rsi_window_bars)
        low_end = min(
            len(group),
            low_position + rsi_window_bars + 1,
        )

        low_window = group["rsi"].iloc[
            low_start:low_end
        ].dropna()

        if not low_window.empty:
            rsi_low_timestamp = low_window.idxmin()

            daily.at[day, "rsi_near_low"] = (
                low_window.loc[rsi_low_timestamp]
            )

            daily.at[day, "rsi_near_low_timestamp"] = (
                rsi_low_timestamp
            )

    # Initialize liquidity sweep information.
    daily["high_swept"] = False
    daily["low_swept"] = False

    daily["high_swept_on"] = pd.Series(
        pd.NaT,
        index=daily.index,
        dtype=df.index.dtype,
    )

    daily["low_swept_on"] = pd.Series(
        pd.NaT,
        index=daily.index,
        dtype=df.index.dtype,
    )

    # Identify the first subsequent daily sweep.
    days = daily.index

    for i, day in enumerate(days):

        subsequent = daily.iloc[i + 1:]

        if subsequent.empty:
            continue

        high_sweeps = subsequent.index[
            subsequent["high"] > daily.at[day, "high"]
        ]

        if len(high_sweeps):
            daily.at[day, "high_swept"] = True
            daily.at[day, "high_swept_on"] = high_sweeps[0]

        low_sweeps = subsequent.index[
            subsequent["low"] < daily.at[day, "low"]
        ]

        if len(low_sweeps):
            daily.at[day, "low_swept"] = True
            daily.at[day, "low_swept_on"] = low_sweeps[0]

    return daily
def find_hidden_divergence(daily, current_day):
    """
    Detect hidden divergence against previous unswept daily extremes.

    Hidden bearish:
        1. Current high < reference high.
        2. Current RSI near high > reference RSI near high.
        3. Current high > every intervening daily high.
        4. Reference high was not swept before current_day.

    Hidden bullish:
        1. Current low > reference low.
        2. Current RSI near low < reference RSI near low.
        3. Current low < every intervening daily low.
        4. Reference low was not swept before current_day.

    All comparisons are strict.
    """

    required = {
        "high",
        "low",
        "rsi_near_high",
        "rsi_near_low",
        "high_swept_on",
        "low_swept_on",
    }

    missing = required.difference(daily.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    current_day = pd.Timestamp(current_day)

    # Normalize timezone to match the daily index.
    if daily.index.tz is not None:
        if current_day.tzinfo is None:
            current_day = current_day.tz_localize(
                daily.index.tz
            )
        else:
            current_day = current_day.tz_convert(
                daily.index.tz
            )

    elif current_day.tzinfo is not None:
        current_day = current_day.tz_localize(None)

    if current_day not in daily.index:
        raise ValueError(
            f"{current_day} is not present in daily structure."
        )

    current = daily.loc[current_day]
    previous = daily.loc[daily.index < current_day]

    result = {
        "bearish": [],
        "bullish": [],
    }

    if previous.empty:
        return result

    # Reference levels must have remained unswept
    # as of current_day.
    unswept_highs = previous.loc[
        previous["high_swept_on"].isna()
        | (previous["high_swept_on"] > current_day)
    ]

    unswept_lows = previous.loc[
        previous["low_swept_on"].isna()
        | (previous["low_swept_on"] > current_day)
    ]

    # --------------------------------------------------
    # Hidden bearish divergence
    # --------------------------------------------------

    if pd.notna(current["rsi_near_high"]):

        for reference_day, reference in unswept_highs.iterrows():

            if pd.isna(reference["rsi_near_high"]):
                continue

            # Price must form a lower high.
            lower_high = (
                current["high"] < reference["high"]
            )

            # RSI must form a higher high.
            higher_rsi = (
                current["rsi_near_high"]
                > reference["rsi_near_high"]
            )

            if not (lower_high and higher_rsi):
                continue

            # Check all daily highs between the two extremes.
            between = daily.loc[
                (daily.index > reference_day)
                & (daily.index < current_day)
            ]

            if not between.empty:

                # Current high must exceed every intervening high.
                if not (
                    current["high"] > between["high"].max()
                ):
                    continue

            result["bearish"].append({
                "reference_day": reference_day,
                "current_day": current_day,

                "reference_price": reference["high"],
                "current_price": current["high"],

                "reference_price_timestamp": reference.get(
                    "high_timestamp"
                ),
                "current_price_timestamp": current.get(
                    "high_timestamp"
                ),

                "reference_rsi": reference["rsi_near_high"],
                "current_rsi": current["rsi_near_high"],

                "reference_rsi_timestamp": reference.get(
                    "rsi_near_high_timestamp"
                ),
                "current_rsi_timestamp": current.get(
                    "rsi_near_high_timestamp"
                ),

                "price_difference": (
                    current["high"] - reference["high"]
                ),

                "rsi_difference": (
                    current["rsi_near_high"]
                    - reference["rsi_near_high"]
                ),
            })

    # --------------------------------------------------
    # Hidden bullish divergence
    # --------------------------------------------------

    if pd.notna(current["rsi_near_low"]):

        for reference_day, reference in unswept_lows.iterrows():

            if pd.isna(reference["rsi_near_low"]):
                continue

            # Price must form a higher low.
            higher_low = (
                current["low"] > reference["low"]
            )

            # RSI must form a lower low.
            lower_rsi = (
                current["rsi_near_low"]
                < reference["rsi_near_low"]
            )

            if not (higher_low and lower_rsi):
                continue

            # Check all daily lows between the two extremes.
            between = daily.loc[
                (daily.index > reference_day)
                & (daily.index < current_day)
            ]

            if not between.empty:

                # Current low must be below every intervening low.
                if not (
                    current["low"] < between["low"].min()
                ):
                    continue

            result["bullish"].append({
                "reference_day": reference_day,
                "current_day": current_day,

                "reference_price": reference["low"],
                "current_price": current["low"],

                "reference_price_timestamp": reference.get(
                    "low_timestamp"
                ),
                "current_price_timestamp": current.get(
                    "low_timestamp"
                ),

                "reference_rsi": reference["rsi_near_low"],
                "current_rsi": current["rsi_near_low"],

                "reference_rsi_timestamp": reference.get(
                    "rsi_near_low_timestamp"
                ),
                "current_rsi_timestamp": current.get(
                    "rsi_near_low_timestamp"
                ),

                "price_difference": (
                    current["low"] - reference["low"]
                ),

                "rsi_difference": (
                    current["rsi_near_low"]
                    - reference["rsi_near_low"]
                ),
            })

    # Most recent reference first.
    result["bearish"].sort(
        key=lambda x: x["reference_day"],
        reverse=True,
    )

    result["bullish"].sort(
        key=lambda x: x["reference_day"],
        reverse=True,
    )

    return result
def get_unswept_levels(daily, current_day, lookback=5):
    """
    Return previous days' unswept highs and lows.

    current_day is excluded because its extremes are
    still developing.
    """

    previous = daily.loc[daily.index < current_day].tail(lookback)

    unswept_highs = previous.loc[
        ~previous["high_swept"],
        ["high", "rsi_at_high"]
    ].copy()

    unswept_lows = previous.loc[
        ~previous["low_swept"],
        ["low", "rsi_at_low"]
    ].copy()

    return unswept_highs, unswept_lows
