from abc import ABCMeta, abstractmethod
import asyncio
from datetime import datetime, time, tzinfo
import logging
from typing import Mapping, Any, Optional, Tuple
import uuid
from ..meta_data import ProtocolMetaData
from ..types import Store, Event
from ..utils.date_utils import wait_for_time_period

logger = logging.getLogger(__name__)

STATE_LOGGING_ON = 'logon.start'
STATE_LOGGED_ON = 'logon.ok'
STATE_LOGGING_OFF = 'logout.start'
STATE_LOGGED_OUT = 'logout.done'
STATE_TEST_HEARTBEAT = 'test.heartbeat'
STATE_SYNCHRONISING = 'session.sync'


class AcceptorHandler(metaclass=ABCMeta):

    def __init__(
            self,
            protocol: ProtocolMetaData,
            sender_comp_id: str,
            target_comp_id: str,
            store: Store,
            heartbeat_timeout: int,
            cancellation_token: asyncio.Event,
            *,
            heartbeat_threshold: int = 1,
            logon_time_range: Optional[Tuple[time, time]] = None,
            tz: tzinfo = None
    ) -> None:
        self.protocol = protocol
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_threshold = heartbeat_threshold
        self.cancellation_token = cancellation_token
        self.logon_time_range = logon_time_range
        self.tz = tz

        self._state = None
        self._test_heartbeat_message = None
        self._last_send_time_utc: datetime = None
        self._last_receive_time_utc: datetime = None
        self._store = store
        self._session = self._store.get_session(sender_comp_id, target_comp_id)

    async def __call__(self, send, receive) -> None:
        self._send, self._receive = send, receive

        # Wait for connection.
        event = await receive()

        if event['type'] == 'connected':
            logger.info('connected')
            self._state = STATE_LOGGING_ON

            logout_time = await self._wait_till_logon_time()

            while self._state != STATE_LOGGED_OUT:
                try:
                    await self._send_logout_if_login_expired(logout_time)
                    seconds_till_next_heartbeat = await self._send_heartbeat_if_required()
                    event = await asyncio.wait_for(receive(), timeout=seconds_till_next_heartbeat)

                    if event['type'] == 'fix':
                        await self._on_event_fix(
                            event['message'],
                            event['message_contents'],
                            event['message_category']
                        )

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

        logger.info('disconnected')

    async def _wait_till_logon_time(self) -> Optional[datetime]:
        if not self.logon_time_range:
            return None

        start_time, end_time = self.logon_time_range
        logout_time = await wait_for_time_period(
            datetime.now(tz=self.tz),
            start_time,
            end_time,
            cancellation_token=self.cancellation_token
        )
        return logout_time

    async def _send_logout_if_login_expired(self, logout_time: Optional[datetime]) -> None:
        if self._state != STATE_LOGGED_ON or not logout_time:
            return

        # Is it time to logout?
        if datetime.now(tz=self.tz) >= logout_time:
            await self.send_logout()
            await self.on_logout()

    async def _send_heartbeat_if_required(self) -> float:
        now_utc = datetime.utcnow()
        seconds_since_last_send = (now_utc - self._last_send_time_utc).total_seconds()
        if seconds_since_last_send >= self.heartbeat_timeout and self._state == STATE_LOGGED_ON:
            await self.send_heartbeat()
            seconds_since_last_send = 0

        seconds_till_next_heartbeat = self.heartbeat_timeout - seconds_since_last_send

        return seconds_till_next_heartbeat

    async def _on_event_fix(
            self,
            encoded_message: bytes,
            decoded_message: Mapping[str, Any],
            message_category: str
    ) -> None:

        await self._session.save_message(encoded_message)

        if self._state == STATE_TEST_HEARTBEAT:
            # Ignore all messages other than the heartbeat response
            if decoded_message['MsgType'] == 'HEARTBEAT':
                if decoded_message['TestReqID'] == self._test_heartbeat_message:
                    # SWitch back to logged on
                    self._state = STATE_LOGGED_ON
                else:
                    self._state = STATE_LOGGING_OFF
                    await self.send_logout()

        elif self._state == STATE_SYNCHRONISING:
            pass
        elif message_category == 'admin':
            await self._on_admin_message(decoded_message)
        else:
            await self.on_application_message(decoded_message)

        await self._set_incoming_seqnum(decoded_message['MsgSeqNum'])
        self._last_receive_time_utc = datetime.utcnow()

    async def _on_timeout(self) -> None:
        if self._state != STATE_LOGGED_ON:
            return

        now_utc = datetime.utcnow()
        seconds_since_last_receive = (now_utc - self._last_receive_time_utc).total_seconds()
        if seconds_since_last_receive - self.heartbeat_timeout > self.heartbeat_threshold:
            self._state = STATE_TEST_HEARTBEAT
            self._test_heartbeat_message = str(uuid.uuid4())
            await self.send_test_request(self._test_heartbeat_message)

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
        await self._send(event)
        self._last_send_time_utc = send_time_utc

    async def _send_fix_message(self, message: Mapping[str, Any], send_time_utc: datetime) -> None:
        logger.info(f'sending: {message}')
        event = {
            'type': 'fix',
            'message_contents': message
        }
        await self._send_event(event, send_time_utc)

    async def logon(self) -> None:
        send_time_utc = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'LOGON',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time_utc,
            'EncryptMethod': 'NONE',
            'HeartBtInt': self.heartbeat_timeout
        }
        self._state = STATE_LOGGING_ON
        await self._send_fix_message(message, send_time_utc)

    async def send_logout(self) -> None:
        send_time_utc = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'LOGOUT',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time_utc
        }
        self._state = STATE_LOGGING_OFF
        await self._send_fix_message(message, send_time_utc)

    async def send_heartbeat(self, test_req_id: Optional[str] = None) -> None:
        send_time_utc = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'HEARTBEAT',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time_utc
        }
        if test_req_id:
            message['TestReqID'] = test_req_id
        await self._send_fix_message(message, send_time_utc)

    async def send_resend_request(self, begin_seqnum: int, end_seqnum: int = 0) -> None:
        send_time_utc = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'RESEND_REQUEST',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time_utc,
            'BeginSeqNo': begin_seqnum,
            'EndSeqNo': end_seqnum
        }
        await self._send_fix_message(message, send_time_utc)

    async def send_test_request(self, test_req_id: str) -> None:
        send_time_utc = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'TEST_REQUEST',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time_utc,
            'TestReqID': test_req_id
        }
        await self._send_fix_message(message, send_time_utc)

    async def send_sequence_reset(self, gap_fill: bool, new_seq_no: int) -> None:
        send_time_utc = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'SEQUENCE_RESET',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time_utc,
            'GapFillFlag': gap_fill,
            'NewSeqNo': new_seq_no
        }
        await self._send_fix_message(message, send_time_utc)

    async def _on_admin_message(self, message: Mapping[str, Any]) -> bool:
        logger.info(f'on_admin_message: {message}')

        # Only handle if unhandled by the overrideing method.
        override_status = await self.on_admin_message(message)
        if override_status is not None:
            return override_status

        if message['MsgType'] == 'LOGON':
            return await self._on_login(message)
        elif message['MsgType'] == 'HEARTBEAT':
            return True
        elif message['MsgType'] == 'TEST_REQUEST':
            await self.send_test_request(message['TestReqID'])
            return True
        elif message['MsgType'] == 'RESEND_REQUEST':
            await self.send_sequence_reset(False, await self._session.get_outgoing_seqnum() + 2)
            return True
        elif message['MsgType'] == 'SEQUENCE_RESET':
            await self._set_incoming_seqnum(message['NewSeqNo'])
            return True
        elif message['MsgType'] == 'LOGOUT':
            self._state = STATE_LOGGED_OUT
            return False
        else:
            logger.warning(f'unhandled admin message type "{message["MsgType"]}".')
            return True

    @abstractmethod
    async def on_admin_message(self, message: Mapping[str, Any]) -> Optional[bool]:
        raise NotImplementedError

    async def _on_login(self, message: Mapping[str, Any]) -> bool:
        if await self.on_logon(message):
            # Acknowledge the login
            await self.logon()
            self._state = STATE_LOGGED_ON
            return True
        else:
            # Reject the login.
            await self.send_logout()
            self._state = STATE_LOGGING_OFF
            return False

    @abstractmethod
    async def on_logon(self, message: Mapping[str, Any]) -> bool:
        """Return True if the login is valid"""
        raise NotImplementedError

    @abstractmethod
    async def on_logout(self) -> None:
        """Perform any logout lasks"""
        raise NotImplementedError

    @abstractmethod
    async def on_application_message(self, message: Mapping[str, Any]) -> bool:
        raise NotImplementedError
