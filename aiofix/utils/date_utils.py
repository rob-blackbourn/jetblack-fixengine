import asyncio
from calendar import day_name
from datetime import datetime, date, time, timedelta, tzinfo
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def is_dow_in_range(start_dow: int, end_dow: int, target_dow: int) -> bool:
    if start_dow <= end_dow:
        return start_dow <= target_dow and target_dow <= end_dow
    else:
        return start_dow <= target_dow or target_dow <= end_dow


def is_time_in_range(start_time: time, end_time: time, target_time: time) -> bool:
    if start_time <= end_time:
        return start_time <= target_time and target_time <= end_time
    else:
        return start_time <= target_time or target_time <= end_time


def make_datetime(d: date, t: time, tz: tzinfo) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, t.microsecond, tzinfo=tz)


def delay_for_time_period(now: datetime, start_time: time, end_time: time) -> Tuple[timedelta, datetime]:
    if start_time < end_time:
        start_datetime = make_datetime(now.date(), start_time, now.tzinfo)
        end_datetime = make_datetime(now.date(), end_time, now.tzinfo)
        if now > end_datetime:
            start_datetime += timedelta(days=1)
            end_datetime += timedelta(days=1)
    else:
        start_datetime = make_datetime(now.date(), start_time, now.tzinfo)
        end_datetime = make_datetime(now.date(), end_time, now.tzinfo) + timedelta(days=1)

    time_to_wait = (start_datetime - now) if now < start_datetime else timedelta(seconds=0)
    return time_to_wait, end_datetime


async def wait_for_day_of_week(now: datetime, start_dow: int, end_dow: int, cancellation_token: asyncio.Event) -> None:
    while not is_dow_in_range(start_dow, end_dow, now.weekday()):
        logger.info(f'Today is {now:%A} - waiting for {day_name[start_dow]} to connect.')
        # Wait a till tomorrow then try again.
        tomorrow = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo) + timedelta(days=1)
        time_to_wait = (tomorrow - now)

        try:
            await asyncio.wait_for(cancellation_token.wait(), time_to_wait.total_seconds())
            raise asyncio.CancelledError
        except asyncio.TimeoutError:
            now += time_to_wait


async def wait_for_time_period(
        now: datetime,
        start_time: time,
        end_time: time,
        cancellation_token: asyncio.Event
) -> datetime:
    # Wait for start time.
    time_to_wait, end_datetime = delay_for_time_period(now, start_time, end_time)
    if time_to_wait.total_seconds() == 0:
        logger.info('No need to wait')
    else:
        logger.info(f'Waiting for {time_to_wait}')
        try:
            await asyncio.wait_for(cancellation_token.wait(), timeout=time_to_wait.total_seconds())
            raise asyncio.CancelledError
        except asyncio.TimeoutError:
            now = datetime.now()

    return end_datetime
