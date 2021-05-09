"""Acceptor handler"""

from abc import ABCMeta, abstractmethod
import asyncio
from datetime import datetime, time, tzinfo, timezone
import logging
from typing import (
    Awaitable,
    Callable,
    Mapping,
    Any,
    Optional,
    Tuple,
    Union,
    cast
)
import uuid

from jetblack_fixparser.fix_message import FixMessageFactory
from jetblack_fixparser.meta_data import ProtocolMetaData
from ..types import Store, Event
from ..utils.date_utils import wait_for_time_period

LOGGER = logging.getLogger(__name__)

STATE_LOGGING_ON = 'logon.start'
STATE_LOGGED_ON = 'logon.ok'
STATE_LOGGING_OFF = 'logout.start'
STATE_LOGGED_OUT = 'logout.done'
STATE_TEST_HEARTBEAT = 'test.heartbeat'
STATE_SYNCHRONISING = 'session.sync'

EPOCH_UTC = datetime.fromtimestamp(0, timezone.utc)


class AcceptorHandler(metaclass=ABCMeta):
    """The base class for acceptor handlers"""

    def __init__(
            self,
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
            tz: Optional[tzinfo] = None
    ) -> None:
        self.protocol = protocol
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_threshold = heartbeat_threshold
        self.cancellation_event = cancellation_event
        self.logon_time_range = logon_time_range
        self.logon_timeout = logon_timeout
        self.tz = tz
        self.fix_message_factory = FixMessageFactory(
            protocol,
            sender_comp_id,
            target_comp_id
        )

        self._state: Optional[str] = None
        self._test_heartbeat_message: Optional[str] = None
        self._last_send_time_utc: datetime = EPOCH_UTC
        self._last_receive_time_utc: datetime = EPOCH_UTC
        self._store = store
        self._session = self._store.get_session(sender_comp_id, target_comp_id)
        self._send: Optional[Callable[[Event], Awaitable[None]]] = None
        self._receive: Optional[Callable[[], Awaitable[Event]]] = None

    async def __call__(
            self,
            send: Callable[[Event], Awaitable[None]],
            receive: Callable[[], Awaitable[Event]]
    ) -> None:
        self._send, self._receive = send, receive

        # Wait for connection.
        event = await receive()

        if event['type'] == 'connected':
            LOGGER.info('connected')
            self._state = STATE_LOGGING_ON

            logout_time = await self._wait_till_logon_time()

            while self._state != STATE_LOGGED_OUT:
                try:
                    await self._send_logout_if_login_expired(logout_time)
                    seconds_till_next_heartbeat = await self._send_heartbeat_if_required()
                    event = await asyncio.wait_for(receive(), timeout=seconds_till_next_heartbeat)

                    if event['type'] == 'fix':
                        await self._on_fix_event(event)

                    elif event['type'] == 'error':
                        break
                    elif event['type'] == 'disconnect':
                        break
                    else:
                        raise Exception(f'Unhandled event {event["type"]}')

                except asyncio.TimeoutError:
                    await self._on_timeout()
        else:
            raise RuntimeError('Failed to connect')

        LOGGER.info('disconnected')

    async def _wait_till_logon_time(self) -> Optional[datetime]:
        if not self.logon_time_range:
            return None

        start_time, end_time = self.logon_time_range
        logout_time = await wait_for_time_period(
            datetime.now(tz=self.tz),
            start_time,
            end_time,
            cancellation_event=self.cancellation_event
        )
        return logout_time

    async def _send_logout_if_login_expired(self, logout_time: Optional[datetime]) -> None:
        if self._state != STATE_LOGGED_ON or not logout_time:
            return

        # Is it time to logout?
        if datetime.now(tz=self.tz) >= logout_time:
            self._state = STATE_LOGGING_OFF
            await self.send_message('LOGOUT')
            await self.on_logout({})

    async def _send_heartbeat_if_required(self) -> float:
        if self._state == STATE_LOGGING_ON:
            return self.logon_timeout

        now_utc = datetime.now(timezone.utc)
        seconds_since_last_send = (
            now_utc - self._last_send_time_utc
        ).total_seconds()
        if (
                seconds_since_last_send >= self.heartbeat_timeout and
                self._state == STATE_LOGGED_ON
        ):
            await self.send_message('HEARTBEAT')
            seconds_since_last_send = 0

        seconds_till_next_heartbeat = self.heartbeat_timeout - seconds_since_last_send

        return seconds_till_next_heartbeat

    async def _on_fix_event(self, event: Event) -> None:

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

    async def _on_timeout(self) -> None:
        if self._state != STATE_LOGGED_ON:
            return

        now_utc = datetime.now(timezone.utc)
        seconds_since_last_receive = (
            now_utc - self._last_receive_time_utc).total_seconds()
        if seconds_since_last_receive - self.heartbeat_timeout > self.heartbeat_threshold:
            self._state = STATE_TEST_HEARTBEAT
            self._test_heartbeat_message = str(uuid.uuid4())
            await self.send_message(
                'TEST_REQUEST',
                {
                    'TestReqID': self._test_heartbeat_message
                }
            )

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
            raise ValueError("Not connected")
        await self._send(event)
        self._last_send_time_utc = send_time_utc

    async def _send_fix_message(
            self,
            message: Mapping[str, Any],
            send_time_utc: datetime
    ) -> None:
        LOGGER.info('Sending %s', message)
        event = {
            'type': 'fix',
            'message_contents': message
        }
        await self._send_event(event, send_time_utc)

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

    async def send_resend_request(self, begin_seqnum: int, end_seqnum: int = 0) -> None:
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

    async def _handle_logon_received(self, message: Mapping[str, Any]) -> bool:
        if await self.on_logon(message):
            # Acknowledge the login
            await self.send_message(
                'LOGON',
                {
                    'EncryptMethod': 'NONE',
                    'HeartBtInt': self.heartbeat_timeout
                }
            )
            self._state = STATE_LOGGED_ON
            return True
        else:
            # Reject the login.
            self._state = STATE_LOGGING_OFF
            await self.send_message('LOGOUT')
            self._state = STATE_LOGGING_OFF
            return False

    async def _handle_heartbeat_received(
            self,
            message: Mapping[str, Any]
    ) -> None:
        await self.on_heartbeat(message)

    async def _handle_test_request(self, message: Mapping[str, Any]) -> None:
        test_req_id = message['TestReqID']
        await self.send_message(
            'TEST_REQUEST',
            {
                'TestReqID': test_req_id
            }
        )

    async def _handle_resend_request(self, _message: Mapping[str, Any]) -> None:
        new_seq_no = await self._session.get_outgoing_seqnum() + 2
        await self.send_message(
            'SEQUENCE_RESET',
            {
                'GapFillFlag': False,
                'NewSeqNo': new_seq_no
            }
        )

    async def _handle_sequence_reset(self, message: Mapping[str, Any]) -> None:
        await self._set_incoming_seqnum(message['NewSeqNo'])

    async def _handle_logout_received(self, message: Mapping[str, Any]) -> None:
        self._state = STATE_LOGGED_OUT
        await self.on_logout(message)

    async def _handle_admin_message(self, message: Mapping[str, Any]) -> None:
        LOGGER.info('on_admin_message: %s', message)

        await self.on_admin_message(message)

        if self._state == STATE_TEST_HEARTBEAT:
            # Ignore all messages other than the heartbeat response
            if message['MsgType'] == 'HEARTBEAT':
                if message['TestReqID'] == self._test_heartbeat_message:
                    # SWitch back to logged on
                    self._state = STATE_LOGGED_ON
                else:
                    self._state = STATE_LOGGING_OFF
                    await self.send_message('LOGOUT')
        elif self._state == STATE_SYNCHRONISING:
            pass
        elif message['MsgType'] == 'LOGON':
            await self._handle_logon_received(message)
        elif message['MsgType'] == 'HEARTBEAT':
            await self._handle_heartbeat_received(message)
        elif message['MsgType'] == 'TEST_REQUEST':
            await self._handle_test_request(message)
        elif message['MsgType'] == 'RESEND_REQUEST':
            await self._handle_resend_request(message)
        elif message['MsgType'] == 'SEQUENCE_RESET':
            await self._handle_sequence_reset(message)
        elif message['MsgType'] == 'LOGOUT':
            await self._handle_logout_received(message)
        else:
            LOGGER.warning(
                'unhandled admin message type "%s".',
                message["MsgType"]
            )

    async def on_admin_message(self, message: Mapping[str, Any]) -> None:
        """Handle an admin message.

        Args:
            message (Mapping[str, Any]): The message to handle.
        """

    async def on_heartbeat(self, message: Mapping[str, Any]) -> None:
        pass

    @abstractmethod
    async def on_logon(self, message: Mapping[str, Any]) -> bool:
        """Return True if the login is valid

        Args:
            message (Mapping[str, Any]): The message to handle.
        """

    @abstractmethod
    async def on_logout(self, message: Mapping[str, Any]) -> None:
        """Perform any logout tasks

        Args:
            message (Mapping[str, Any]): The message to handle.
        """

    @abstractmethod
    async def on_application_message(self, message: Mapping[str, Any]) -> None:
        """Handle an application message.

        Args:
            message (Mapping[str, Any]): The message to handle.
        """
