import asyncio
from calendar import day_name
from datetime import datetime, timedelta, time
import logging
from ssl import SSLContext
from typing import Optional, Tuple, Callable
from ..meta_data import ProtocolMetaData
from ..transports import InitiatorHandler
from ..middlewares import FixMessageMiddleware, mw
from ..types import InitiatorStore
from ..transports import initiate
from ..utils.date_utils import is_dow_in_range, is_time_in_range
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
            logon_time_range: Optional[Tuple[time, time]] = None
    ) -> None:
        if session_time_range:
            if len(session_time_range) != 2:
                raise RuntimeError('session_time_range must be a tuple of start and end time')
            self.session_start, self.session_end = session_time_range
        else:
            self.session_start, self.session_end = None, None

        if session_dow_range:
            if len(session_dow_range) != 2:
                raise RuntimeError('session_dow_range must be a tuple of start and end day of week')
            self.session_start_dow, self.session_end_dow = session_dow_range
        else:
            self.session_start_dow, self.session_end_dow = None, None

        if logon_time_range:
            if len(logon_time_range) != 2:
                raise RuntimeError('logon_time_range must be a tuple of start and end time')
            self.logon_start, self.logon_end = logon_time_range
        else:
            self.logon_start, self.logon_end = None, None

        self.handler_factory = handler_factory
        self.host = host
        self.port = port
        self.ssl = ssl
        self.cancellation_token = cancellation_token

    async def sleep_until_session_starts(self) -> Optional[float]:
        now = datetime.now()

        # Wait for valid weekday.
        if self.session_start_dow is not None and self.session_end_dow is not None:
            while not is_dow_in_range(self.session_start_dow, self.session_end_dow, now.weekday()):
                logger.info(f'Today is {now:%A} - waiting for {day_name[self.session_start_dow]} to connect.')
                # Wait a till tomorrow then try again.
                tomorrow = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo) + timedelta(days=1)
                seconds_till_tomorrow = (tomorrow - now).total_seconds()

                try:
                    await asyncio.wait_for(self.cancellation_token.wait(), seconds_till_tomorrow)
                    raise asyncio.CancelledError
                except asyncio.TimeoutError:
                    now = datetime.now()

        # Wait for session start time.
        if self.session_start is not None and self.session_end is not None:
            while is_time_in_range(self.session_start, self.session_end, now.time()):
                logger.info(f'Time is {now:%H:%M:%S} - waiting for {self.session_start_dow:%H:%M:%S}')
                # Wait till start time
                if now.time() < self.session_start:
                    seconds_till_start_time = (self.session_start - now.time()).total_seconds()
                else:
                    tomorrow = now.date() + timedelta(days=1)
                    tomorrow_session_start = tomorrow + self.session_start
                    seconds_till_start_time = (tomorrow_session_start - now).total_seconds()

                try:
                    await asyncio.wait_for(self.cancellation_token, seconds_till_start_time)
                    raise asyncio.CancelledError
                except asyncio.TimeoutError:
                    now = datetime.now()

        if self.session_end is None:
            return None

        session_end = datetime(
            now.year, now.month, now.day,
            self.session_end.hour, self.session_end.minute, self.session_end.second, self.session_end.microsecond,
            tzinfo=now.tzinfo)
        return (session_end - now).total_seconds()

    async def start(self, shutdown_timeout: float = 10.0) -> None:
        while not self.cancellation_token.is_set():
            try:
                # Wait for the seeion to start.
                seconds_till_session_ends = await self.sleep_until_session_starts()
            except asyncio.CancelledError:
                continue

            # Make a new initiator handler
            handler = self.handler_factory()

            try:
                # Start the initiator for the duration of the session.
                await asyncio.wait_for(
                    initiate(
                        self.host,
                        self.port,
                        handler,
                        self.cancellation_token,
                        shutdown_timeout=shutdown_timeout,
                        ssl=self.ssl
                    ),
                    timeout=seconds_till_session_ends
                )
            except asyncio.TimeoutError:
                # After logout we should disconnect.
                await handler.logout()
                try:
                    await asyncio.wait(
                        [handler(), self.cancellation_token.wait()],
                        timeout=10,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                except asyncio.TimeoutError:
                    pass


def start_initator_manager(
        host: str,
        port: int,
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: InitiatorStore,
        *,
        ssl: Optional[SSLContext] = None,
        heartbeat_timeout: int = 30,
        session_dow_range: Optional[Tuple[int, int]] = None,
        session_time_range: Optional[Tuple[time, time]] = None,
        logon_time_range: Optional[Tuple[time, time]] = None,
        shutdown_timeout: float = 10.0
) -> None:
    cancellation_token = asyncio.Event()

    def initiator_handler_factory() -> InitiatorHandler:
        initator_handler = InitiatorHandler(
            protocol,
            sender_comp_id,
            target_comp_id,
            store,
            heartbeat_timeout=heartbeat_timeout)
        middleware = FixMessageMiddleware(protocol)
        handler: InitiatorHandler = mw([middleware], handler=initator_handler)
        return handler

    manager = InitiatorManager(
        initiator_handler_factory,
        host,
        port,
        cancellation_token,
        ssl=ssl,
        session_dow_range=session_dow_range,
        session_time_range=session_time_range,
        logon_time_range=logon_time_range
    )

    loop = asyncio.get_event_loop()
    register_cancellation_token(cancellation_token, loop)
    loop.run_until_complete(manager.start(shutdown_timeout))
