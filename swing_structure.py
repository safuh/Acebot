from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any

import pandas as pd


class SwingStructureEngine:
    """
    Stateful, non-repainting swing and market-structure engine.

    Feed completed OHLC candles in chronological order. A pivot at bar `i`
    is confirmed only after `right_bars` subsequent candles have closed.

    Swing highs/lows use strict comparisons against every candle in the
    left/right window. Equal highs/lows do not qualify as pivots.

    Structure breaks:
      * BOS: close breaks the latest confirmed swing in the current bias.
      * CHoCH: close breaks the latest confirmed swing against current bias.
      * The first break establishes the initial bias and is labelled BOS.

    Liquidity sweeps:
      * A wick strictly beyond a confirmed swing level marks it swept.
      * A wick sweep alone is not a BOS/CHoCH; a close beyond the level is.
    """

    def __init__(
        self,
        left_bars: int = 2,
        right_bars: int = 2,
        timeframe_ms: int = 3_600_000,
    ) -> None:
        if not isinstance(left_bars, int) or left_bars < 1:
            raise ValueError("left_bars must be an integer >= 1.")
        if not isinstance(right_bars, int) or right_bars < 1:
            raise ValueError("right_bars must be an integer >= 1.")
        if not isinstance(timeframe_ms, int) or timeframe_ms <= 0:
            raise ValueError("timeframe_ms must be a positive integer.")

        self.left_bars = left_bars
        self.right_bars = right_bars
        self.timeframe_ms = timeframe_ms
        self.bar_duration = pd.Timedelta(milliseconds=timeframe_ms)

        self.bars: list[dict[str, Any]] = []
        self.swings: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

        self.last_timestamp: pd.Timestamp | None = None
        self.bias: str | None = None
        self._latest_swing_high_id: str | None = None
        self._latest_swing_low_id: str | None = None
        self._event_counter = 0

    def update(
        self,
        timestamp: Any,
        candle: dict[str, Any] | pd.Series,
    ) -> list[dict[str, Any]]:
        """Process one completed candle and return events created by it."""
        timestamp = self._normalize_timestamp(timestamp)

        if self.last_timestamp is not None:
            if timestamp == self.last_timestamp:
                return []
            if timestamp < self.last_timestamp:
                raise ValueError(
                    "Candles must be processed chronologically: "
                    f"{timestamp} is earlier than {self.last_timestamp}."
                )

        row = self._normalize_candle(timestamp, candle)
        created: list[dict[str, Any]] = []

        # Only levels confirmed before this candle may be swept or broken.
        created.extend(self._process_existing_levels(row))

        self.bars.append(row)

        # A pivot is confirmed at the close of the current (rightmost) bar.
        pivot = self._find_confirmed_pivot()
        if pivot is not None:
            created.extend(self._record_pivot(pivot))

        self.last_timestamp = timestamp
        return deepcopy(created)

    def get_swings(self) -> list[dict[str, Any]]:
        """Return all confirmed swing points in chronological order."""
        return deepcopy(self.swings)

    def get_events(self) -> list[dict[str, Any]]:
        """Return all sweep and market-structure events."""
        return deepcopy(self.events)

    def get_snapshot(self) -> dict[str, Any]:
        """Return a detached snapshot suitable for charting."""
        return {
            "swings": self.get_swings(),
            "events": self.get_events(),
            "bias": self.bias,
        }

    def _find_confirmed_pivot(self) -> dict[str, Any] | None:
        window_size = self.left_bars + self.right_bars + 1
        if len(self.bars) < window_size:
            return None

        window = self.bars[-window_size:]
        pivot = window[self.left_bars]
        others = window[:self.left_bars] + window[self.left_bars + 1:]

        is_high = all(pivot["high"] > item["high"] for item in others)
        is_low = all(pivot["low"] < item["low"] for item in others)

        # A wide-range candle can be both a local high and a local low.
        if not is_high and not is_low:
            return None

        return {
            "bar": pivot,
            "is_high": is_high,
            "is_low": is_low,
            "confirmed_at": self.bars[-1]["timestamp"] + self.bar_duration,
        }

    def _record_pivot(self, pivot: dict[str, Any]) -> list[dict[str, Any]]:
        bar = pivot["bar"]
        created: list[dict[str, Any]] = []

        if pivot["is_high"]:
            previous = self._latest_swing("high")
            classification = None
            if previous is not None:
                classification = "HH" if bar["high"] > previous["price"] else "LH"

            swing = self._new_swing(
                side="high",
                bar=bar,
                price=bar["high"],
                classification=classification,
                confirmed_at=pivot["confirmed_at"],
            )
            self.swings.append(swing)
            self._latest_swing_high_id = swing["swing_id"]

            event = self._new_event(
                event_type="swing_high",
                timestamp=bar["timestamp"],
                confirmed_at=pivot["confirmed_at"],
                price=bar["high"],
                swing_id=swing["swing_id"],
                classification=classification,
            )
            self.events.append(event)
            created.append(event)

        if pivot["is_low"]:
            previous = self._latest_swing("low")
            classification = None
            if previous is not None:
                classification = "HL" if bar["low"] > previous["price"] else "LL"

            swing = self._new_swing(
                side="low",
                bar=bar,
                price=bar["low"],
                classification=classification,
                confirmed_at=pivot["confirmed_at"],
            )
            self.swings.append(swing)
            self._latest_swing_low_id = swing["swing_id"]

            event = self._new_event(
                event_type="swing_low",
                timestamp=bar["timestamp"],
                confirmed_at=pivot["confirmed_at"],
                price=bar["low"],
                swing_id=swing["swing_id"],
                classification=classification,
            )
            self.events.append(event)
            created.append(event)

        return created

    def _process_existing_levels(
        self,
        candle: dict[str, Any],
    ) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        candle_close_time = candle["timestamp"] + self.bar_duration

        for swing in self.swings:
            if candle_close_time <= swing["confirmed_at"]:
                continue

            side = swing["side"]
            price = swing["price"]

            if side == "high":
                swept = candle["high"] > price
                direction = "bullish"
            else:
                swept = candle["low"] < price
                direction = "bearish"

            if swept and not swing["liquidity_swept"]:
                swing["liquidity_swept"] = True
                swing["swept_at"] = candle_close_time

                event = self._new_event(
                    event_type="liquidity_sweep",
                    timestamp=candle["timestamp"],
                    confirmed_at=candle_close_time,
                    price=price,
                    swing_id=swing["swing_id"],
                    side=side,
                    direction=direction,
                    candle_extreme=(
                        candle["high"] if side == "high" else candle["low"]
                    ),
                )
                self.events.append(event)
                created.append(event)

        # Structure breaks are evaluated only against the latest confirmed
        # swing of each side. Older pivots remain available as liquidity data.
        for side, swing_id in (
            ("high", self._latest_swing_high_id),
            ("low", self._latest_swing_low_id),
        ):
            if swing_id is None:
                continue

            swing = next(
                (item for item in self.swings if item["swing_id"] == swing_id),
                None,
            )
            if swing is None or swing["broken"]:
                continue
            if candle_close_time <= swing["confirmed_at"]:
                continue

            if side == "high" and candle["close"] > swing["price"]:
                direction = "bullish"
            elif side == "low" and candle["close"] < swing["price"]:
                direction = "bearish"
            else:
                continue

            structure_type = (
                "BOS"
                if self.bias is None or direction == self.bias
                else "CHoCH"
            )

            previous_bias = self.bias
            self.bias = direction
            swing["broken"] = True
            swing["broken_at"] = candle_close_time

            event = self._new_event(
                event_type="structure_break",
                timestamp=candle["timestamp"],
                confirmed_at=candle_close_time,
                price=swing["price"],
                swing_id=swing["swing_id"],
                side=side,
                direction=direction,
                structure_type=structure_type,
                previous_bias=previous_bias,
                new_bias=self.bias,
                close=candle["close"],
            )
            self.events.append(event)
            created.append(event)

        return created

    def _latest_swing(self, side: str) -> dict[str, Any] | None:
        for swing in reversed(self.swings):
            if swing["side"] == side:
                return swing
        return None

    def _new_swing(
        self,
        side: str,
        bar: dict[str, Any],
        price: float,
        classification: str | None,
        confirmed_at: pd.Timestamp,
    ) -> dict[str, Any]:
        swing_id = (
            f"{side}:{bar['timestamp'].isoformat()}:"
            f"{self._event_counter + 1}"
        )
        self._event_counter += 1

        return {
            "swing_id": swing_id,
            "side": side,
            "timestamp": bar["timestamp"],
            "confirmed_at": confirmed_at,
            "price": price,
            "classification": classification,
            "liquidity_swept": False,
            "swept_at": None,
            "broken": False,
            "broken_at": None,
        }

    def _new_event(self, **fields: Any) -> dict[str, Any]:
        self._event_counter += 1
        return {
            "event_id": f"swing-event:{self._event_counter}",
            **fields,
        }

    @staticmethod
    def _normalize_timestamp(value: Any) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            raise ValueError("Candle timestamp cannot be NaT.")
        if timestamp.tzinfo is None:
            return timestamp.tz_localize("UTC")
        return timestamp.tz_convert("UTC")

    @staticmethod
    def _number(value: Any, field: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Candle field '{field}' must be numeric."
            ) from exc

        if not isfinite(number):
            raise ValueError(f"Candle field '{field}' must be finite.")

        return number

    def _normalize_candle(
        self,
        timestamp: pd.Timestamp,
        candle: dict[str, Any] | pd.Series,
    ) -> dict[str, Any]:
        try:
            high = self._number(candle["high"], "high")
            low = self._number(candle["low"], "low")
            close = self._number(candle["close"], "close")
            open_price = self._number(candle["open"], "open")
        except KeyError as exc:
            raise KeyError(
                "Each candle must contain open, high, low, and close."
            ) from exc

        if high < low:
            raise ValueError("Candle high cannot be below candle low.")

        if not low <= open_price <= high:
            raise ValueError("Candle open must be between low and high.")

        if not low <= close <= high:
            raise ValueError("Candle close must be between low and high.")

        return {
            "timestamp": timestamp,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        }