"""The Initiator handler class"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Awaitable, Callable, Mapping, Any, Optional, Tuple, cast

from jetblack_fixparser.fix_message import FixMessageFactory
from jetblack_fixparser.meta_data import ProtocolMetaData
from ..types import Store, Event

LOGGER = logging.getLogger(__name__)


class AdminState(Enum):
    LOGON_REQUIRED = 'logon.required'
    LOGGED_ON = 'logon.ok'
    LOGGED_OUT = 'logout.done'


class ConnectionState(Enum):
    DISCONNECTED = 'disconnected'
    CONNECTED = 'connected'
    ERROR = 'error'


EventHandler = Callable[[Event], Awaitable[None]]

AdminTransitionKey = Tuple[AdminState, Optional[str]]
AdminTransitionValue = Tuple[EventHandler, AdminState]
AdminTransitionMapping = Mapping[AdminTransitionKey, AdminTransitionValue]

ConnectionTransitionKey = Tuple[ConnectionState, Optional[str]]
ConnectionTransitionValue = Tuple[EventHandler, ConnectionState]
ConnectionTransitionMapping = Mapping[ConnectionTransitionKey,
                                      ConnectionTransitionValue]

EPOCH_UTC = datetime.fromtimestamp(0, timezone.utc)


class InitiatorHandler():
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

        self._connection_state = ConnectionState.DISCONNECTED
        self._admin_state = AdminState.LOGON_REQUIRED
        self._last_send_time_utc: datetime = EPOCH_UTC
        self._last_receive_time_utc: datetime = EPOCH_UTC
        self._store = store
        self._session = self._store.get_session(sender_comp_id, target_comp_id)
        self._send: Optional[Callable[[Event], Awaitable[None]]] = None
        self._receive: Optional[Callable[[], Awaitable[Event]]] = None

        self._connection_transitions: ConnectionTransitionMapping = {
            (ConnectionState.DISCONNECTED, 'connected'): (
                self._handle_connected,
                ConnectionState.CONNECTED
            ),
            (ConnectionState.CONNECTED, 'fix'): (
                self._handle_fix_event,
                ConnectionState.CONNECTED
            ),
            (ConnectionState.CONNECTED, 'timeout'): (
                self._handle_timeout,
                ConnectionState.CONNECTED
            ),
            (ConnectionState.CONNECTED, 'error'): (
                self._handle_error_event,
                ConnectionState.DISCONNECTED
            ),
            (ConnectionState.CONNECTED, 'disconnect'): (
                self._handle_disconnect_event,
                ConnectionState.DISCONNECTED
            )
        }
        self._admin_transitions: AdminTransitionMapping = {
            (AdminState.LOGON_REQUIRED, 'LOGON'): (
                self._handle_logon_received,
                AdminState.LOGGED_ON
            ),
            (AdminState.LOGGED_ON, 'HEARTBEAT'): (
                self._handle_heartbeat_received,
                AdminState.LOGGED_ON
            ),
            (AdminState.LOGGED_ON, 'TEST_REQUEST'): (
                self._handle_test_request,
                AdminState.LOGGED_ON
            ),
            (AdminState.LOGGED_ON, 'RESEND_REQUEST'): (
                self._handle_resend_request,
                AdminState.LOGGED_ON
            ),
            (AdminState.LOGGED_ON, 'SEQUENCE_RESET'): (
                self._handle_sequence_reset,
                AdminState.LOGGED_ON
            ),
            (AdminState.LOGGED_ON, 'LOGOUT'): (
                self._handle_acceptor_logout,
                AdminState.LOGGED_OUT
            )
        }

    async def _next_outgoing_seqnum(self) -> int:
        seqnum = await self._session.get_outgoing_seqnum()
        seqnum += 1
        await self._session.set_outgoing_seqnum(seqnum)
        return seqnum

    async def _set_seqnums(self, outgoing_seqnum: int, incoming_seqnum: int) -> None:
        await self._session.set_seqnums(outgoing_seqnum, incoming_seqnum)

    async def _set_incoming_seqnum(self, seqnum: int) -> None:
        await self._session.set_incoming_seqnum(seqnum)

    async def _send_event(self, event: Event, send_time_utc: datetime) -> None:
        if self._send is None:
            raise ValueError('Not connected')
        await self._send(event)
        self._last_send_time_utc = send_time_utc

    async def send_message(
            self,
            msg_type: str,
            message: Optional[Mapping[str, Any]] = None
    ) -> None:
        send_time_utc = datetime.now(timezone.utc)
        msg_seq_num = await self._next_outgoing_seqnum()
        fix_message = self.fix_message_factory.create(
            msg_type,
            msg_seq_num,
            send_time_utc,
            message
        )
        LOGGER.info('sending: %s', fix_message.message)
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

    async def heartbeat(self, test_req_id: Optional[str] = None) -> None:
        """Send a heartbeat message.

        Args:
            test_req_id (Optional[str], optional): An optional test req id.
                Defaults to None.
        """
        body_kwargs = {}
        if test_req_id:
            body_kwargs['TestReqID'] = test_req_id
        await self.send_message('HEARTBEAT', body_kwargs)

    async def resend_request(self, begin_seqnum: int, end_seqnum: int = 0) -> None:
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

    async def _handle_test_request(self, message: Mapping[str, Any]) -> None:
        # Respond to the server with the token it sent.
        await self.send_message(
            'TEST_REQUEST',
            {
                'TestReqID': message['TestReqID']
            }
        )

    async def _handle_resend_request(
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

    async def _handle_logon_received(self, _message: Mapping[str, Any]) -> None:
        await self.on_logon()

    async def _handle_heartbeat_received(self, _message: Mapping[str, Any]) -> None:
        await self.on_heartbeat()

    async def _handle_sequence_reset(self, message: Mapping[str, Any]) -> None:
        await self._set_incoming_seqnum(message['NewSeqNo'])

    async def _handle_acceptor_logout(self, _message: Mapping[str, Any]) -> None:
        await self.on_logout()

    async def _handle_admin_message(self, message: Mapping[str, Any]) -> None:
        LOGGER.info('Admin message: %s', message)

        await self.on_admin_message(message)

        try:
            handler, self._admin_state = self._admin_transitions[
                (self._admin_state, message['MsgType'])
            ]
            await handler(message)
        except KeyError:
            LOGGER.warning(
                'unhandled admin message type "%s".',
                message["MsgType"]
            )

    async def _handle_fix_event(self, event: Event) -> None:
        await self._session.save_message(event['message'])

        fix_message = self.fix_message_factory.decode(event['message'])
        msgcat = cast(str, fix_message.meta_data.msgcat)
        if msgcat == 'admin':
            await self._handle_admin_message(fix_message.message)
        else:
            await self.on_application_message(fix_message.message)

        msg_seq_num: int = cast(int, fix_message.message['MsgSeqNum'])
        await self._set_incoming_seqnum(msg_seq_num)

        self._last_receive_time_utc = datetime.now(timezone.utc)

    async def _handle_error_event(self, event: Event) -> None:
        LOGGER.warning('error: %s', event)

    async def _handle_disconnect_event(self, _event: Event) -> None:
        LOGGER.info('Disconnected')

    async def _send_heartbeat_if_required(self) -> float:
        if self._connection_state != ConnectionState.CONNECTED:
            return self.logon_timeout

        now_utc = datetime.now(timezone.utc)
        seconds_since_last_send = (
            now_utc - self._last_send_time_utc
        ).total_seconds()
        if (
                seconds_since_last_send >= self.heartbeat_timeout and
                self._admin_state == AdminState.LOGGED_ON
        ):
            await self.heartbeat()
            seconds_since_last_send = 0

        return self.heartbeat_timeout - seconds_since_last_send

    async def _handle_timeout(self, _event: Event) -> None:
        if not self._admin_state == AdminState.LOGGED_ON:
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
        handler, self._connection_state = self._connection_transitions[
            (self._connection_state, event['type'])
        ]
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
            if self._connection_state != ConnectionState.CONNECTED:
                break

        LOGGER.info('disconnected')
        self._connection_state = ConnectionState.DISCONNECTED

    async def on_admin_message(self, message: Mapping[str, Any]) -> None:
        """Called when an admin message is received.

        Args:
            message (Mapping[str, Any]): The admin message that was sent by the
                acceptor.
        """

    async def on_application_message(self, message: Mapping[str, Any]) -> None:
        """Called when an application message is received.

        Args:
            message (Mapping[str, Any]): The application message sent by the
                acceptor.
        """

    async def on_logon(self) -> None:
        """Called when a logon message is received.
        """

    async def on_logout(self) -> None:
        """Called when a logout message is received.
        """

    async def on_heartbeat(self) -> None:
        """Called when a heartbeat is received.
        """
