import unittest

import pandas as pd

from swing_structure import SwingStructureEngine


class SwingStructureDayBoundaryTests(unittest.TestCase):
    @staticmethod
    def candle(high, low):
        return {
            "open": (high + low) / 2,
            "high": high,
            "low": low,
            "close": (high + low) / 2,
        }

    def test_pivot_window_cannot_cross_utc_midnight(self):
        engine = SwingStructureEngine(
            left_bars=1,
            right_bars=1,
            timeframe_ms=3_600_000,
        )
        times = pd.date_range(
            "2026-01-01 23:00:00+00:00",
            periods=4,
            freq="1h",
        )
        candles = [
            self.candle(10, 8),  # previous day
            self.candle(9, 7),   # new day, first candle
            self.candle(12, 8),  # candidate high
            self.candle(10, 9),  # confirms candidate
        ]

        events = []
        for timestamp, candle in zip(times, candles):
            events.extend(engine.update(timestamp, candle))

        high_events = [
            event for event in events
            if event["event_type"] == "swing_high"
        ]
        self.assertEqual(len(high_events), 1)
        self.assertEqual(high_events[0]["timestamp"], times[2])


if __name__ == "__main__":
    unittest.main()
