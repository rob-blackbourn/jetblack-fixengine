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
    ConnectionEvent,
    ConnectionStateMachineAsync
)
from ..types import Store, Message

from .state import (
    AdminState,
    AdminEvent,
    AdminMessage,
    AdminStateMachineAsync,
)

LOGGER = logging.getLogger(__name__)
EPOCH_UTC = datetime.fromtimestamp(0, timezone.utc)

EventHandler = Callable[[Message], Awaitable[None]]


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
        self._send: Optional[Callable[[Message], Awaitable[None]]] = None
        self._receive: Optional[Callable[[], Awaitable[Message]]] = None

        self._connection_state_machine = ConnectionStateMachineAsync(
            {
                ConnectionState.DISCONNECTED: {
                    ConnectionEvent.CONNECTION_RECEIVED: self._handle_connected
                },
                ConnectionState.CONNECTED: {
                    ConnectionEvent.FIX_RECEIVED: self._handle_fix,
                    ConnectionEvent.TIMEOUT_RECEIVED: self._handle_timeout,
                    ConnectionEvent.DISCONNECT_RECEIVED: self._handle_disconnect
                }
            }
        )
        self._admin_state_machine = AdminStateMachineAsync(
            {
                AdminState.DISCONNECTED: {
                    AdminEvent.CONNECTED: self._send_logon
                },
                AdminState.LOGON_EXPECTED: {
                    AdminEvent.LOGON_RECEIVED: self._logon_received
                },
                AdminState.AUTHENTICATED: {
                    AdminEvent.HEARTBEAT_RECEIVED: self._acknowledge_heartbeat,
                    AdminEvent.TEST_REQUEST_RECEIVED: self._send_test_request,
                    AdminEvent.RESEND_REQUEST_RECEIVED: self._send_sequence_reset,
                    AdminEvent.SEQUENCE_RESET_RECEIVED: self._reset_incoming_seqnum,
                    AdminEvent.LOGOUT_RECEIVED: self._acknowledge_logout
                },
            }
        )

        self._stop_event = asyncio.Event()

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

    async def _send_event(self, event: Message, send_time_utc: datetime) -> None:
        if self._send is None:
            raise ValueError('Not connected')
        await self._send(event)
        self._last_send_time_utc = send_time_utc

    async def _send_test_request(
            self,
            event: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        assert event is not None and event.message is not None
        # Respond to the server with the token it sent.
        await self.send_message(
            'TEST_REQUEST',
            {
                'TestReqID': event.message['TestReqID']
            }
        )
        return AdminMessage(AdminEvent.TEST_REQUEST_SENT)

    async def _send_sequence_reset(
            self,
            _event: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        new_seq_no = await self._session.get_outgoing_seqnum() + 2
        await self.send_message(
            'SEQUENCE_RESET',
            {
                'GapFillFlag': False,
                'NewSeqNo': new_seq_no
            }
        )
        return AdminMessage(AdminEvent.SEQUENCE_RESET_SENT)

    async def _logon_received(
            self,
            event: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        assert event is not None and event.message is not None
        await self.on_logon(event.message)
        return None

    async def _acknowledge_heartbeat(
            self,
            event: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        assert event is not None and event.message is not None
        await self.on_heartbeat(event.message)
        return AdminMessage(AdminEvent.HEARTBEAT_ACK)

    async def _reset_incoming_seqnum(
            self,
            event: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        assert event is not None and event.message is not None
        await self._set_incoming_seqnum(event.message['NewSeqNo'])
        return AdminMessage(AdminEvent.SEQUENCE_RESET_SENT)

    async def _acknowledge_logout(
            self,
            event: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        assert event is not None and event.message is not None
        await self.on_logout(event.message)
        return AdminMessage(AdminEvent.LOGOUT_ACK)

    async def _handle_admin_message(self, message: Mapping[str, Any]) -> None:
        await self.on_admin_message(message)

        await self._admin_state_machine.handle_event(
            AdminMessage(
                AdminEvent.from_msg_type(message['MsgType']),
                message
            )
        )

    async def _handle_fix(
            self,
            event: Optional[Message]
    ) -> Optional[Message]:
        assert event is not None

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

        return {
            'type': 'fix.handled'
        }

    async def _handle_error(self, event: Message) -> None:
        LOGGER.warning('error: %s', event)

    async def _handle_disconnect(
            self,
            _event: Optional[Message]
    ) -> Optional[Message]:
        LOGGER.info('Disconnected')
        return None

    async def _send_heartbeat_if_required(self) -> float:
        if self._connection_state_machine.state != ConnectionState.CONNECTED:
            return self.logon_timeout

        now_utc = datetime.now(timezone.utc)
        seconds_since_last_send = (
            now_utc - self._last_send_time_utc
        ).total_seconds()
        if (
                seconds_since_last_send >= self.heartbeat_timeout and
                self._admin_state_machine.state == AdminState.AUTHENTICATED
        ):
            await self.send_message('HEARTBEAT')
            seconds_since_last_send = 0

        return self.heartbeat_timeout - seconds_since_last_send

    async def _handle_timeout(
            self,
            _event: Optional[Message]
    ) -> Optional[Message]:
        if not self._admin_state_machine.state == AdminState.AUTHENTICATED:
            raise RuntimeError('Make a state for this')

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

        return {
            'type': 'timeout.handled'
        }

    async def _handle_connected(
            self,
            _event: Optional[Message]
    ) -> Optional[Message]:
        LOGGER.info('connected')
        await self._admin_state_machine.handle_event(
            AdminMessage(AdminEvent.CONNECTED)
        )
        return None

    async def _send_logon(
            self,
            _event: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        """Send a logon message"""
        await self.send_message(
            'LOGON',
            {
                'EncryptMethod': 'NONE',
                'HeartBtInt': self.heartbeat_timeout
            }
        )
        return AdminMessage(AdminEvent.LOGON_SENT)

    async def _next_message(
            self,
            receive: Callable[[], Awaitable[Message]]
    ) -> Message:
        try:
            timeout = await self._send_heartbeat_if_required()
            return await asyncio.wait_for(receive(), timeout=timeout)
        except asyncio.TimeoutError:
            return {
                'type': 'timeout'
            }

    async def __call__(
            self,
            send: Callable[[Message], Awaitable[None]],
            receive: Callable[[], Awaitable[Message]]
    ) -> None:
        self._send, self._receive = send, receive

        while True:
            message = await self._next_message(receive)
            await self._connection_state_machine.process(message)
            if self._connection_state_machine.state != ConnectionState.CONNECTED:
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
