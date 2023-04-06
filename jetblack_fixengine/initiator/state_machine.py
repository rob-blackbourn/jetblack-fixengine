"""Admin state machine"""

import logging
from typing import Optional
import uuid

from ..admin import (
    AdminState,
    AdminEvent,
    AdminMessage,
    AdminStateProcessor,
)
from ..types import FIXApplication

from .state_transitions import INITIATOR_ADMIN_TRANSITIONS
from .types import AbstractInitiatorEngine

LOGGER = logging.getLogger(__name__)


class InitiatorAdminStateMachine(AdminStateProcessor):

    def __init__(
            self,
            engine: AbstractInitiatorEngine,
            app: FIXApplication
    ) -> None:
        super().__init__(
            INITIATOR_ADMIN_TRANSITIONS,
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
                    AdminEvent.LOGOUT_RECEIVED: self._acknowledge_logout,
                    AdminEvent.TEST_HEARTBEAT_REQUIRED: self._send_test_heartbeat,
                },
                AdminState.SEND_TEST_HEARTBEAT: {
                    AdminEvent.TEST_REQUEST_SENT: self._validate_test_heartbeat
                },
            }
        )
        self._engine = engine
        self._app = app
        self._test_heartbeat_message: Optional[str] = None

    async def _send_logon(
            self,
            _admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        """Send a logon message"""
        await self._engine.send_message(
            'LOGON',
            {
                'EncryptMethod': 'NONE',
                'HeartBtInt': self._engine.heartbeat_timeout
            }
        )
        return AdminMessage(AdminEvent.LOGON_SENT)

    async def _logon_received(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        await self._app.on_logon(admin_message.fix, self._engine)
        return None

    async def _acknowledge_heartbeat(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        await self._app.on_heartbeat(admin_message.fix, self._engine)
        return AdminMessage(AdminEvent.HEARTBEAT_ACKNOWLEDGED)

    async def _send_test_request(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        assert 'TestReqID' in admin_message.fix, "expected TestReqID"

        # Respond to the server with the token it sent.
        await self._engine.send_message(
            'TEST_REQUEST',
            {
                'TestReqID': admin_message.fix['TestReqID']
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

    async def _reset_incoming_seqnum(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        assert 'NewSeqNo' in admin_message.fix, "expected NewSeqNo"
        seqnum = admin_message.fix['NewSeqNo']
        await self._engine.session.set_incoming_seqnum(seqnum)
        return AdminMessage(AdminEvent.SEQUENCE_RESET_SENT)

    async def _acknowledge_logout(
            self,
            admin_message: AdminMessage
    ) -> Optional[AdminMessage]:
        assert admin_message.fix is not None
        await self._app.on_logout(admin_message.fix, self._engine)
        return AdminMessage(AdminEvent.LOGOUT_ACKNOWLEDGED)

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
