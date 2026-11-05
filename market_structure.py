from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any

import pandas as pd


class MarketStructureEngine:
    """
    Stateful daily market-structure and hidden-divergence engine.

    Historical replay and live streaming both use update(). Feed only
    completed candles, in chronological order. Timestamps are normalized
    to UTC and daily boundaries are UTC calendar days.

    A daily high/low is treated as a running extreme while the day develops.
    When a new extreme is made, its pending RSI candidate replaces the
    previous pending candidate. The candidate is confirmed only after the
    configured number of subsequent candles have closed.

    RSI association:
      * bearish/high candidate: maximum RSI in the symmetric window
      * bullish/low candidate: minimum RSI in the symmetric window
      * windows are clipped to the current UTC day
      * at day end, an incomplete right-hand window is clipped and finalized

    Divergence definitions:
      * hidden bearish: lower price high + higher RSI high
      * hidden bullish: higher price low + lower RSI low

    Reference levels are completed daily highs/lows. A reference level must
    still be unswept when the divergence is detected.

    Intervening-extreme rule:
      * bearish: current daily high must exceed every intervening daily high
      * bullish: current daily low must be below every intervening daily low

    A confirmed event is retained in history. If its reference liquidity
    level is swept later, the event's status changes to "invalidated".
    """

    def __init__(
        self,
        rsi_window_bars: int = 2,
        timeframe_ms: int = 3_600_000,
    ) -> None:
        if not isinstance(rsi_window_bars, int) or rsi_window_bars < 0:
            raise ValueError("rsi_window_bars must be a non-negative integer.")

        if not isinstance(timeframe_ms, int) or timeframe_ms <= 0:
            raise ValueError("timeframe_ms must be a positive integer.")

        self.rsi_window_bars = rsi_window_bars
        self.timeframe_ms = timeframe_ms
        self.bar_duration = pd.Timedelta(milliseconds=timeframe_ms)

        # These are intentionally None until the first valid candle arrives.
        self.current_day: pd.Timestamp | None = None
        self.current_state: dict[str, Any] | None = None
        self.last_timestamp: pd.Timestamp | None = None

        # Completed daily liquidity levels, in chronological order.
        self.levels: list[dict[str, Any]] = []

        # All detected events, keyed by deterministic event ID.
        self.events: dict[str, dict[str, Any]] = {}
        # Timestamped RSI observations across all processed candles.
        # Required for checking trendline integrity across daily boundaries.
        self.rsi_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        timestamp: Any,
        candle: dict[str, Any] | pd.Series,
    ) -> list[dict[str, Any]]:
        """
        Commit one completed candle to the engine.

        Parameters
        ----------
        timestamp:
            Candle opening timestamp. Naive timestamps are interpreted as UTC.
        candle:
            Mapping/Series containing high, low, close and rsi.

        Returns
        -------
        list[dict]
            Deep copies of events created by this update.

        Duplicate timestamps are ignored. Older timestamps raise ValueError.
        """
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
        day = timestamp.normalize()

        existing_event_ids = set(self.events)

        # A day transition closes and stores the previous day before the
        # first candle of the new day is processed.
        if self.current_day is not None and day != self.current_day:
            if day < self.current_day:
                raise ValueError("Candles must be processed chronologically.")
            self._finalize_day()

        # Initialize the first day or the newly started day.
        if self.current_day is None or day != self.current_day:
            self.current_day = day
            self.current_state = self._new_day_state(day)

        # Defensive invariant: a current day must always have a state.
        if self.current_state is None:
            raise RuntimeError(
                f"Daily state initialization failed for {day.isoformat()}."
            )

        state = self.current_state
        state["candles"].append(row)

        # Retain RSI history so divergence checks can inspect every
        # observation between RSI endpoints, including previous days.
        self.rsi_history.append({
            "timestamp": timestamp,
            "rsi": row["rsi"],
        })

        position = len(state["candles"]) - 1

        # Update the running daily high and replace its pending candidate
        # whenever a strictly higher high is printed.
        if state["high"] is None or row["high"] > state["high"]:
            state["high"] = row["high"]
            state["high_candidate"] = {
                "position": position,
                "timestamp": timestamp,
                "price": row["high"],
                "confirmed": False,
            }

        # Update the running daily low and replace its pending candidate
        # whenever a strictly lower low is printed.
        if state["low"] is None or row["low"] < state["low"]:
            state["low"] = row["low"]
            state["low_candidate"] = {
                "position": position,
                "timestamp": timestamp,
                "price": row["low"],
                "confirmed": False,
            }

        # Process sweeps before testing new divergence candidates. A level
        # swept on this candle is therefore unavailable as a reference.
        self._update_sweeps(row)

        # A later sweep can invalidate an event already in the event log.
        self._update_event_status(row["timestamp"] + self.bar_duration)

        # Confirm candidates only when their complete right-hand RSI window
        # is available from candles that have already closed.
        self._confirm_ready_candidates(row["timestamp"])

        self.last_timestamp = timestamp

        return [
            deepcopy(self.events[event_id])
            for event_id in self.events
            if event_id not in existing_event_ids
        ]
    
    def _has_strict_rsi_trendline_integrity(
        self,
        direction: str,
        start_timestamp: pd.Timestamp,
        start_rsi: float,
        end_timestamp: pd.Timestamp,
        end_rsi: float,
    ) -> bool:
        """
        Validate that every intermediate RSI observation respects the
        straight line connecting the two RSI endpoints.

        Bearish:
            Every intermediate RSI must be <= the line.

        Bullish:
            Every intermediate RSI must be >= the line.

        The endpoint observations themselves are excluded from the test.
        No tolerance is applied.
        """

        if direction not in {"bearish", "bullish"}:
            raise ValueError(
                f"Unknown divergence direction: {direction!r}"
            )

        start_timestamp = self._normalize_timestamp(start_timestamp)
        end_timestamp = self._normalize_timestamp(end_timestamp)

        if pd.isna(start_rsi) or pd.isna(end_rsi):
            return False

        # The RSI endpoints must be chronologically ordered.
        if end_timestamp <= start_timestamp:
            return False

        duration = (
            end_timestamp - start_timestamp
        ).total_seconds()

        if duration <= 0:
            return False

        for observation in self.rsi_history:

            timestamp = observation["timestamp"]
            value = observation["rsi"]

            # Only inspect observations strictly between the endpoints.
            if not start_timestamp < timestamp < end_timestamp:
                continue

            # Ignore unavailable RSI values.
            if pd.isna(value):
                continue

            elapsed = (
                timestamp - start_timestamp
            ).total_seconds()

            progress = elapsed / duration

            # RSI value on the straight line at this timestamp.
            trendline_value = (
                start_rsi
                + progress * (end_rsi - start_rsi)
            )

            if direction == "bearish":
                # Any RSI value above the line invalidates the setup.
                if value > trendline_value:
                    return False

            else:
                # Any RSI value below the line invalidates the setup.
                if value < trendline_value:
                    return False

        return True
    def get_divergences(
        self,
        include_invalidated: bool = True,
    ) -> list[dict[str, Any]]:
        """Return a deep-copied, chronologically sorted event history."""
        events = list(self.events.values())

        if not include_invalidated:
            events = [
                event for event in events
                if event["status"] == "confirmed"
            ]

        events.sort(key=lambda event: event["detected_at"])
        return deepcopy(events)

    def get_daily_structure(self) -> pd.DataFrame:
        """Return completed daily highs/lows and associated RSI values."""
        if not self.levels:
            return pd.DataFrame()

        frame = pd.DataFrame(deepcopy(self.levels))
        return frame.set_index("day").sort_index()

    def get_current_day(self) -> dict[str, Any] | None:
        """Return a snapshot of the currently developing UTC day."""
        if self.current_day is None or self.current_state is None:
            return None

        return {
            "day": self.current_day,
            "high": self.current_state["high"],
            "low": self.current_state["low"],
            "high_candidate": deepcopy(
                self.current_state["high_candidate"]
            ),
            "low_candidate": deepcopy(
                self.current_state["low_candidate"]
            ),
            "candles_processed": len(self.current_state["candles"]),
        }

    def get_liquidity_levels(self) -> list[dict[str, Any]]:
        """Return a deep copy of completed daily liquidity levels."""
        return deepcopy(self.levels)

    # ------------------------------------------------------------------
    # Input normalization and daily state
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_timestamp(timestamp: Any) -> pd.Timestamp:
        result = pd.Timestamp(timestamp)

        if pd.isna(result):
            raise ValueError("Candle timestamp cannot be NaT.")

        if result.tzinfo is None:
            result = result.tz_localize("UTC")
        else:
            result = result.tz_convert("UTC")

        return result

    @staticmethod
    def _to_float(value: Any, field: str, allow_nan: bool = False) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Candle field '{field}' must be numeric.") from exc

        if allow_nan and pd.isna(result):
            return float("nan")

        if not isfinite(result):
            raise ValueError(
                f"Candle field '{field}' must be finite; received {value!r}."
            )

        return result

    def _normalize_candle(
        self,
        timestamp: pd.Timestamp,
        candle: dict[str, Any] | pd.Series,
    ) -> dict[str, Any]:
        try:
            high = self._to_float(candle["high"], "high")
            low = self._to_float(candle["low"], "low")
            close = self._to_float(candle["close"], "close")
            rsi = self._to_float(candle["rsi"], "rsi", allow_nan=True)
        except KeyError as exc:
            raise KeyError(
                "Each candle must contain 'high', 'low', 'close', and 'rsi'."
            ) from exc

        if high < low:
            raise ValueError("Candle high cannot be below its low.")

        if close < low or close > high:
            raise ValueError(
                "Candle close must be between the candle's low and high."
            )

        if not pd.isna(rsi) and not 0.0 <= rsi <= 100.0:
            raise ValueError(f"RSI must be between 0 and 100; received {rsi}.")

        return {
            "timestamp": timestamp,
            "high": high,
            "low": low,
            "close": close,
            "rsi": rsi,
        }

    @staticmethod
    def _new_day_state(day: pd.Timestamp) -> dict[str, Any]:
        if day is None or pd.isna(day):
            raise ValueError("Cannot initialize daily state without a valid day.")

        return {
            "day": day,
            "day_key": day.isoformat(),
            "candles": [],
            "high": None,
            "low": None,
            "high_candidate": None,
            "low_candidate": None,
        }

    # ------------------------------------------------------------------
    # RSI window selection
    # ------------------------------------------------------------------

    def _get_rsi_extreme(
        self,
        state: dict[str, Any],
        candidate: dict[str, Any] | None,
        direction: str,
        allow_partial: bool = False,
    ) -> dict[str, Any] | None:
        """
        Select the RSI extreme in the candidate's symmetric, day-clipped
        window. A full window is required during normal streaming.
        """
        if candidate is None:
            return None

        if direction not in {"bearish", "bullish"}:
            raise ValueError(f"Unknown divergence direction: {direction!r}")

        candles = state["candles"]
        position = candidate["position"]
        radius = self.rsi_window_bars

        # During streaming, wait until all required bars to the right close.
        if not allow_partial and position + radius >= len(candles):
            return None

        start = max(0, position - radius)
        end = min(len(candles), position + radius + 1)
        window = candles[start:end]

        valid = [
            item for item in window
            if not pd.isna(item["rsi"])
        ]

        if not valid:
            return None

        if direction == "bearish":
            selected = max(valid, key=lambda item: item["rsi"])
        else:
            selected = min(valid, key=lambda item: item["rsi"])

        return {
            "value": selected["rsi"],
            "timestamp": selected["timestamp"],
        }

    # ------------------------------------------------------------------
    # Candidate confirmation
    # ------------------------------------------------------------------

    def _confirm_ready_candidates(self, timestamp: pd.Timestamp) -> None:
        state = self.current_state
        if state is None or not state["candles"]:
            return

        last_position = len(state["candles"]) - 1

        for direction in ("bearish", "bullish"):
            key = (
                "high_candidate"
                if direction == "bearish"
                else "low_candidate"
            )
            candidate = state[key]

            if candidate is None or candidate["confirmed"]:
                continue

            age = last_position - candidate["position"]
            if age < self.rsi_window_bars:
                continue

            self._confirm_candidate(
                direction=direction,
                timestamp=timestamp,
                allow_partial=False,
            )

    def _confirm_candidate(
        self,
        direction: str,
        timestamp: pd.Timestamp,
        allow_partial: bool = False,
    ) -> None:
        state = self.current_state
        if state is None:
            return

        key = (
            "high_candidate"
            if direction == "bearish"
            else "low_candidate"
        )
        candidate = state[key]

        if candidate is None or candidate["confirmed"]:
            return

        rsi_extreme = self._get_rsi_extreme(
            state=state,
            candidate=candidate,
            direction=direction,
            allow_partial=allow_partial,
        )

        # Mark as confirmed even if its RSI window contains no valid RSI.
        # It must not be repeatedly reconsidered on every subsequent bar.
        candidate["confirmed"] = True

        if rsi_extreme is None:
            return

        self._detect_divergence(
            direction=direction,
            candidate=candidate,
            rsi_extreme=rsi_extreme,
            detected_at=timestamp + self.bar_duration,
        )

    # ------------------------------------------------------------------
    # Divergence detection
    # ------------------------------------------------------------------

    def _detect_divergence(
        self,
        direction: str,
        candidate: dict[str, Any],
        rsi_extreme: dict[str, Any],
        detected_at: pd.Timestamp,
    ) -> None:
        if self.current_day is None:
            raise RuntimeError("Cannot detect divergence without a current day.")

        day = self.current_day
        price = candidate["price"]
        rsi = rsi_extreme["value"]

        # Only completed daily levels before the current day can be
        # reference levels.
        previous_levels = [
            level for level in self.levels
            if level["day"] < day
        ]

        for reference in previous_levels:
            reference_day = reference["day"]

            if direction == "bearish":
                # The reference daily high must remain unswept.
                if reference["high_swept_on"] is not None:
                    continue

                if pd.isna(reference["rsi_near_high"]):
                    continue

                # Hidden bearish: lower price high + higher RSI high.
                if not price < reference["high"]:
                    continue

                if not rsi > reference["rsi_near_high"]:
                    continue

                # User-defined intervening-extreme condition:
                # current high must exceed ALL intervening daily highs.
                intervening = [
                    level["high"]
                    for level in self.levels
                    if reference_day < level["day"] < day
                ]
                if intervening and not price > max(intervening):
                    continue

                reference_price = reference["high"]
                reference_rsi = reference["rsi_near_high"]
                reference_price_timestamp = reference["high_timestamp"]
                reference_rsi_timestamp = reference[
                    "rsi_near_high_timestamp"
                ]

            elif direction == "bullish":
                # The reference daily low must remain unswept.
                if reference["low_swept_on"] is not None:
                    continue

                if pd.isna(reference["rsi_near_low"]):
                    continue

                # Hidden bullish: higher price low + lower RSI low.
                if not price > reference["low"]:
                    continue

                if not rsi < reference["rsi_near_low"]:
                    continue

                # User-defined inverse condition:
                # current low must be below ALL intervening daily lows.
                intervening = [
                    level["low"]
                    for level in self.levels
                    if reference_day < level["day"] < day
                ]
                if intervening and not price < min(intervening):
                    continue

                reference_price = reference["low"]
                reference_rsi = reference["rsi_near_low"]
                reference_price_timestamp = reference["low_timestamp"]
                reference_rsi_timestamp = reference[
                    "rsi_near_low_timestamp"
                ]

            else:
                raise ValueError(f"Unknown divergence direction: {direction!r}")
            # Strict RSI trendline integrity.
            #
            # Reject the divergence if any intermediate RSI observation
            # violates the line connecting the reference and current RSI.
            if not self._has_strict_rsi_trendline_integrity(
                direction=direction,
                start_timestamp=reference_rsi_timestamp,
                start_rsi=reference_rsi,
                end_timestamp=rsi_extreme["timestamp"],
                end_rsi=rsi,
            ):
                continue

            # One event per reference level and actual current price extreme.
            event_id = (
                f"{direction}:"
                f"{reference_day.isoformat()}:"
                f"{day.isoformat()}:"
                f"{candidate['timestamp'].isoformat()}"
            )

            if event_id in self.events:
                continue

            self.events[event_id] = {
                "event_id": event_id,
                "direction": direction,
                "reference_day": reference_day,
                "current_day": day,
                "detected_at": detected_at,
                "reference_price": reference_price,
                "current_price": price,
                "reference_price_timestamp": reference_price_timestamp,
                "current_price_timestamp": candidate["timestamp"],
                "reference_rsi": reference_rsi,
                "current_rsi": rsi,
                "reference_rsi_timestamp": reference_rsi_timestamp,
                "current_rsi_timestamp": rsi_extreme["timestamp"],
                "price_difference": price - reference_price,
                "rsi_difference": rsi - reference_rsi,
                "status": "confirmed",
                "invalidated_at": None,
            }

    # ------------------------------------------------------------------
    # Liquidity sweeps and event lifecycle
    # ------------------------------------------------------------------

    def _update_sweeps(self, candle: dict[str, Any]) -> None:
        """
        Mark the first completed candle that strictly breaches each
        completed daily high/low. Store candle close time so the sweep
        can be compared consistently with event detection time.
        """
        sweep_time = candle["timestamp"] + self.bar_duration

        for level in self.levels:
            if (
                level["high_swept_on"] is None
                and candle["high"] > level["high"]
            ):
                level["high_swept_on"] = sweep_time

            if (
                level["low_swept_on"] is None
                and candle["low"] < level["low"]
            ):
                level["low_swept_on"] = sweep_time

    def _update_event_status(self, timestamp: pd.Timestamp) -> None:
        """Invalidate confirmed events if their reference is swept later."""
        level_by_day = {
            level["day"]: level
            for level in self.levels
        }

        for event in self.events.values():
            if event["status"] != "confirmed":
                continue

            reference = level_by_day.get(event["reference_day"])
            if reference is None:
                continue

            if event["direction"] == "bearish":
                sweep_time = reference["high_swept_on"]
            else:
                sweep_time = reference["low_swept_on"]

            # Sweep timestamps and detected_at are candle-close times.
            if (
                sweep_time is not None
                and sweep_time > event["detected_at"]
            ):
                event["status"] = "invalidated"
                event["invalidated_at"] = timestamp

    # ------------------------------------------------------------------
    # Day finalization
    # ------------------------------------------------------------------

    def _finalize_day(self) -> None:
        """
        Finalize the current day and append its daily liquidity level.

        This is called automatically on the first candle of the next day.
        The last day in a historical replay remains the developing day
        until the next day's first candle arrives.
        """
        state = self.current_state

        if state is None or not state["candles"]:
            return

        high_candidate = state["high_candidate"]
        low_candidate = state["low_candidate"]

        if high_candidate is None or low_candidate is None:
            raise RuntimeError(
                f"Incomplete daily extremes for {self.current_day!r}."
            )

        last_timestamp = state["candles"][-1]["timestamp"]

        # At day close, finalize candidates using the available part of
        # their RSI windows, clipped to candles belonging to this day.
        self._confirm_candidate(
            direction="bearish",
            timestamp=last_timestamp,
            allow_partial=True,
        )
        self._confirm_candidate(
            direction="bullish",
            timestamp=last_timestamp,
            allow_partial=True,
        )

        high_rsi = self._get_rsi_extreme(
            state=state,
            candidate=high_candidate,
            direction="bearish",
            allow_partial=True,
        )
        low_rsi = self._get_rsi_extreme(
            state=state,
            candidate=low_candidate,
            direction="bullish",
            allow_partial=True,
        )

        level = {
            "day": self.current_day,
            "high": state["high"],
            "low": state["low"],
            "high_timestamp": high_candidate["timestamp"],
            "low_timestamp": low_candidate["timestamp"],
            "rsi_near_high": (
                high_rsi["value"] if high_rsi is not None else float("nan")
            ),
            "rsi_near_high_timestamp": (
                high_rsi["timestamp"] if high_rsi is not None else pd.NaT
            ),
            "rsi_near_low": (
                low_rsi["value"] if low_rsi is not None else float("nan")
            ),
            "rsi_near_low_timestamp": (
                low_rsi["timestamp"] if low_rsi is not None else pd.NaT
            ),
            "high_swept_on": None,
            "low_swept_on": None,
        }

        # Avoid accidentally adding the same UTC day twice.
        if self.levels and self.levels[-1]["day"] == self.current_day:
            self.levels[-1] = level
        else:
            self.levels.append(level)
