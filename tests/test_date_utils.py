from datetime import time
from aiofix.utils.date_utils import is_dow_in_range, is_time_in_range

MONDAY = 0
TUESDAY = 1
WEDNESDAY = 2
THURSDAY = 3
FRIDAY = 4
SATURDAY = 5
SUNDAY = 6


def test_dow_range():
    assert is_dow_in_range(MONDAY, FRIDAY, MONDAY)
    assert is_dow_in_range(MONDAY, FRIDAY, WEDNESDAY)
    assert is_dow_in_range(MONDAY, FRIDAY, FRIDAY)
    assert not is_dow_in_range(MONDAY, FRIDAY, SATURDAY)

    assert not is_dow_in_range(TUESDAY, THURSDAY, MONDAY)
    assert not is_dow_in_range(TUESDAY, THURSDAY, FRIDAY)

    assert is_dow_in_range(WEDNESDAY, WEDNESDAY, WEDNESDAY)
    assert not is_dow_in_range(WEDNESDAY, WEDNESDAY, TUESDAY)
    assert not is_dow_in_range(WEDNESDAY, WEDNESDAY, THURSDAY)

    assert is_dow_in_range(FRIDAY, TUESDAY, FRIDAY)
    assert is_dow_in_range(FRIDAY, TUESDAY, SUNDAY)
    assert is_dow_in_range(FRIDAY, TUESDAY, TUESDAY)
    assert not is_dow_in_range(FRIDAY, TUESDAY, THURSDAY)
    assert not is_dow_in_range(SATURDAY, SUNDAY, MONDAY)


def test_time_range():
    assert is_time_in_range(time(0, 0, 0), time(17, 30, 0), time(0, 0, 0))
    assert is_time_in_range(time(0, 0, 0), time(17, 30, 0), time(12, 0, 0))
    assert is_time_in_range(time(0, 0, 0), time(17, 30, 0), time(17, 30, 0))
    assert not is_time_in_range(time(0, 0, 0), time(17, 30, 0), time(20, 0, 0))
    assert not is_time_in_range(time(9, 30, 0), time(17, 30, 0), time(0, 0, 0))
