"""Acceptor handler"""

from abc import ABCMeta
import asyncio
from datetime import datetime, time, tzinfo, timezone
import logging
from typing import (
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

from ..transports.state import (
    TransportState,
    TransportEvent,
    TransportStateMachineAsync,
    TransportMessage,
    Send,
    Receive
)
from ..types import Store
from ..utils.date_utils import wait_for_time_period

from .state import (
    AdminState,
    AdminEvent,
    AdminMessage,
    AdminStateMachineAsync,
)
from .types import AbstractAcceptor

LOGGER = logging.getLogger(__name__)


EPOCH_UTC = datetime.fromtimestamp(0, timezone.utc)


class Acceptor(AbstractAcceptor, metaclass=ABCMeta):
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

        self._transport_state_machine = TransportStateMachineAsync(
            {
                TransportState.DISCONNECTED: {
                    TransportEvent.CONNECTION_RECEIVED: self._handle_transport_connected
                },
                TransportState.CONNECTED: {
                    TransportEvent.FIX_RECEIVED: self._handle_fix,
                    TransportEvent.TIMEOUT_RECEIVED: self._handle_timeout,
                    TransportEvent.DISCONNECT_RECEIVED: self._handle_disconnect
                }
            }
        )

        self._admin_state_machine = AdminStateMachineAsync(
            {
                AdminState.DISCONNECTED: {
                    AdminEvent.CONNECTED: self._handle_connected
                },
                AdminState.LOGON_EXPECTED: {
                    AdminEvent.LOGON_RECEIVED: self._validate_logon
                },
                AdminState.AUTHENTICATING: {
                    AdminEvent.LOGON_ACCEPTED: self._send_logon,
                    AdminEvent.LOGON_REJECTED: self._send_logout
                },
                AdminState.AUTHENTICATED: {
                    AdminEvent.HEARTBEAT_RECEIVED: self._receive_heartbeat,
                    AdminEvent.TEST_REQUEST_RECEIVED: self._receive_test_request,
                    AdminEvent.RESEND_REQUEST_RECEIVED: self._send_sequence_reset,
                    AdminEvent.SEQUENCE_RESET_RECEIVED: self._handle_sequence_reset,
                    AdminEvent.LOGOUT_RECEIVED: self._receive_logout,
                    AdminEvent.TEST_HEARTBEAT_REQUIRED: self._send_test_heartbeat,
                },
                AdminState.SEND_TEST_HEARTBEAT: {
                    AdminEvent.TEST_REQUEST_SENT: self._validate_test_heartbeat
                },
                AdminState.REJECT_LOGON: {
                    AdminEvent.SEND_LOGOUT: self._send_logout
                }
            }
        )

        self._test_heartbeat_message: Optional[str] = None
        self._last_send_time_utc: datetime = EPOCH_UTC
        self._last_receive_time_utc: datetime = EPOCH_UTC
        self._store = store
        self._session = self._store.get_session(sender_comp_id, target_comp_id)
        self._send: Optional[Send] = None
        self._receive: Optional[Receive] = None
        self._logout_time: Optional[datetime] = None

    async def _handle_connected(
            self,
            _admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        if self.logon_time_range:
            start_time, end_time = self.logon_time_range
            LOGGER.info(
                "Waiting for logging window between %s and %s",
                start_time,
                end_time
            )
            self._logout_time = await wait_for_time_period(
                datetime.now(tz=self.tz),
                start_time,
                end_time,
                self.cancellation_event
            )

        self._last_send_time_utc = datetime.now(timezone.utc)
        return None

    async def _validate_logon(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        if await self.on_logon(admin_message.fix):
            return AdminMessage(AdminEvent.LOGON_ACCEPTED)
        else:
            return AdminMessage(AdminEvent.LOGON_REJECTED)

    async def _send_logon(
            self,
            _admin_message: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        await self.send_message(
            'LOGON',
            {
                'EncryptMethod': 'NONE',
                'HeartBtInt': self.heartbeat_timeout
            }
        )
        return None

    async def _send_logout(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        await self.send_message('LOGOUT')
        await self.on_logout(admin_message.fix)
        return None

    async def _receive_heartbeat(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        await self.on_heartbeat(admin_message.fix)
        return None

    async def _receive_test_request(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        assert 'TestReqID' in admin_message.fix
        test_req_id = admin_message.fix['TestReqID']
        await self.send_message(
            'TEST_REQUEST',
            {
                'TestReqID': test_req_id
            }
        )

        return AdminMessage(AdminEvent.TEST_REQUEST_SENT)

    async def _send_sequence_reset(
            self,
            _admin_message: AdminMessage
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

    async def _handle_sequence_reset(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        assert 'NewSeqNo' in admin_message.fix
        await self._set_incoming_seqnum(admin_message.fix['NewSeqNo'])
        return AdminMessage(AdminEvent.INCOMING_SEQNUM_SET)

    async def _receive_logout(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        await self.on_logout(admin_message.fix)
        return None

    async def _send_test_heartbeat(
            self,
            _admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        self._test_heartbeat_message = str(uuid.uuid4())

        await self.send_message(
            'TEST_REQUEST',
            {
                'TestReqID': self._test_heartbeat_message
            }
        )
        return AdminMessage(AdminEvent.TEST_HEARTBEAT_SENT)

    async def _validate_test_heartbeat(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        assert 'TestReqID' in admin_message.fix
        if admin_message.fix['TestReqID'] == self._test_heartbeat_message:
            return AdminMessage(AdminEvent.TEST_HEARTBEAT_VALID)
        else:
            return AdminMessage(AdminEvent.TEST_HEARTBEAT_INVALID)

    async def _handle_transport_connected(
            self,
            _transport_message: TransportMessage
    ) -> Optional[TransportMessage]:
        LOGGER.info('connected')
        await self._admin_state_machine.process(
            AdminMessage(AdminEvent.CONNECTED)
        )
        return None

    async def _handle_timeout(
            self,
            _transport_message: TransportMessage
    ) -> Optional[TransportMessage]:
        if self._admin_state_machine.state != AdminState.AUTHENTICATED:
            raise RuntimeError('Make a state for this')

        now_utc = datetime.now(timezone.utc)
        seconds_since_last_receive = (
            now_utc - self._last_receive_time_utc
        ).total_seconds()
        if seconds_since_last_receive - self.heartbeat_timeout > self.heartbeat_threshold:
            await self._admin_state_machine.process(
                AdminMessage(AdminEvent.TEST_HEARTBEAT_REQUIRED)
            )

        return TransportMessage(TransportEvent.TIMEOUT_HANDLED)

    async def _handle_admin_message(self, message: Mapping[str, Any]) -> None:
        assert 'MsgType' in message

        LOGGER.info('admin message: %s', message)

        await self.on_admin_message(message)

        await self._admin_state_machine.process(
            AdminMessage(
                AdminEvent.from_msg_type(message['MsgType']),
                message
            )
        )

    async def _handle_fix(
            self,
            transport_message: TransportMessage
    ) -> Optional[TransportMessage]:
        await self._session.save_message(transport_message.buffer)

        fix_message = self.fix_message_factory.decode(transport_message.buffer)
        LOGGER.info('Received %s', fix_message.message)

        msgcat = cast(str, fix_message.meta_data.msgcat)
        if msgcat == 'admin':
            await self._handle_admin_message(fix_message.message)
        else:
            await self.on_application_message(fix_message.message)

        msg_seq_num: int = cast(int, fix_message.message['MsgSeqNum'])
        await self._set_incoming_seqnum(msg_seq_num)

        self._last_receive_time_utc = datetime.now(timezone.utc)

        return TransportMessage(TransportEvent.FIX_HANDLED)

    async def _handle_error(
            self,
            transport_message: TransportMessage
    ) -> None:
        LOGGER.warning('error: %s', transport_message)

    async def _handle_disconnect(
            self,
            _transport_message: Optional[TransportMessage]
    ) -> Optional[TransportMessage]:
        LOGGER.info('Disconnected')
        return None

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
        if datetime.now(tz=self.tz) >= logout_time:
            await self._admin_state_machine.process(
                AdminMessage(AdminEvent.SEND_LOGOUT)
            )

    async def _send_heartbeat_if_required(self) -> float:
        if self._transport_state_machine.state != TransportState.CONNECTED:
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

        seconds_till_next_heartbeat = self.heartbeat_timeout - seconds_since_last_send

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

    async def _set_incoming_seqnum(self, seqnum: int) -> None:
        await self._session.set_incoming_seqnum(seqnum)

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
        send_time_utc = datetime.now(timezone.utc)
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
