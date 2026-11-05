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
            {"open": 10, "high": 20, "low": 1, "close": 10, "rsi": 40},
            {"open": 10, "high": 19, "low": 2, "close": 10, "rsi": 45},
            {"open": 10, "high": 18, "low": 3, "close": 10, "rsi": 50},
            {"open": 10, "high": 17, "low": 4, "close": 10, "rsi": 55},
        ]

        for position, candle in enumerate(rows):
            timestamp = day + pd.Timedelta(hours=position)
            swings = []
            if position == 2:
                swings.append({
                    "event_type": "swing_high",
                    "timestamp": day + pd.Timedelta(hours=1),
                    "price": 15,
                    "confirmed_at": timestamp + pd.Timedelta(hours=1),
                    "swing_id": "test-high",
                })
            if position == 3:
                swings.append({
                    "event_type": "swing_low",
                    "timestamp": day + pd.Timedelta(hours=2),
                    "price": 5,
                    "confirmed_at": timestamp + pd.Timedelta(hours=1),
                    "swing_id": "test-low",
                })
            engine.update(timestamp, candle, confirmed_swings=swings)

        next_day = day + pd.Timedelta(days=1)
        engine.update(
            next_day,
            {"open": 10, "high": 16, "low": 6, "close": 10, "rsi": 50},
        )

        daily = engine.get_daily_structure()
        self.assertEqual(daily.loc[day, "high"], 15)
        self.assertEqual(daily.loc[day, "low"], 5)
        self.assertEqual(engine.min_reference_days, 2)
        self.assertEqual(engine.max_reference_days, 21)


if __name__ == "__main__":
    unittest.main()
