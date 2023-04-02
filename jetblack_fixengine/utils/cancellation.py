"""Utilities for handling cancellation"""

import asyncio
from asyncio import AbstractEventLoop, Event, Task
import logging
import signal
from typing import Callable, Optional

LOGGER = logging.getLogger(__name__)


def _cancel(
        signame: str,
        signum: int,
        cancellation_event: Event
) -> None:
    msg = f'received signal {signame}'
    if signum == signal.SIGINT:
        LOGGER.info(msg)
    else:
        LOGGER.warning(msg)
    cancellation_event.set()


def register_cancellation_event(
        cancellation_event: Event,
        loop: AbstractEventLoop
) -> None:
    for signame in ('SIGHUP', 'SIGINT', 'SIGTERM'):
        signum = getattr(signal, signame)
        loop.add_signal_handler(
            signum,
            _cancel,
            signame,
            signum,
            cancellation_event
        )


async def cancel_await(
        task: Task,
        callback: Optional[Callable[[], None]] = None
) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        if callback is not None:
            callback()
