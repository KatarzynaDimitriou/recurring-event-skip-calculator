import unittest
from datetime import date

from recurring_event_skip_calculator import (
    RecurrenceRule,
    SkipResult,
    calculate_skipped,
)
from recurring_event_skip_calculator.core import Frequency


class TestDaily(unittest.TestCase):
    def test_basic_range(self):
        rule = RecurrenceRule(
            frequency=Frequency.DAILY,
            start_date=date(2024, 1, 1),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 1, 3), date(2024, 1, 6))
        # Jan 3, 4, 5 are inside [Jan 3, Jan 6)
        self.assertEqual(result.count, 3)
        self.assertEqual(result.first_skipped, date(2024, 1, 3))
        self.assertEqual(result.last_skipped, date(2024, 1, 5))

    def test_half_open_excludes_end(self):
        rule = RecurrenceRule(
            frequency=Frequency.DAILY,
            start_date=date(2024, 1, 1),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 1, 3), date(2024, 1, 4))
        self.assertEqual(result.count, 1)
        self.assertEqual(result.first_skipped, date(2024, 1, 3))
        self.assertEqual(result.last_skipped, date(2024, 1, 3))

    def test_empty_range(self):
        rule = RecurrenceRule(
            frequency=Frequency.DAILY,
            start_date=date(2024, 1, 1),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 1, 3), date(2024, 1, 3))
        self.assertEqual(result.count, 0)
        self.assertIsNone(result.first_skipped)
        self.assertIsNone(result.last_skipped)

    def test_range_before_start(self):
        rule = RecurrenceRule(
            frequency=Frequency.DAILY,
            start_date=date(2024, 1, 10),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 1, 1), date(2024, 1, 5))
        self.assertEqual(result.count, 0)

    def test_interval_3(self):
        rule = RecurrenceRule(
            frequency=Frequency.DAILY,
            start_date=date(2024, 1, 1),
            interval=3,
        )
        # Occurrences: Jan 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31
        result = calculate_skipped(rule, date(2024, 1, 5), date(2024, 1, 20))
        # Jan 7, 10, 13, 16, 19 -> 5
        self.assertEqual(result.count, 5)
        self.assertEqual(result.first_skipped, date(2024, 1, 7))
        self.assertEqual(result.last_skipped, date(2024, 1, 19))

    def test_start_inside_range(self):
        rule = RecurrenceRule(
            frequency=Frequency.DAILY,
            start_date=date(2024, 1, 5),
            interval=2,
        )
        result = calculate_skipped(rule, date(2024, 1, 1), date(2024, 1, 12))
        # Jan 5, 7, 9, 11 -> 4
        self.assertEqual(result.count, 4)
        self.assertEqual(result.first_skipped, date(2024, 1, 5))
        self.assertEqual(result.last_skipped, date(2024, 1, 11))


class TestWeekly(unittest.TestCase):
    def test_every_monday(self):
        # 2024-01-01 is a Monday
        rule = RecurrenceRule(
            frequency=Frequency.WEEKLY,
            start_date=date(2024, 1, 1),
            interval=1,
            weekdays=(0,),
        )
        result = calculate_skipped(rule, date(2024, 1, 8), date(2024, 1, 30))
        # Mondays: Jan 8, 15, 22, 29 -> 4
        self.assertEqual(result.count, 4)
        self.assertEqual(result.first_skipped, date(2024, 1, 8))
        self.assertEqual(result.last_skipped, date(2024, 1, 29))

    def test_mon_and_fri(self):
        # 2024-01-01 is Monday
        rule = RecurrenceRule(
            frequency=Frequency.WEEKLY,
            start_date=date(2024, 1, 1),
            interval=1,
            weekdays=(0, 4),
        )
        result = calculate_skipped(rule, date(2024, 1, 3), date(2024, 1, 16))
        # Fri Jan 5, Mon Jan 8, Fri Jan 12, Mon Jan 15 -> 4
        self.assertEqual(result.count, 4)
        self.assertEqual(result.first_skipped, date(2024, 1, 5))
        self.assertEqual(result.last_skipped, date(2024, 1, 15))

    def test_biweekly(self):
        # 2024-01-01 is Monday, interval=2
        rule = RecurrenceRule(
            frequency=Frequency.WEEKLY,
            start_date=date(2024, 1, 1),
            interval=2,
            weekdays=(0,),
        )
        # Mondays: Jan 1, Jan 15, Jan 29, Feb 12
        result = calculate_skipped(rule, date(2024, 1, 10), date(2024, 2, 1))
        # Jan 15, Jan 29 -> 2
        self.assertEqual(result.count, 2)
        self.assertEqual(result.first_skipped, date(2024, 1, 15))
        self.assertEqual(result.last_skipped, date(2024, 1, 29))

    def test_weekly_empty_range(self):
        rule = RecurrenceRule(
            frequency=Frequency.WEEKLY,
            start_date=date(2024, 1, 1),
            interval=1,
            weekdays=(0,),
        )
        result = calculate_skipped(rule, date(2024, 1, 2), date(2024, 1, 7))
        # Monday Jan 8 is outside; Jan 1 is before range
        self.assertEqual(result.count, 0)
        self.assertIsNone(result.first_skipped)
        self.assertIsNone(result.last_skipped)

    def test_weekly_start_inside_range(self):
        # 2024-01-03 is Wednesday
        rule = RecurrenceRule(
            frequency=Frequency.WEEKLY,
            start_date=date(2024, 1, 3),
            interval=1,
            weekdays=(2,),
        )
        result = calculate_skipped(rule, date(2024, 1, 1), date(2024, 2, 1))
        # Wednesdays: Jan 3, 10, 17, 24, 31 -> 5
        self.assertEqual(result.count, 5)
        self.assertEqual(result.first_skipped, date(2024, 1, 3))
        self.assertEqual(result.last_skipped, date(2024, 1, 31))


class TestMonthly(unittest.TestCase):
    def test_basic(self):
        rule = RecurrenceRule(
            frequency=Frequency.MONTHLY,
            start_date=date(2024, 1, 15),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 2, 1), date(2024, 5, 1))
        # Feb 15, Mar 15, Apr 15 -> 3
        self.assertEqual(result.count, 3)
        self.assertEqual(result.first_skipped, date(2024, 2, 15))
        self.assertEqual(result.last_skipped, date(2024, 4, 15))

    def test_clamped_day_31(self):
        rule = RecurrenceRule(
            frequency=Frequency.MONTHLY,
            start_date=date(2024, 1, 31),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 2, 1), date(2024, 5, 1))
        # Feb 29 (leap year), Mar 31, Apr 30 -> 3
        self.assertEqual(result.count, 3)
        self.assertEqual(result.first_skipped, date(2024, 2, 29))
        self.assertEqual(result.last_skipped, date(2024, 4, 30))

    def test_interval_3(self):
        rule = RecurrenceRule(
            frequency=Frequency.MONTHLY,
            start_date=date(2024, 1, 10),
            interval=3,
        )
        # Jan 10, Apr 10, Jul 10, Oct 10
        result = calculate_skipped(rule, date(2024, 3, 1), date(2024, 11, 1))
        # Apr 10, Jul 10, Oct 10 -> 3
        self.assertEqual(result.count, 3)
        self.assertEqual(result.first_skipped, date(2024, 4, 10))
        self.assertEqual(result.last_skipped, date(2024, 10, 10))

    def test_monthly_empty_range(self):
        rule = RecurrenceRule(
            frequency=Frequency.MONTHLY,
            start_date=date(2024, 1, 15),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 2, 16), date(2024, 3, 14))
        self.assertEqual(result.count, 0)
        self.assertIsNone(result.first_skipped)
        self.assertIsNone(result.last_skipped)

    def test_monthly_start_inside_range(self):
        rule = RecurrenceRule(
            frequency=Frequency.MONTHLY,
            start_date=date(2024, 1, 10),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 1, 1), date(2024, 4, 1))
        # Jan 10, Feb 10, Mar 10 -> 3
        self.assertEqual(result.count, 3)
        self.assertEqual(result.first_skipped, date(2024, 1, 10))
        self.assertEqual(result.last_skipped, date(2024, 3, 10))


class TestValidation(unittest.TestCase):
    def test_interval_below_one(self):
        with self.assertRaises(ValueError):
            RecurrenceRule(
                frequency=Frequency.DAILY,
                start_date=date(2024, 1, 1),
                interval=0,
            )

    def test_weekly_requires_weekdays(self):
        with self.assertRaises(ValueError):
            RecurrenceRule(
                frequency=Frequency.WEEKLY,
                start_date=date(2024, 1, 1),
                interval=1,
                weekdays=(),
            )

    def test_weekday_out_of_range(self):
        with self.assertRaises(ValueError):
            RecurrenceRule(
                frequency=Frequency.WEEKLY,
                start_date=date(2024, 1, 1),
                interval=1,
                weekdays=(7,),
            )

    def test_miss_end_before_start(self):
        rule = RecurrenceRule(
            frequency=Frequency.DAILY,
            start_date=date(2024, 1, 1),
            interval=1,
        )
        with self.assertRaises(ValueError):
            calculate_skipped(rule, date(2024, 1, 10), date(2024, 1, 5))

    def test_result_type(self):
        rule = RecurrenceRule(
            frequency=Frequency.DAILY,
            start_date=date(2024, 1, 1),
            interval=1,
        )
        result = calculate_skipped(rule, date(2024, 1, 1), date(2024, 1, 4))
        self.assertIsInstance(result, SkipResult)


if __name__ == "__main__":
    unittest.main()
