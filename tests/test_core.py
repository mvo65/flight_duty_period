import unittest
from datetime import datetime, timedelta

from flight_duty_period import (
    DutyPeriod,
    DutyResult,
    RestResult,
    calculate_duty,
    calculate_rest,
)


class DutyPeriodValidationTests(unittest.TestCase):
    def test_end_must_be_after_start(self):
        start = datetime(2024, 1, 1, 6, 0)
        with self.assertRaises(ValueError):
            DutyPeriod(start, start, timedelta(hours=1))

    def test_flight_time_cannot_exceed_duty(self):
        start = datetime(2024, 1, 1, 6, 0)
        end = datetime(2024, 1, 1, 10, 0)
        with self.assertRaises(ValueError):
            DutyPeriod(start, end, timedelta(hours=5))

    def test_negative_flight_time_rejected(self):
        start = datetime(2024, 1, 1, 6, 0)
        end = datetime(2024, 1, 1, 10, 0)
        with self.assertRaises(ValueError):
            DutyPeriod(start, end, timedelta(hours=-1))

    def test_naive_datetimes_required(self):
        from datetime import timezone

        aware = datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            DutyPeriod(aware, datetime(2024, 1, 1, 10, 0), timedelta(hours=2))

    def test_sectors_must_be_positive(self):
        start = datetime(2024, 1, 1, 6, 0)
        end = datetime(2024, 1, 1, 10, 0)
        with self.assertRaises(ValueError):
            DutyPeriod(start, end, timedelta(hours=2), sectors=0)

    def test_duty_duration_property(self):
        start = datetime(2024, 1, 1, 6, 0)
        end = datetime(2024, 1, 1, 10, 30)
        dp = DutyPeriod(start, end, timedelta(hours=2))
        self.assertEqual(dp.duty_duration, timedelta(hours=4, minutes=30))


class CalculateDutyTests(unittest.TestCase):
    def _dp(self, hours, flight_hours=None, augmented=False, sectors=1):
        start = datetime(2024, 1, 1, 6, 0)
        end = start + timedelta(hours=hours)
        if flight_hours is None:
            flight_hours = max(0.0, hours - 0.5)
        return DutyPeriod(start, end, timedelta(hours=flight_hours), augmented=augmented, sectors=sectors)

    def test_compliant_single_sector(self):
        dp = self._dp(8, flight_hours=6, sectors=1)
        r = calculate_duty(dp)
        self.assertTrue(r.compliant)
        self.assertEqual(r.max_duty, timedelta(hours=13))
        self.assertEqual(r.remaining, min(timedelta(hours=4), timedelta(hours=5)))
        self.assertEqual(r.remaining, timedelta(hours=4))
        self.assertEqual(r.limiting_factor, "flight_time")

    def test_duty_limit_binding(self):
        dp = self._dp(12, flight_hours=6, sectors=1)
        r = calculate_duty(dp)
        self.assertTrue(r.compliant)
        self.assertEqual(r.remaining, timedelta(hours=1))
        self.assertEqual(r.limiting_factor, "duty_duration")

    def test_flight_time_exceeded(self):
        dp = self._dp(12, flight_hours=11, sectors=1)
        r = calculate_duty(dp)
        self.assertFalse(r.compliant)
        self.assertEqual(r.limiting_factor, "flight_time")
        self.assertEqual(r.remaining, timedelta(0))

    def test_duty_time_exceeded(self):
        dp = self._dp(14, flight_hours=6, sectors=1)
        r = calculate_duty(dp)
        self.assertFalse(r.compliant)
        self.assertEqual(r.limiting_factor, "duty_duration")
        self.assertEqual(r.remaining, timedelta(0))

    def test_augmented_raises_limits(self):
        dp = self._dp(9, flight_hours=8.5, augmented=True, sectors=2)
        r = calculate_duty(dp)
        self.assertTrue(r.compliant)
        self.assertEqual(r.max_duty, timedelta(hours=13, minutes=30))
        self.assertEqual(r.limiting_factor, "flight_time")
        self.assertEqual(r.remaining, timedelta(hours=4, minutes=30))

    def test_return_type_is_duty_result(self):
        dp = self._dp(8, flight_hours=6, sectors=1)
        r = calculate_duty(dp)
        self.assertIsInstance(r, DutyResult)


class CalculateRestTests(unittest.TestCase):
    def _dp(self, hours):
        start = datetime(2024, 1, 1, 6, 0)
        return DutyPeriod(start, start + timedelta(hours=hours), timedelta(hours=max(0, hours - 1)))

    def test_short_duty_gets_ten_hour_floor(self):
        dp = self._dp(6)
        r = calculate_rest(dp, timedelta(hours=10))
        self.assertTrue(r.compliant)
        self.assertEqual(r.required_rest, timedelta(hours=10))
        self.assertIsInstance(r, RestResult)

    def test_short_duty_insufficient_rest(self):
        dp = self._dp(6)
        r = calculate_rest(dp, timedelta(hours=9, minutes=59))
        self.assertFalse(r.compliant)
        self.assertEqual(r.required_rest, timedelta(hours=10))

    def test_long_duty_requires_duty_plus_two(self):
        dp = self._dp(12)
        r = calculate_rest(dp, timedelta(hours=14))
        self.assertTrue(r.compliant)
        self.assertEqual(r.required_rest, timedelta(hours=14))

    def test_long_duty_insufficient_rest(self):
        dp = self._dp(11)
        r = calculate_rest(dp, timedelta(hours=12, minutes=59))
        self.assertFalse(r.compliant)
        self.assertEqual(r.required_rest, timedelta(hours=13))

    def test_zero_rest_rejected(self):
        dp = self._dp(6)
        with self.assertRaises(ValueError):
            calculate_rest(dp, timedelta(0))

    def test_negative_rest_rejected(self):
        dp = self._dp(6)
        with self.assertRaises(ValueError):
            calculate_rest(dp, timedelta(hours=-1))

    def test_boundary_exactly_ten_hours_duty(self):
        dp = self._dp(10)
        r = calculate_rest(dp, timedelta(hours=12))
        self.assertTrue(r.compliant)
        self.assertEqual(r.required_rest, timedelta(hours=12))

    def test_boundary_exactly_required_rest(self):
        dp = self._dp(10)
        r = calculate_rest(dp, timedelta(hours=12))
        self.assertTrue(r.compliant)


if __name__ == "__main__":
    unittest.main()
