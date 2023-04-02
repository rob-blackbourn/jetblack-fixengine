"""Date Utils"""

import asyncio
from asyncio import Event
from calendar import day_name
from datetime import datetime, time, timedelta
import logging
from typing import Tuple

LOGGER = logging.getLogger(__name__)


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


def delay_for_time_period(
        now: datetime,
        start_time: time,
        end_time: time
) -> Tuple[timedelta, datetime]:
    if start_time < end_time:
        start_datetime = datetime.combine(now.date(), start_time, now.tzinfo)
        end_datetime = datetime.combine(now.date(), end_time, now.tzinfo)
        if now > end_datetime:
            start_datetime += timedelta(days=1)
            end_datetime += timedelta(days=1)
    else:
        start_datetime = datetime.combine(now.date(), start_time, now.tzinfo)
        end_datetime = datetime.combine(
            now.date(),
            end_time,
            now.tzinfo
        ) + timedelta(days=1)

    time_to_wait = (start_datetime -
                    now) if now < start_datetime else timedelta(seconds=0)
    return time_to_wait, end_datetime


async def wait_for_day_of_week(
        now: datetime,
        start_dow: int,
        end_dow: int,
        cancellation_event: Event
) -> None:
    while not is_dow_in_range(start_dow, end_dow, now.weekday()):
        LOGGER.info(
            'Today is %s - waiting for %s to connect.',
            now.strftime("%A"),
            day_name[start_dow]
        )
        # Wait a till tomorrow then try again.
        tomorrow = datetime(now.year, now.month, now.day,
                            tzinfo=now.tzinfo) + timedelta(days=1)
        time_to_wait = (tomorrow - now)

        try:
            await asyncio.wait_for(
                cancellation_event.wait(),
                time_to_wait.total_seconds()
            )
            raise asyncio.CancelledError
        except asyncio.TimeoutError:
            now += time_to_wait


async def wait_for_time_period(
        now: datetime,
        start_time: time,
        end_time: time,
        cancellation_event: Event
) -> datetime:
    # Wait for start time.
    time_to_wait, end_datetime = delay_for_time_period(
        now,
        start_time,
        end_time
    )
    if time_to_wait.total_seconds() == 0:
        LOGGER.info('No need to wait')
    else:
        LOGGER.info('Waiting for %s', time_to_wait)
        try:
            await asyncio.wait_for(
                cancellation_event.wait(),
                timeout=time_to_wait.total_seconds()
            )
            raise asyncio.CancelledError
        except asyncio.TimeoutError:
            pass

    return end_datetime
