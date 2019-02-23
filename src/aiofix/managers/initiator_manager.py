import asyncio
import calendar
from datetime import datetime, time, tzinfo
import logging
from ssl import SSLContext
from typing import Optional, Tuple, Callable, Type
from ..meta_data import ProtocolMetaData
from ..transports import InitiatorHandler, create_initiator
from ..types import Store
from ..transports import initiate
from ..utils.date_utils import wait_for_day_of_week, wait_for_time_period
from ..utils.cancellation import register_cancellation_token

logger = logging.getLogger(__name__)

WEEKDAYS = ['Monday', 'Tuesday']


class InitiatorManager:

    def __init__(
            self,
            handler_factory: Callable[[], InitiatorHandler],
            host: str,
            port: int,
            cancellation_token: asyncio.Event,
            *,
            ssl: Optional[SSLContext] = None,
            session_dow_range: Optional[Tuple[int, int]] = None,
            session_time_range: Optional[Tuple[time, time]] = None,
            tz: tzinfo = None
    ) -> None:
        self.handler_factory = handler_factory
        self.host = host
        self.port = port
        self.ssl = ssl
        self.cancellation_token = cancellation_token
        self.session_time_range = session_time_range
        self.session_dow_range = session_dow_range
        self.tz = tz

    async def sleep_until_session_starts(self) -> Optional[datetime]:
        if self.session_dow_range:
            start_dow, end_dow = self.session_dow_range
            logger.info(f'Session from {calendar.day_name[start_dow]} to {calendar.day_name[end_dow]}')
            await wait_for_day_of_week(
                datetime.now(tz=self.tz),
                *self.session_dow_range,
                cancellation_token=self.cancellation_token)

        if self.session_time_range:
            start_time, end_time = self.session_time_range
            logger.info(f'Session from {start_time} to {end_time}')
            end_datetime = await wait_for_time_period(
                datetime.now(tz=self.tz),
                start_time,
                end_time,
                cancellation_token=self.cancellation_token)

            return end_datetime

        return None

    async def start(self, shutdown_timeout: float = 10.0) -> None:
        while not self.cancellation_token.is_set():
            try:
                # Wait for the seeion to start.
                end_datetime = await self.sleep_until_session_starts()
            except asyncio.CancelledError:
                continue

            # Make a new initiator handler
            handler = self.handler_factory()

            try:
                # Start the initiator for the duration of the session.
                session_timeout = (end_datetime - datetime.now(tz=self.tz)).total_seconds() if end_datetime else None
                await asyncio.wait_for(
                    initiate(
                        self.host,
                        self.port,
                        handler,
                        self.cancellation_token,
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
                        [handler, self.cancellation_token.wait()],
                        timeout=10,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                except asyncio.TimeoutError:
                    pass


def start_initator_manager(
        klass: Type[InitiatorHandler],
        host: str,
        port: int,
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: Store,
        heartbeat_timeout: int,
        *,
        ssl: Optional[SSLContext] = None,
        session_dow_range: Optional[Tuple[int, int]] = None,
        session_time_range: Optional[Tuple[time, time]] = None,
        shutdown_timeout: float = 10.0,
        heartbeat_threshold: int = 1,
        logon_time_range: Optional[Tuple[time, time]] = None,
        tz: tzinfo = None
) -> None:
    cancellation_token = asyncio.Event()

    def initiator_factory() -> InitiatorHandler:
        return create_initiator(
            klass,
            protocol,
            sender_comp_id,
            target_comp_id,
            store,
            heartbeat_timeout,
            cancellation_token,
            heartbeat_threshold=heartbeat_threshold,
            logon_time_range=logon_time_range,
            tz=tz
        )

    manager = InitiatorManager(
        initiator_factory,
        host,
        port,
        cancellation_token,
        ssl=ssl,
        session_dow_range=session_dow_range,
        session_time_range=session_time_range
    )

    loop = asyncio.get_event_loop()
    register_cancellation_token(cancellation_token, loop)
    loop.run_until_complete(manager.start(shutdown_timeout))
