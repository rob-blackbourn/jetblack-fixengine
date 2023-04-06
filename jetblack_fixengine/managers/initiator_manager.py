"""An initiator manager"""

import asyncio
import calendar
from datetime import datetime, time, tzinfo
import logging
from ssl import SSLContext
from typing import Callable, Optional, Tuple

from jetblack_fixparser.meta_data import ProtocolMetaData

from ..initiator import InitiatorEngine, initiate
from ..types import Store, FIXApplication
from ..utils.date_utils import wait_for_day_of_week, wait_for_time_period
from ..utils.cancellation import register_cancellation_event

LOGGER = logging.getLogger(__name__)


class InitiatorManager:
    """A class to manage an initiator lifecycle"""

    def __init__(
            self,
            handler_factory: Callable[[], InitiatorEngine],
            host: str,
            port: int,
            cancellation_event: asyncio.Event,
            *,
            ssl: Optional[SSLContext] = None,
            session_dow_range: Optional[Tuple[int, int]] = None,
            session_time_range: Optional[Tuple[time, time]] = None,
            tz: Optional[tzinfo] = None
    ) -> None:
        self.handler_factory = handler_factory
        self.host = host
        self.port = port
        self.ssl = ssl
        self.cancellation_event = cancellation_event
        self.session_time_range = session_time_range
        self.session_dow_range = session_dow_range
        self.tz = tz

    async def sleep_until_session_starts(self) -> Optional[datetime]:
        if self.session_dow_range:
            start_dow, end_dow = self.session_dow_range
            LOGGER.info(
                'Session from %s to %s',
                calendar.day_name[start_dow],
                calendar.day_name[end_dow]
            )
            await wait_for_day_of_week(
                datetime.now(tz=self.tz),
                *self.session_dow_range,
                cancellation_event=self.cancellation_event)

        if self.session_time_range:
            start_time, end_time = self.session_time_range
            LOGGER.info('Session from %s to %s', start_time, end_time)
            end_datetime = await wait_for_time_period(
                datetime.now(tz=self.tz),
                start_time,
                end_time,
                cancellation_event=self.cancellation_event)

            return end_datetime

        return None

    async def start(self, shutdown_timeout: float = 10.0) -> None:
        while not self.cancellation_event.is_set():
            try:
                # Wait for the session to start.
                end_datetime = await self.sleep_until_session_starts()
            except asyncio.CancelledError:
                continue

            # Make a new initiator handler
            handler = self.handler_factory()

            try:
                # Start the initiator for the duration of the session.
                session_timeout = (
                    end_datetime - datetime.now(tz=self.tz)
                ).total_seconds() if end_datetime else None

                await asyncio.wait_for(
                    initiate(
                        self.host,
                        self.port,
                        handler,
                        self.cancellation_event,
                        shutdown_timeout=shutdown_timeout,
                        ssl=self.ssl
                    ),
                    timeout=session_timeout
                )
            except asyncio.TimeoutError:
                # After logout we should disconnect.
                await handler.logout()

                try:
                    await asyncio.wait(
                        [
                            handler.wait_stopped(),
                            self.cancellation_event.wait()
                        ],
                        timeout=10,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                except asyncio.TimeoutError:
                    pass


def start_initiator_manager(
        app: FIXApplication,
        host: str,
        port: int,
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: Store,
        logon_timeout: int,
        heartbeat_timeout: int,
        *,
        ssl: Optional[SSLContext] = None,
        session_dow_range: Optional[Tuple[int, int]] = None,
        session_time_range: Optional[Tuple[time, time]] = None,
        shutdown_timeout: float = 10.0,
        heartbeat_threshold: int = 1,
        logon_time_range: Optional[Tuple[time, time]] = None,
        tz: Optional[tzinfo] = None
) -> None:
    cancellation_event = asyncio.Event()

    def initiator_factory() -> InitiatorEngine:
        return InitiatorEngine(
            app,
            protocol,
            sender_comp_id,
            target_comp_id,
            store,
            logon_timeout,
            heartbeat_timeout,
            cancellation_event,
            heartbeat_threshold=heartbeat_threshold
        )

    manager = InitiatorManager(
        initiator_factory,
        host,
        port,
        cancellation_event,
        ssl=ssl,
        session_dow_range=session_dow_range,
        session_time_range=session_time_range
    )

    loop = asyncio.get_event_loop()
    register_cancellation_event(cancellation_event, loop)
    loop.run_until_complete(manager.start(shutdown_timeout))
