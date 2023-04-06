"""An Initiator"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Mapping, Any, Optional

from jetblack_fixparser.fix_message import FixMessageFactory
from jetblack_fixparser.meta_data import ProtocolMetaData

from ..admin import (
    AdminState,
)
from ..time_provider import TimeProvider, DefaultTimeProvider
from ..transports import (
    TransportState,
    TransportEvent,
    TransportMessage,
    TransportStateMachine,
    Send,
    Receive,
)
from ..types import Store, Session, FIXApplication

from .state_machine import InitiatorAdminStateMachine
from .types import AbstractInitiatorEngine

LOGGER = logging.getLogger(__name__)


class InitiatorEngine(AbstractInitiatorEngine):
    """The base class for initiator handlers"""

    def __init__(
            self,
            app: FIXApplication,
            protocol: ProtocolMetaData,
            sender_comp_id: str,
            target_comp_id: str,
            store: Store,
            logon_timeout: int,
            heartbeat_timeout: int,
            cancellation_event: asyncio.Event,
            *,
            heartbeat_threshold: int = 1,
            time_provider: Optional[TimeProvider] = None
    ) -> None:
        self.logon_timeout = logon_timeout
        self._heartbeat_timeout = heartbeat_timeout
        self._heartbeat_threshold = heartbeat_threshold
        self._cancellation_event = cancellation_event
        self._fix_message_factory = FixMessageFactory(
            protocol,
            sender_comp_id,
            target_comp_id
        )
        self._time_provider = time_provider or DefaultTimeProvider()

        self._last_send_time_utc = self._time_provider.min(timezone.utc)
        self._session = store.get_session(sender_comp_id, target_comp_id)
        self._send: Optional[Send] = None
        self._receive: Optional[Receive] = None
        self._timeout = float(heartbeat_timeout)

        self._admin_state_machine = InitiatorAdminStateMachine(
            self,
            app,
        )
        self._transport_state_machine = TransportStateMachine(
            self,
            app,
            self._admin_state_machine,
            self._time_provider,
        )

        self._stop_event = asyncio.Event()

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

    async def _next_outgoing_seqnum(self) -> int:
        seqnum = await self._session.get_outgoing_seqnum()
        seqnum += 1
        await self._session.set_outgoing_seqnum(seqnum)
        return seqnum

    async def _send_transport_message(
            self,
            transport_message: TransportMessage,
            send_time_utc: datetime
    ) -> None:
        if self._send is None:
            raise ValueError('Not connected')
        await self._send(transport_message)
        self._last_send_time_utc = send_time_utc

    async def _handle_error(
            self,
            transport_message: TransportMessage
    ) -> None:
        LOGGER.warning('error: %s', transport_message)

    async def _send_heartbeat_if_required(self) -> None:
        if self._transport_state_machine.state != TransportState.CONNECTED:
            self._timeout = self.logon_timeout
            return

        now_utc = self._time_provider.now(timezone.utc)
        seconds_since_last_send = (
            now_utc - self._last_send_time_utc
        ).total_seconds()
        if (
                seconds_since_last_send >= self._heartbeat_timeout and
                self._admin_state_machine.state == AdminState.AUTHENTICATED
        ):
            await self.send_message('HEARTBEAT')
            seconds_since_last_send = 0

        self._timeout = self._heartbeat_timeout - seconds_since_last_send

    async def _next_message(
            self,
            receive: Receive
    ) -> TransportMessage:
        try:
            await self._send_heartbeat_if_required()
            message = await asyncio.wait_for(
                receive(),
                timeout=self._timeout
            )
            return message
        except asyncio.TimeoutError:
            return TransportMessage(TransportEvent.TIMEOUT_RECEIVED)

    async def __call__(
            self,
            send: Send,
            receive: Receive
    ) -> None:
        self._send, self._receive = send, receive

        while True:
            message = await self._next_message(receive)
            await self._transport_state_machine.process(message)
            if self._transport_state_machine.state != TransportState.CONNECTED:
                break

        LOGGER.info('disconnected')

        self._stop_event.set()

    async def wait_stopped(self) -> None:
        await self._stop_event.wait()

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
        send_time_utc = self._time_provider.now(timezone.utc)
        msg_seq_num = await self._next_outgoing_seqnum()
        fix_message = self._fix_message_factory.create(
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

    async def logout(self) -> None:
        """Send a logout message.
        """
        # self._admin_state = AdminState.LOGGING_OFF
        await self.send_message('LOGOUT')
