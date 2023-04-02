"""Tests for initiator state"""

from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional, Tuple

import pytest

from jetblack_fixparser.loader import load_yaml_protocol
from jetblack_fixparser.fix_message import FixMessageFactory

from jetblack_fixengine.admin.state_processor import (
    AdminState,
    AdminEvent,
    AdminStateTransition,
    AdminMessage
)

from jetblack_fixengine.transports.state_transitions import (
    TransportState,
    TransportEvent,
    TransportStateTransitions
)

from jetblack_fixengine.initiator.admin_state_machine import InitiatorAdminStateMachine
from jetblack_fixengine.initiator.state import INITIATOR_ADMIN_TRANSITIONS

from ..mocks import MockSession
from .mocks import MockInitiatorApp


@pytest.mark.asyncio
async def test_logon() -> None:
    """Test for login"""
    sender_comp_id = "INITIATOR"
    target_comp_id = "ACCEPTOR"
    session = MockSession(sender_comp_id, target_comp_id, 0, 0)
    protocol = load_yaml_protocol('etc/FIX44.yaml')
    fix_message_factory = FixMessageFactory(
        protocol,
        sender_comp_id,
        target_comp_id
    )

    messages: List[Tuple[str, Optional[Mapping[str, Any]]]] = []

    async def send_message(
            msg_type: str,
            message: Optional[Mapping[str, Any]]
    ) -> None:
        messages.append((msg_type, message))

    initiator = MockInitiatorApp(
        session,
        fix_message_factory,
        30,
        1,
        send_message
    )

    state_machine = InitiatorAdminStateMachine(initiator)

    state = await state_machine.process(AdminMessage(AdminEvent.CONNECTED))
    assert state == AdminState.LOGON_EXPECTED

    state = await state_machine.process(AdminMessage(
        AdminEvent.LOGON_RECEIVED,
        {
            'MsgType': 'LOGON',
            'MsgSeqNum': 0,
            'SenderCompID': sender_comp_id,
            'TargetCompID': target_comp_id,
            'SendingTime': datetime(2000, 1, 1, tzinfo=timezone.utc),
            'EncryptMethod': "NONE",
            'HeartBtInt': 30
        }
    ))
    assert state == AdminState.AUTHENTICATED


def test_initiator_admin_state():
    """Test initiator state"""
    state_machine = AdminStateTransition(INITIATOR_ADMIN_TRANSITIONS)

    assert state_machine.state == AdminState.DISCONNECTED

    response = state_machine.transition(AdminEvent.CONNECTED)
    assert response == AdminState.LOGON_REQUESTED

    response = state_machine.transition(AdminEvent.LOGON_SENT)
    assert response == AdminState.LOGON_EXPECTED

    response = state_machine.transition(AdminEvent.LOGON_RECEIVED)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEvent.HEARTBEAT_RECEIVED)
    assert response == AdminState.ACKNOWLEDGE_HEARTBEAT

    response = state_machine.transition(AdminEvent.HEARTBEAT_ACKNOWLEDGED)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEvent.TEST_REQUEST_RECEIVED)
    assert response == AdminState.TEST_REQUEST_REQUESTED

    response = state_machine.transition(AdminEvent.TEST_REQUEST_SENT)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEvent.RESEND_REQUEST_RECEIVED)
    assert response == AdminState.SEQUENCE_RESET_REQUESTED

    response = state_machine.transition(AdminEvent.SEQUENCE_RESET_SENT)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEvent.SEQUENCE_RESET_RECEIVED)
    assert response == AdminState.SET_INCOMING_SEQNUM

    response = state_machine.transition(AdminEvent.INCOMING_SEQNUM_SET)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEvent.LOGOUT_RECEIVED)
    assert response == AdminState.ACKNOWLEDGE_LOGOUT

    response = state_machine.transition(AdminEvent.LOGOUT_ACKNOWLEDGED)
    assert response == AdminState.DISCONNECTED


def test_initiator_connection_state():
    state_machine = TransportStateTransitions()

    assert state_machine.state == TransportState.DISCONNECTED

    response = state_machine.transition(
        TransportEvent.CONNECTION_RECEIVED)
    assert response == TransportState.CONNECTED

    response = state_machine.transition(TransportEvent.FIX_RECEIVED)
    assert response == TransportState.FIX

    response = state_machine.transition(TransportEvent.FIX_HANDLED)
    assert response == TransportState.CONNECTED

    response = state_machine.transition(TransportEvent.TIMEOUT_RECEIVED)
    assert response == TransportState.TIMEOUT

    response = state_machine.transition(TransportEvent.TIMEOUT_HANDLED)
    assert response == TransportState.CONNECTED

    response = state_machine.transition(
        TransportEvent.DISCONNECT_RECEIVED)
    assert response == TransportState.DISCONNECTED
