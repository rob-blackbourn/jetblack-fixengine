"""The Initiator handler class"""

from abc import ABCMeta, abstractmethod
import asyncio
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Awaitable, Callable, Mapping, Any, Optional, cast

from jetblack_fixparser.fix_message import FixMessageFactory
from jetblack_fixparser.meta_data import ProtocolMetaData
from ..types import Store, Event

LOGGER = logging.getLogger(__name__)


class InitiatorState(Enum):
    DISCONNECTED = 'disconnected'
    CONNECTED = 'connected'
    LOGGING_ON = 'logon.start'
    LOGGED_ON = 'logon.ok'
    LOGGING_OFF = 'logout.start'
    LOGGED_OUT = 'logout.done'
    ERROR = 'error'


EPOCH_UTC = datetime.fromtimestamp(0, timezone.utc)


class InitiatorHandler(metaclass=ABCMeta):
    """The base class for initiators"""

    def __init__(
            self,
            protocol: ProtocolMetaData,
            sender_comp_id: str,
            target_comp_id: str,
            store: Store,
            heartbeat_timeout: int,
            cancellation_event: asyncio.Event,
            *,
            heartbeat_threshold: int = 1
    ) -> None:
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_threshold = heartbeat_threshold
        self.cancellation_event = cancellation_event
        self.fix_message_factory = FixMessageFactory(
            protocol,
            sender_comp_id,
            target_comp_id
        )

        self._state = InitiatorState.DISCONNECTED
        self._last_send_time_utc: datetime = EPOCH_UTC
        self._last_receive_time_utc: datetime = EPOCH_UTC
        self._store = store
        self._session = self._store.get_session(sender_comp_id, target_comp_id)
        self._send: Optional[Callable[[Event], Awaitable[None]]] = None
        self._receive: Optional[Callable[[], Awaitable[Event]]] = None

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

    async def logon(self) -> None:
        """Send a logon message"""
        self._state = InitiatorState.LOGGING_ON
        await self.send_message(
            'LOGON',
            {
                'EncryptMethod': 'NONE',
                'HeartBtInt': self.heartbeat_timeout
            }
        )

    async def logout(self) -> None:
        """Send a logout message.
        """
        self._state = InitiatorState.LOGGING_OFF
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

    async def _handle_test_request(self, message: Mapping[str, Any]) -> bool:
        # Respond to the server with the token it sent.
        await self.send_message(
            'TEST_REQUEST',
            {
                'TestReqID': message['TestReqID']
            }
        )
        return True

    async def _handle_resend_request(
            self,
            _message: Mapping[str, Any]
    ) -> bool:
        new_seq_no = await self._session.get_outgoing_seqnum() + 2
        await self.send_message(
            'SEQUENCE_RESET',
            {
                'GapFillFlag': False,
                'NewSeqNo': new_seq_no
            }
        )
        return True

    async def _handle_logon(self, _message: Mapping[str, Any]) -> bool:
        await self.on_logon()
        self._state = InitiatorState.LOGGED_ON
        return True

    async def _handle_heartbeat(self, _message: Mapping[str, Any]) -> bool:
        return True

    async def _handle_sequence_reset(self, message: Mapping[str, Any]) -> bool:
        await self._set_incoming_seqnum(message['NewSeqNo'])
        return True

    async def _handle_logout(self, _message: Mapping[str, Any]) -> bool:
        self._state = InitiatorState.LOGGED_OUT
        return False

    async def _handle_admin_message(self, message: Mapping[str, Any]) -> None:
        LOGGER.info('on_admin_message: %s', message)

        # Only handle if unhandled by the overrideing method.
        override_status = await self.on_admin_message(message)
        if override_status is not None:
            return

        if message['MsgType'] == 'LOGON':
            await self._handle_logon(message)
        elif message['MsgType'] == 'HEARTBEAT':
            await self._handle_heartbeat(message)
        elif message['MsgType'] == 'TEST_REQUEST':
            await self._handle_test_request(message)
        elif message['MsgType'] == 'RESEND_REQUEST':
            await self._handle_resend_request(message)
        elif message['MsgType'] == 'SEQUENCE_RESET':
            await self._handle_sequence_reset(message)
        elif message['MsgType'] == 'LOGOUT':
            await self._handle_logout(message)
        else:
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
        LOGGER.warning('error')
        self._state = InitiatorState.ERROR

    async def _handle_disconnect_event(self, event: Event) -> None:
        self._state = InitiatorState.DISCONNECTED

    async def _handle_event(self, event: Event) -> None:
        if event['type'] == 'fix':
            await self._handle_fix_event(event)
        elif event['type'] == 'error':
            await self._handle_error_event(event)
        elif event['type'] == 'disconnect':
            await self._handle_disconnect_event(event)
        else:
            raise ValueError(f"Unknown event type: {event['type']}")

    async def _send_heartbeat_if_required(self) -> float:
        now_utc = datetime.now(timezone.utc)
        seconds_since_last_send = (
            now_utc - self._last_send_time_utc
        ).total_seconds()
        if (
                seconds_since_last_send >= self.heartbeat_timeout and
                self._state == InitiatorState.LOGGED_ON
        ):
            await self.heartbeat()
            seconds_since_last_send = 0

        return self.heartbeat_timeout - seconds_since_last_send

    async def _handle_timeout(self) -> None:
        if not self._state == InitiatorState.LOGGED_ON:
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

    async def __call__(
            self,
            send: Callable[[Event], Awaitable[None]],
            receive: Callable[[], Awaitable[Event]]
    ) -> None:
        self._send, self._receive = send, receive

        event = await receive()

        if event['type'] == 'connected':
            LOGGER.info('connected')
            self._state = InitiatorState.CONNECTED

            await self.logon()

            while self._state not in (
                    InitiatorState.LOGGED_OUT,
                    InitiatorState.DISCONNECTED,
                    InitiatorState.ERROR
            ):
                try:
                    timeout = await self._send_heartbeat_if_required()
                    event = await asyncio.wait_for(receive(), timeout=timeout)
                    await self._handle_event(event)
                except asyncio.TimeoutError:
                    await self._handle_timeout()
        else:
            raise RuntimeError('Failed to connect')

        LOGGER.info('disconnected')
        self._state = InitiatorState.DISCONNECTED

    @abstractmethod
    async def on_admin_message(self, message: Mapping[str, Any]) -> Optional[bool]:
        """Handle an admin message

        Args:
            message (Mapping[str, Any]): The admin message that was sent by the
                acceptor.

        Raises:
            NotImplementedError: [description]

        Returns:
            Optional[bool]: If true the message will override the base handler.
        """
        ...

    @abstractmethod
    async def on_application_message(self, message: Mapping[str, Any]) -> None:
        """Handle an application message.

        Args:
            message (Mapping[str, Any]): The application message sent by the
                acceptor.

        Raises:
            NotImplementedError: [description]
        """
        ...

    @abstractmethod
    async def on_logon(self) -> None:
        """Called when a logon message is received.
        """
        ...

    @abstractmethod
    async def on_logout(self) -> None:
        """Called when a logout message is received.
        """
        ...
