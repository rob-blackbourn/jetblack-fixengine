import asyncio
from datetime import datetime
import logging
from typing import Mapping, Any, Optional
from ..meta_data import ProtocolMetaData
from ..types import InitiatorStore, Event

logger = logging.getLogger(__name__)


class InitiatorHandler:

    def __init__(
            self,
            protocol: ProtocolMetaData,
            sender_comp_id: str,
            target_comp_id: str,
            store: InitiatorStore,
            heartbeat_timeout: int,
            *,
            heartbeat_threshold: int = 1
    ) -> None:
        self.protocol = protocol
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_threshold = heartbeat_threshold
        self.is_logged_on = False
        self._last_send_time: datetime = None
        self._last_receive_time: datetime = None
        self._store = store
        self._session = self._store.get_session(sender_comp_id, target_comp_id)

    async def _next_outgoing_seqnum(self) -> int:
        seqnum = await self._session.get_outgoing_seqnum()
        seqnum += 1
        await self._session.set_outgoing_seqnum(seqnum)
        return seqnum

    async def _set_seqnums(self, outgoing_seqnum: int, incoming_seqnum: int) -> None:
        await self._session.set_seqnums(outgoing_seqnum, incoming_seqnum)

    async def _set_incoming_seqnum(self, seqnum: int) -> None:
        await self._session.set_incoming_seqnum(seqnum)

    async def _send_event(self, event: Event, send_time: datetime) -> None:
        await self._send(event)
        self._last_send_time = send_time

    async def _send_fix_message(self, message: Mapping[str, Any], send_time: datetime) -> None:
        logger.info(f'sending: {message}')
        event = {
            'type': 'fix',
            'message_contents': message
        }
        await self._send_event(event, send_time)

    async def logon(self) -> None:
        send_time = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'LOGON',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time,
            'EncryptMethod': 'NONE',
            'HeartBtInt': self.heartbeat_timeout
        }
        await self._send_fix_message(message, send_time)

    async def logout(self) -> None:
        send_time = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'LOGOUT',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time
        }
        await self._send_fix_message(message, send_time)

    async def heartbeat(self, test_req_id: Optional[str] = None) -> None:
        send_time = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'HEARTBEAT',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time
        }
        if test_req_id:
            message['TestReqID'] = test_req_id
        await self._send_fix_message(message, send_time)

    async def resend_request(self, begin_seqnum: int, end_seqnum: int = 0) -> None:
        send_time = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'RESEND_REQUEST',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time,
            'BeginSeqNo': begin_seqnum,
            'EndSeqNo': end_seqnum
        }
        await self._send_fix_message(message, send_time)

    async def test_request(self, test_req_id: str) -> None:
        send_time = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'TEST_REQUEST',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time,
            'TestReqID': test_req_id
        }
        await self._send_fix_message(message, send_time)

    async def sequence_reset(self, gap_fill: bool, new_seq_no: int) -> None:
        send_time = datetime.utcnow()
        msg_seq_num = await self._next_outgoing_seqnum()
        message = {
            'MsgType': 'SEQUENCE_RESET',
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': send_time,
            'GapFillFlag': gap_fill,
            'NewSeqNo': new_seq_no
        }
        await self._send_fix_message(message, send_time)

    async def _on_admin_message(self, message: Mapping[str, Any]) -> bool:
        logger.info(f'on_admin_message: {message}')

        # Only handle if unhandled by the overrideing method.
        override_status = await self.on_admin_message(message)
        if override_status is not None:
            return override_status

        if message['MsgType'] == 'LOGON':
            await self.on_logon()
            self.is_logged_on = True
            return True
        elif message['MsgType'] == 'HEARTBEAT':
            return True
        elif message['MsgType'] == 'TEST_REQUEST':
            await self.test_request(message['TestReqID'])
            return True
        elif message['MsgType'] == 'RESEND_REQUEST':
            await self.sequence_reset(False, await self._session.get_outgoing_seqnum() + 2)
            return True
        elif message['MsgType'] == 'SEQUENCE_RESET':
            await self._set_incoming_seqnum(message['NewSeqNo'])
            return True
        elif message['MsgType'] == 'LOGOUT':
            self.is_logged_on = False
            return False
        else:
            logger.warning(f'unhandled admin message type "{message["MsgType"]}".')
            return True

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    async def on_admin_message(self, message: Mapping[str, Any]) -> Optional[bool]:
        return None

    # noinspection PyMethodMayBeStatic
    async def on_application_message(self, message: Mapping[str, Any]) -> bool:
        logger.info(f'on_application_message: {message}')
        return True

    async def _handle_event(self, event: Event) -> bool:
        if event['type'] == 'fix':
            if event['message_category'] == 'admin':
                status = await self._on_admin_message(event['message_contents'])
            else:
                status = await self.on_application_message(event['message_comtents'])
            await self._set_incoming_seqnum(event['message_contents']['MsgSeqNum'])
            self._last_receive_time = datetime.utcnow()
            return status
        elif event['type'] == 'error':
            logger.warning('error')
            return False
        elif event['type'] == 'disconnect':
            return False
        else:
            return False

    async def _handle_heartbeat(self) -> float:
        now = datetime.utcnow()
        seconds_since_last_send = (now - self._last_send_time).total_seconds()
        if seconds_since_last_send >= self.heartbeat_timeout and self.is_logged_on:
            await self.heartbeat()
            seconds_since_last_send = 0

        return self.heartbeat_timeout - seconds_since_last_send

    async def _handle_timeout(self) -> None:
        now = datetime.utcnow()
        seconds_since_last_receive = (now - self._last_receive_time).total_seconds()
        if seconds_since_last_receive - self.heartbeat_timeout > self.heartbeat_threshold and self.is_logged_on:
            await self.test_request('TEST')

    async def on_logon(self) -> None:
        pass

    async def __call__(self, send, receive) -> None:
        self._send, self._receive = send, receive

        event = await receive()

        if event['type'] == 'connected':
            logger.info('connected')

            await self.logon()

            ok = True
            while ok:
                try:
                    timeout = await self._handle_heartbeat()
                    event = await asyncio.wait_for(receive(), timeout=timeout)
                    ok = await self._handle_event(event)
                except asyncio.TimeoutError:
                    await self._handle_timeout()
        else:
            raise RuntimeError('Failed to connect')

        logger.info('disconnected')
