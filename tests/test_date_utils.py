"""Tests for date utils"""

from datetime import time, datetime

import pytz

from aiofix.utils.date_utils import (
    is_dow_in_range,
    is_time_in_range,
    delay_for_time_period
)

MONDAY = 0
TUESDAY = 1
WEDNESDAY = 2
THURSDAY = 3
FRIDAY = 4
SATURDAY = 5
SUNDAY = 6


def test_dow_range():
    """Test day of week range"""
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
    """Test time range"""
    assert is_time_in_range(time(0, 0, 0), time(17, 30, 0), time(0, 0, 0))
    assert is_time_in_range(time(0, 0, 0), time(17, 30, 0), time(12, 0, 0))
    assert is_time_in_range(time(0, 0, 0), time(17, 30, 0), time(17, 30, 0))
    assert not is_time_in_range(time(0, 0, 0), time(17, 30, 0), time(20, 0, 0))
    assert not is_time_in_range(time(9, 30, 0), time(17, 30, 0), time(0, 0, 0))


def test_seconds_for_period():
    """Test seconds in a period"""
    # now=6am, star=8am, end=4pm
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 1, 1, 6, 0, 0),
        time(8, 0, 0),
        time(16, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 2
    assert end_datetime == datetime(2019, 1, 1, 16, 0, 0)

    # now=10am, start=8am, end=4pm
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 1, 1, 10, 0, 0),
        time(8, 0, 0),
        time(16, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 0
    assert end_datetime == datetime(2019, 1, 1, 16, 0, 0)

    # now=6pm, start=8am, end=4pm
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 1, 1, 18, 0, 0),
        time(8, 0, 0),
        time(16, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 14
    assert end_datetime == datetime(2019, 1, 2, 16, 0, 0)

    # now=6pm,start=8pm, end=4am
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 1, 1, 18, 0, 0),
        time(20, 0, 0),
        time(4, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 2
    assert end_datetime == datetime(2019, 1, 2, 4, 0, 0)

    # now=10pm,start=8pm, end=4am
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 1, 1, 22, 0, 0),
        time(20, 0, 0),
        time(4, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 0
    assert end_datetime == datetime(2019, 1, 2, 4, 0, 0)

    # now=6am,start=8pm, end=4am
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 1, 1, 6, 0, 0),
        time(20, 0, 0),
        time(4, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 14
    assert end_datetime == datetime(2019, 1, 2, 4, 0, 0)

    london = pytz.timezone('Europe/London')

    # now=6pm,start=8pm, end=4am, London clocks forward.
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 3, 31, 18, 0, 0, tzinfo=london),
        time(20, 0, 0),
        time(4, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 2
    assert end_datetime == datetime(2019, 4, 1, 4, 0, 0, tzinfo=london)

    # now=10pm,start=8pm, end=4am
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 3, 31, 22, 0, 0, tzinfo=london),
        time(20, 0, 0),
        time(4, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 0
    assert end_datetime == datetime(2019, 4, 1, 4, 0, 0, tzinfo=london)

    # now=6am,start=8pm, end=4am
    time_to_wait, end_datetime = delay_for_time_period(
        datetime(2019, 3, 31, 6, 0, 0, tzinfo=london),
        time(20, 0, 0),
        time(4, 0, 0))
    assert time_to_wait.total_seconds() / 60 / 60 == 14
    assert end_datetime == datetime(2019, 4, 1, 4, 0, 0, tzinfo=london)
