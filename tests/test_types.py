from datetime import datetime

from ytpb.types import DateInterval


class TestDateInterval:
    interval = DateInterval(datetime(2023, 12, 10, 1), datetime(2023, 12, 10, 2))

    def test_duration(self):
        assert self.interval.duration == 60 * 60

    def test_substraction_of_intervals(self):
        other = DateInterval(
            datetime(2023, 12, 10, 0, 50), datetime(2023, 12, 10, 2, 10)
        )
        assert self.interval - other == (10 * 60, -10 * 60)
        assert other - self.interval == (-10 * 60, 10 * 60)

    def test_date_inside_interval(self):
        assert datetime(2023, 12, 10, 1, 30) in self.interval
        assert datetime(2023, 12, 10, 1) in self.interval

    def test_interval_is_subinterval(self):
        assert self.interval.is_subinterval(
            DateInterval(datetime(2023, 12, 10, 0, 50), datetime(2023, 12, 10, 2, 10))
        )
        assert not self.interval.is_subinterval(
            DateInterval(datetime(2023, 12, 10, 1, 10), datetime(2023, 12, 10, 1, 50))
        )
