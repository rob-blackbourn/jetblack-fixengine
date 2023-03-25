"""Tests for initiator state"""

from jetblack_fixengine.initiator.state import (
    AdminState,
    AdminEventType,
    AdminStateMachine,
)

from jetblack_fixengine.connection_state import (
    ConnectionState,
    ConnectionEventType,
    ConnectionStateMachine
)


def test_initiator_admin_state():
    """Test initiator state"""
    state_machine = AdminStateMachine()

    assert state_machine.state == AdminState.DISCONNECTED

    response = state_machine.transition(AdminEventType.CONNECTED)
    assert response == AdminState.LOGON_REQUESTED

    response = state_machine.transition(AdminEventType.LOGON_SENT)
    assert response == AdminState.LOGON_EXPECTED

    response = state_machine.transition(AdminEventType.LOGON_RECEIVED)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEventType.HEARTBEAT_RECEIVED)
    assert response == AdminState.ACKNOWLEDGE_HEARTBEAT

    response = state_machine.transition(AdminEventType.HEARTBEAT_ACK)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEventType.TEST_REQUEST_RECEIVED)
    assert response == AdminState.TEST_REQUEST_REQUESTED

    response = state_machine.transition(AdminEventType.TEST_REQUEST_SENT)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEventType.RESEND_REQUEST_RECEIVED)
    assert response == AdminState.SEQUENCE_RESET_REQUESTED

    response = state_machine.transition(AdminEventType.SEQUENCE_RESET_SENT)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEventType.SEQUENCE_RESET_RECEIVED)
    assert response == AdminState.SET_INCOMING_SEQNUM

    response = state_machine.transition(AdminEventType.INCOMING_SEQNUM_SET)
    assert response == AdminState.AUTHENTICATED

    response = state_machine.transition(AdminEventType.LOGOUT_RECEIVED)
    assert response == AdminState.ACKNOWLEDGE_LOGOUT

    response = state_machine.transition(AdminEventType.LOGOUT_ACK)
    assert response == AdminState.DISCONNECTED


def test_initiator_connection_state():
    state_machine = ConnectionStateMachine()

    assert state_machine.state == ConnectionState.DISCONNECTED

    response = state_machine.transition(
        ConnectionEventType.CONNECTION_RECEIVED)
    assert response == ConnectionState.CONNECTED

    response = state_machine.transition(ConnectionEventType.FIX_RECEIVED)
    assert response == ConnectionState.FIX

    response = state_machine.transition(ConnectionEventType.FIX_HANDLED)
    assert response == ConnectionState.CONNECTED

    response = state_machine.transition(ConnectionEventType.TIMEOUT_RECEIVED)
    assert response == ConnectionState.TIMEOUT

    response = state_machine.transition(ConnectionEventType.TIMEOUT_HANDLED)
    assert response == ConnectionState.CONNECTED

    response = state_machine.transition(
        ConnectionEventType.DISCONNECT_RECEIVED)
    assert response == ConnectionState.DISCONNECTED
