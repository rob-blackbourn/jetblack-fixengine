"""Admin state machine"""

import asyncio
from datetime import timezone
import logging
from typing import Optional
import uuid

from ..admin import (
    AdminState,
    AdminEvent,
    AdminMessage,
    AdminStateProcessor,
)
from ..time_provider import TimeProvider
from ..types import LoginError, FIXApplication
from ..utils.date_utils import wait_for_time_period

from .state_transitions import ACCEPTOR_ADMIN_TRANSITIONS
from .types import AbstractAcceptorEngine

LOGGER = logging.getLogger(__name__)


class AcceptorAdminStateMachine(AdminStateProcessor):

    def __init__(
            self,
            engine: AbstractAcceptorEngine,
            app: FIXApplication,
            time_provider: TimeProvider,
            cancellation_event: asyncio.Event
    ) -> None:
        super().__init__(
            ACCEPTOR_ADMIN_TRANSITIONS,
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

        self._engine = engine
        self._app = app
        self._time_provider = time_provider
        self._cancellation_event = cancellation_event
        self._test_heartbeat_message: Optional[str] = None

    async def _handle_connected(
            self,
            _admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        if self._engine.logon_time_range:
            start_time, end_time = self._engine.logon_time_range
            LOGGER.info(
                "Waiting for logging window between %s and %s",
                start_time,
                end_time
            )
            self._engine.logout_time = await wait_for_time_period(
                self._time_provider.now(self._engine.tz or timezone.utc),
                start_time,
                end_time,
                self._cancellation_event
            )

        return None

    async def _validate_logon(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        try:
            await self._app.on_logon(admin_message.fix, self._engine)
            return AdminMessage(AdminEvent.LOGON_ACCEPTED)
        except LoginError:
            LOGGER.info("Logon rejected")
        except:  # pylint: disable=bare-except
            LOGGER.exception("Logon failed")

        return AdminMessage(AdminEvent.LOGON_REJECTED)

    async def _send_logon(
            self,
            _admin_message: Optional[AdminMessage]
    ) -> Optional[AdminMessage]:
        await self._engine.send_message(
            'LOGON',
            {
                'EncryptMethod': 'NONE',
                'HeartBtInt': self._engine.heartbeat_timeout
            }
        )
        return None

    async def _send_logout(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        await self._engine.send_message('LOGOUT')
        await self._app.on_logout(admin_message.fix, self._engine)
        return None

    async def _receive_heartbeat(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        await self._app.on_heartbeat(admin_message.fix, self._engine)
        return None

    async def _receive_test_request(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        assert 'TestReqID' in admin_message.fix
        test_req_id = admin_message.fix['TestReqID']
        await self._engine.send_message(
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
        new_seq_no = await self._engine.session.get_outgoing_seqnum() + 2
        await self._engine.send_message(
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
        seqnum = admin_message.fix['NewSeqNo']
        await self._engine.session.set_incoming_seqnum(seqnum)
        return AdminMessage(AdminEvent.INCOMING_SEQNUM_SET)

    async def _receive_logout(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        await self._app.on_logout(admin_message.fix, self._engine)
        return None

    async def _send_test_heartbeat(
            self,
            _admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        self._test_heartbeat_message = str(uuid.uuid4())

        await self._engine.send_message(
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
