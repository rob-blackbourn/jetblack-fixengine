"""Tests for initiator state"""

from jetblack_fixengine.initiator.state import (
    AdminState,
    AdminEvent,
    AdminStateMachine,
)

from jetblack_fixengine.connection_state import (
    ConnectionState,
    ConnectionEvent,
    ConnectionStateMachine
)


def test_initiator_admin_state():
    """Test initiator state"""
    state_machine = AdminStateMachine()

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
    state_machine = ConnectionStateMachine()

    assert state_machine.state == ConnectionState.DISCONNECTED

    response = state_machine.transition(
        ConnectionEvent.CONNECTION_RECEIVED)
    assert response == ConnectionState.CONNECTED

    response = state_machine.transition(ConnectionEvent.FIX_RECEIVED)
    assert response == ConnectionState.FIX

    response = state_machine.transition(ConnectionEvent.FIX_HANDLED)
    assert response == ConnectionState.CONNECTED

    response = state_machine.transition(ConnectionEvent.TIMEOUT_RECEIVED)
    assert response == ConnectionState.TIMEOUT

    response = state_machine.transition(ConnectionEvent.TIMEOUT_HANDLED)
    assert response == ConnectionState.CONNECTED

    response = state_machine.transition(
        ConnectionEvent.DISCONNECT_RECEIVED)
    assert response == ConnectionState.DISCONNECTED
