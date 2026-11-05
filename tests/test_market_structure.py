import unittest

import pandas as pd

from market_structure import MarketStructureEngine


class SwingDerivedDailyExtremeTests(unittest.TestCase):
    def test_daily_extremes_come_only_from_confirmed_swings(self):
        engine = MarketStructureEngine(
            rsi_window_bars=0,
            timeframe_ms=3_600_000,
            min_reference_days=2,
            max_reference_days=21,
        )
        day = pd.Timestamp("2026-01-01 00:00:00", tz="UTC")

        rows = [
            # The first candle contains the raw daily high and low, but is
            # not supplied as a confirmed swing pivot.
            {"open": 10, "high": 22, "low": 1, "close": 10, "rsi": 40},
            {"open": 10, "high": 14, "low": 6, "close": 10, "rsi": 45},
            {"open": 10, "high": 20, "low": 5, "close": 10, "rsi": 50},
            {"open": 10, "high": 15, "low": 7, "close": 10, "rsi": 55},
        ]

        for position, candle in enumerate(rows):
            timestamp = day + pd.Timedelta(hours=position)
            swings = []
            if position == 3:
                swings.extend([
                    {
                        "event_type": "swing_high",
                        "timestamp": day + pd.Timedelta(hours=2),
                        "price": 20,
                        "confirmed_at": timestamp + pd.Timedelta(hours=1),
                        "swing_id": "test-high",
                    },
                    {
                        "event_type": "swing_low",
                        "timestamp": day + pd.Timedelta(hours=2),
                        "price": 5,
                        "confirmed_at": timestamp + pd.Timedelta(hours=1),
                        "swing_id": "test-low",
                    },
                ])
            engine.update(timestamp, candle, confirmed_swings=swings)

        next_day = day + pd.Timedelta(days=1)
        engine.update(
            next_day,
            {"open": 10, "high": 16, "low": 6, "close": 10, "rsi": 50},
        )

        daily = engine.get_daily_structure()
        self.assertEqual(daily.loc[day, "high"], 20)
        self.assertEqual(daily.loc[day, "low"], 5)
        self.assertEqual(engine.min_reference_days, 2)
        self.assertEqual(engine.max_reference_days, 21)

    def test_reference_window_is_two_through_twenty_one_calendar_days(self):
        current_day = pd.Timestamp("2026-03-01 00:00:00", tz="UTC")

        for days_back, should_detect in (
            (1, False),
            (2, True),
            (21, True),
            (22, False),
        ):
            with self.subTest(days_back=days_back):
                engine = MarketStructureEngine(
                    rsi_window_bars=0,
                    timeframe_ms=3_600_000,
                    min_reference_days=2,
                    max_reference_days=21,
                )
                reference_day = current_day - pd.Timedelta(days=days_back)
                reference_timestamp = reference_day + pd.Timedelta(hours=12)
                current_timestamp = current_day + pd.Timedelta(hours=12)
                engine.current_day = current_day
                engine.levels = [{
                    "day": reference_day,
                    "high": 100.0,
                    "low": 50.0,
                    "high_swept_on": None,
                    "low_swept_on": None,
                    "rsi_near_high": 40.0,
                    "rsi_near_low": 60.0,
                    "high_timestamp": reference_timestamp,
                    "low_timestamp": reference_timestamp,
                    "rsi_near_high_timestamp": reference_timestamp,
                    "rsi_near_low_timestamp": reference_timestamp,
                }]

                engine._detect_divergence(
                    direction="bearish",
                    candidate={
                        "price": 90.0,
                        "timestamp": current_timestamp,
                    },
                    rsi_extreme={
                        "value": 50.0,
                        "timestamp": current_timestamp,
                    },
                    detected_at=current_timestamp + pd.Timedelta(hours=1),
                )

                self.assertEqual(bool(engine.events), should_detect)


if __name__ == "__main__":
    unittest.main()
