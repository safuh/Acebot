import unittest

import pandas as pd

from features_updated import drop_leading_partial_day


class DropLeadingPartialDayTests(unittest.TestCase):
    def test_drops_partial_first_day_and_keeps_first_complete_day(self):
        partial = pd.date_range(
            "2026-01-01 01:00:00+00:00",
            "2026-01-01 23:00:00+00:00",
            freq="1h",
        )
        complete = pd.date_range(
            "2026-01-02 00:00:00+00:00",
            periods=24,
            freq="1h",
        )
        index = partial.append(complete)
        frame = pd.DataFrame(
            {"close": range(len(index))},
            index=index,
        )

        result = drop_leading_partial_day(frame, 3_600_000)

        self.assertEqual(result.index[0], complete[0])
        self.assertEqual(len(result.loc["2026-01-02"]), 24)

    def test_raises_when_no_complete_day_exists(self):
        index = pd.date_range(
            "2026-01-01 01:00:00+00:00",
            "2026-01-01 23:00:00+00:00",
            freq="1h",
        )
        frame = pd.DataFrame({"close": range(len(index))}, index=index)

        with self.assertRaises(ValueError):
            drop_leading_partial_day(frame, 3_600_000)


if __name__ == "__main__":
    unittest.main()
