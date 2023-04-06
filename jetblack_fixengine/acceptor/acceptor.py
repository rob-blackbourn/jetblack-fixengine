"""An acceptor"""

import asyncio
from datetime import datetime, time, tzinfo, timezone
import logging
from typing import (
    Mapping,
    Any,
    Optional,
    Tuple,
    Union,
)

from jetblack_fixparser.fix_message import FixMessageFactory
from jetblack_fixparser.meta_data import ProtocolMetaData

from ..admin import (
    AdminState,
    AdminEvent,
    AdminMessage,
)
from ..time_provider import TimeProvider, DefaultTimeProvider
from ..transports import (
    TransportState,
    TransportEvent,
    TransportMessage,
    TransportStateMachine,
    Send,
    Receive
)
from ..types import Store, Session, FIXApplication

from .state_machine import AcceptorAdminStateMachine
from .types import AbstractAcceptorEngine

LOGGER = logging.getLogger(__name__)


class AcceptorEngine(AbstractAcceptorEngine):
    """The base class for acceptor handlers"""

    def __init__(
            self,
            app: FIXApplication,
            protocol: ProtocolMetaData,
            sender_comp_id: str,
            target_comp_id: str,
            store: Store,
            heartbeat_timeout: int,
            cancellation_event: asyncio.Event,
            *,
            heartbeat_threshold: int = 1,
            logon_time_range: Optional[Tuple[time, time]] = None,
            logon_timeout: Union[float, int] = 60,
            tz: Optional[tzinfo] = None,
            time_provider: Optional[TimeProvider] = None
    ) -> None:
        self.protocol = protocol
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self._heartbeat_timeout = heartbeat_timeout
        self._heartbeat_threshold = heartbeat_threshold
        self.cancellation_event = cancellation_event
        self._logon_time_range = logon_time_range
        self.logon_timeout = logon_timeout
        self._tz = tz
        self.time_provider = time_provider or DefaultTimeProvider()
        self._fix_message_factory = FixMessageFactory(
            protocol,
            sender_comp_id,
            target_comp_id
        )

        self._last_send_time_utc: Optional[datetime] = None
        self._store = store
        self._session = self._store.get_session(sender_comp_id, target_comp_id)
        self._send: Optional[Send] = None
        self._receive: Optional[Receive] = None
        self._logout_time: Optional[datetime] = None

        self._admin_state_machine = AcceptorAdminStateMachine(
            self,
            app,
            self.time_provider,
            self.cancellation_event
        )
        self._transport_state_machine = TransportStateMachine(
            self,
            app,
            self._admin_state_machine,
            self.time_provider
        )

    @property
    def session(self) -> Session:
        return self._session

    @property
    def fix_message_factory(self) -> FixMessageFactory:
        return self._fix_message_factory

    @property
    def heartbeat_timeout(self) -> int:
        return self._heartbeat_timeout

    @property
    def heartbeat_threshold(self) -> int:
        return self._heartbeat_threshold

    @property
    def logon_time_range(self) -> Optional[Tuple[time, time]]:
        return self._logon_time_range

    @property
    def logout_time(self) -> Optional[datetime]:
        return self._logout_time

    @logout_time.setter
    def logout_time(self, value: datetime) -> None:
        self._logout_time = value

    @property
    def tz(self) -> Optional[tzinfo]:
        return self._tz

    async def _handle_error(
            self,
            transport_message: TransportMessage
    ) -> None:
        LOGGER.warning('error: %s', transport_message)

    async def _next_transport_message(
            self,
            receive: Receive
    ) -> TransportMessage:
        try:
            timeout = await self._send_heartbeat_if_required()
            return await asyncio.wait_for(receive(), timeout=timeout)
        except asyncio.TimeoutError:
            return TransportMessage(TransportEvent.TIMEOUT_RECEIVED)

    async def __call__(
            self,
            send: Send,
            receive: Receive
    ) -> None:
        self._send, self._receive = send, receive

        while True:
            await self._send_logout_if_login_expired(self._logout_time)
            transport_message = await self._next_transport_message(receive)
            await self._transport_state_machine.process(transport_message)
            if self._transport_state_machine.state != TransportState.CONNECTED:
                break

        LOGGER.info('disconnected')

    async def _send_logout_if_login_expired(
            self,
            logout_time: Optional[datetime]
    ) -> None:
        if self._admin_state_machine.state != AdminState.AUTHENTICATED or not logout_time:
            return

        # Is it time to logout?
        if self.time_provider.now(self._tz or timezone.utc) >= logout_time:
            await self._admin_state_machine.process(
                AdminMessage(AdminEvent.SEND_LOGOUT)
            )

    async def _send_heartbeat_if_required(self) -> float:
        if (
                self._transport_state_machine.state != TransportState.CONNECTED
                or self._last_send_time_utc is None
        ):
            return self.logon_timeout

        now_utc = self.time_provider.now(timezone.utc)
        seconds_since_last_send = (
            now_utc - self._last_send_time_utc
        ).total_seconds()
        if (
                seconds_since_last_send >= self._heartbeat_timeout and
                self._admin_state_machine.state == AdminState.AUTHENTICATED
        ):
            await self.send_message('HEARTBEAT')
            seconds_since_last_send = 0

        seconds_till_next_heartbeat = self._heartbeat_timeout - seconds_since_last_send

        return seconds_till_next_heartbeat

    async def _next_outgoing_seqnum(self) -> int:
        seqnum = await self._session.get_outgoing_seqnum()
        seqnum += 1
        await self._session.set_outgoing_seqnum(seqnum)
        return seqnum

    async def _set_seqnums(
            self,
            outgoing_seqnum: int,
            incoming_seqnum: int
    ) -> None:
        await self._session.set_seqnums(outgoing_seqnum, incoming_seqnum)

    async def _send_transport_message(
            self,
            transport_message: TransportMessage,
            send_time_utc: datetime
    ) -> None:
        if self._send is None:
            raise ValueError("Not connected")
        await self._send(transport_message)
        self._last_send_time_utc = send_time_utc

    async def send_message(
            self,
            msg_type: str,
            message: Optional[Mapping[str, Any]] = None
    ) -> None:
        """Send a FIX message

        Args:
            msg_type (str): The message type.
            message (Optional[Mapping[str, Any]], optional): The message.
                Defaults to None.
        """
        send_time_utc = self.time_provider.now(timezone.utc)
        msg_seq_num = await self._next_outgoing_seqnum()
        fix_message = self.fix_message_factory.create(
            msg_type,
            msg_seq_num,
            send_time_utc,
            message
        )
        LOGGER.info('Sending %s', fix_message.message)

        buffer = fix_message.encode(regenerate_integrity=True)
        transport_message = TransportMessage(
            TransportEvent.FIX_RECEIVED,
            buffer
        )
        await self._send_transport_message(transport_message, send_time_utc)

    async def send_resend_request(
            self,
            begin_seqnum: int,
            end_seqnum: int = 0
    ) -> None:
        """Send a resend request.

        Args:
            begin_seqnum (int): The begin seqnum
            end_seqnum (int, optional): An optional end seqnum. Defaults to 0.
        """
        await self.send_message(
            'RESEND_REQUEST',
            {
                'BeginSeqNo': begin_seqnum,
                'EndSeqNo': end_seqnum
            }
        )
