"""The Initiator handler class"""

from abc import ABCMeta, abstractmethod
import asyncio
from datetime import datetime, timezone
import logging
from typing import Awaitable, Callable, Mapping, Any, Optional, cast

from jetblack_fixparser.fix_message import FixMessageFactory
from jetblack_fixparser.meta_data import ProtocolMetaData

from ..connection_state import (
    ConnectionState,
    ConnectionResponse,
    ConnectionStateMachine
)
from ..types import Store, Event

from .initiator_state import (
    AdminState,
    AdminResponse,
    AdminStateMachine,
)

LOGGER = logging.getLogger(__name__)
EPOCH_UTC = datetime.fromtimestamp(0, timezone.utc)

EventHandler = Callable[[Event], Awaitable[None]]


class Initiator(metaclass=ABCMeta):
    """The base class for initiator handlers"""

    def __init__(
            self,
            protocol: ProtocolMetaData,
            sender_comp_id: str,
            target_comp_id: str,
            store: Store,
            logon_timeout: int,
            heartbeat_timeout: int,
            cancellation_event: asyncio.Event,
            *,
            heartbeat_threshold: int = 1
    ) -> None:
        self.logon_timeout = logon_timeout
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_threshold = heartbeat_threshold
        self.cancellation_event = cancellation_event
        self.fix_message_factory = FixMessageFactory(
            protocol,
            sender_comp_id,
            target_comp_id
        )

        self._last_send_time_utc: datetime = EPOCH_UTC
        self._last_receive_time_utc: datetime = EPOCH_UTC
        self._store = store
        self._session = self._store.get_session(sender_comp_id, target_comp_id)
        self._send: Optional[Callable[[Event], Awaitable[None]]] = None
        self._receive: Optional[Callable[[], Awaitable[Event]]] = None

        self._connection_state_machine = ConnectionStateMachine()
        self._connection_handlers = {
            ConnectionResponse.PROCESS_CONNECTED: self._handle_connected,
            ConnectionResponse.PROCESS_FIX: self._handle_fix,
            ConnectionResponse.PROCESS_TIMEOUT: self._handle_timeout,
            ConnectionResponse.PROCESS_ERROR: self._handle_error,
            ConnectionResponse.PROCESS_DISCONNECT: self._handle_disconnect
        }
        self._admin_state_machine = AdminStateMachine()
        self._admin_handlers = {
            AdminResponse.PROCESS_LOGON: self._handle_logon_received,
            AdminResponse.PROCESS_HEARTBEAT: self._handle_heartbeat_received,
            AdminResponse.PROCESS_TEST_REQUEST: self._handle_test_request_received,
            AdminResponse.PROCESS_RESEND_REQUEST: self._handle_resend_request_received,
            AdminResponse.PROCESS_SEQUENCE_RESET: self._handle_sequence_reset_received,
            AdminResponse.PROCESS_LOGOUT: self._handle_acceptor_logout_received

        }

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

    async def _set_incoming_seqnum(self, seqnum: int) -> None:
        await self._session.set_incoming_seqnum(seqnum)

    async def _send_event(self, event: Event, send_time_utc: datetime) -> None:
        if self._send is None:
            raise ValueError('Not connected')
        await self._send(event)
        self._last_send_time_utc = send_time_utc

    async def _handle_test_request_received(
            self,
            message: Mapping[str, Any]
    ) -> None:
        # Respond to the server with the token it sent.
        await self.send_message(
            'TEST_REQUEST',
            {
                'TestReqID': message['TestReqID']
            }
        )

    async def _handle_resend_request_received(
            self,
            _message: Mapping[str, Any]
    ) -> None:
        new_seq_no = await self._session.get_outgoing_seqnum() + 2
        await self.send_message(
            'SEQUENCE_RESET',
            {
                'GapFillFlag': False,
                'NewSeqNo': new_seq_no
            }
        )

    async def _handle_logon_received(
            self,
            message: Mapping[str, Any]
    ) -> None:
        await self.on_logon(message)

    async def _handle_heartbeat_received(
            self,
            message: Mapping[str, Any]
    ) -> None:
        await self.on_heartbeat(message)

    async def _handle_sequence_reset_received(
            self,
            message: Mapping[str, Any]
    ) -> None:
        await self._set_incoming_seqnum(message['NewSeqNo'])

    async def _handle_acceptor_logout_received(
            self,
            message: Mapping[str, Any]
    ) -> None:
        await self.on_logout(message)

    async def _handle_admin_message(self, message: Mapping[str, Any]) -> None:
        await self.on_admin_message(message)

        try:
            response = self._admin_state_machine.transition(message['MsgType'])
            handler = self._admin_handlers[response]
            await handler(message)
        except KeyError:
            LOGGER.warning(
                'unhandled admin message type "%s".',
                message["MsgType"]
            )

    async def _handle_fix(self, event: Event) -> None:
        await self._session.save_message(event['message'])

        fix_message = self.fix_message_factory.decode(event['message'])
        LOGGER.info('Received %s', fix_message.message)

        msgcat = cast(str, fix_message.meta_data.msgcat)
        if msgcat == 'admin':
            await self._handle_admin_message(fix_message.message)
        else:
            await self.on_application_message(fix_message.message)

        msg_seq_num: int = cast(int, fix_message.message['MsgSeqNum'])
        await self._set_incoming_seqnum(msg_seq_num)

        self._last_receive_time_utc = datetime.now(timezone.utc)

    async def _handle_error(self, event: Event) -> None:
        LOGGER.warning('error: %s', event)

    async def _handle_disconnect(self, _event: Event) -> None:
        LOGGER.info('Disconnected')

    async def _send_heartbeat_if_required(self) -> float:
        if self._connection_state_machine.state != ConnectionState.CONNECTED:
            return self.logon_timeout

        now_utc = datetime.now(timezone.utc)
        seconds_since_last_send = (
            now_utc - self._last_send_time_utc
        ).total_seconds()
        if (
                seconds_since_last_send >= self.heartbeat_timeout and
                self._admin_state_machine.state == AdminState.LOGGED_ON
        ):
            await self.send_message('HEARTBEAT')
            seconds_since_last_send = 0

        return self.heartbeat_timeout - seconds_since_last_send

    async def _handle_timeout(self, _event: Event) -> None:
        if not self._admin_state_machine.state == AdminState.LOGGED_ON:
            return

        now_utc = datetime.now(timezone.utc)
        seconds_since_last_receive = (
            now_utc - self._last_receive_time_utc
        ).total_seconds()
        if seconds_since_last_receive - self.heartbeat_timeout > self.heartbeat_threshold:
            # Send a test request to the acceptor to ensure the connection is
            # still active.
            await self.send_message(
                'TEST_REQUEST',
                {
                    'TestReqID': 'TEST'
                }
            )

    async def _handle_connected(self, _event: Event) -> None:
        """Send a logon message"""
        LOGGER.info('connected')
        await self.send_message(
            'LOGON',
            {
                'EncryptMethod': 'NONE',
                'HeartBtInt': self.heartbeat_timeout
            }
        )

    async def _next_event(
            self,
            receive: Callable[[], Awaitable[Event]]
    ) -> Event:
        try:
            timeout = await self._send_heartbeat_if_required()
            return await asyncio.wait_for(receive(), timeout=timeout)
        except asyncio.TimeoutError:
            return {
                'type': 'timeout'
            }

    async def _handle_event(self, event: Event) -> None:
        response = self._connection_state_machine.transition(event['type'])
        handler = self._connection_handlers[response]
        await handler(event)

    async def __call__(
            self,
            send: Callable[[Event], Awaitable[None]],
            receive: Callable[[], Awaitable[Event]]
    ) -> None:
        self._send, self._receive = send, receive

        while True:
            event = await self._next_event(receive)
            await self._handle_event(event)
            if self._connection_state_machine.state != ConnectionState.CONNECTED:
                break

        LOGGER.info('disconnected')

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
        send_time_utc = datetime.now(timezone.utc)
        msg_seq_num = await self._next_outgoing_seqnum()
        fix_message = self.fix_message_factory.create(
            msg_type,
            msg_seq_num,
            send_time_utc,
            message
        )
        LOGGER.info('Sending %s', fix_message.message)
        event = {
            'type': 'fix',
            'message': fix_message.encode(regenerate_integrity=True)
        }
        await self._send_event(event, send_time_utc)

    async def logout(self) -> None:
        """Send a logout message.
        """
        # self._admin_state = AdminState.LOGGING_OFF
        await self.send_message('LOGOUT')

    async def on_admin_message(self, message: Mapping[str, Any]) -> None:
        """Called when an admin message is received.

        Args:
            message (Mapping[str, Any]): The admin message that was sent by the
                acceptor.
        """

    async def on_heartbeat(self, message: Mapping[str, Any]) -> None:
        """Called when a heartbeat is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
        """

    @abstractmethod
    async def on_application_message(self, message: Mapping[str, Any]) -> None:
        """Called when an application message is received.

        Args:
            message (Mapping[str, Any]): The application message sent by the
                acceptor.
        """

    @abstractmethod
    async def on_logon(self, message: Mapping[str, Any]) -> None:
        """Called when a logon message is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
        """

    @abstractmethod
    async def on_logout(self, message: Mapping[str, Any]) -> None:
        """Called when a logout message is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
        """
