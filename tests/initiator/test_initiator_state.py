"""Tests for initiator state"""

from jetblack_fixengine.initiator.initiator_state import (
    AdminState,
    AdminResponse,
    AdminStateMachine,
    ConnectionState,
    ConnectionResponse,
    ConnectionStateMachine
)


def test_initiator_admin_state():
    """Test initiator state"""
    state_machine = AdminStateMachine()

    assert state_machine.state == AdminState.LOGON_REQUIRED

    response = state_machine.transition('LOGON')
    assert response == AdminResponse.PROCESS_LOGON
    assert state_machine.state == AdminState.LOGGED_ON

    response = state_machine.transition('HEARTBEAT')
    assert response == AdminResponse.PROCESS_HEARTBEAT
    assert state_machine.state == AdminState.LOGGED_ON

    response = state_machine.transition('TEST_REQUEST')
    assert response == AdminResponse.PROCESS_TEST_REQUEST
    assert state_machine.state == AdminState.LOGGED_ON

    response = state_machine.transition('RESEND_REQUEST')
    assert response == AdminResponse.PROCESS_RESEND_REQUEST
    assert state_machine.state == AdminState.LOGGED_ON

    response = state_machine.transition('SEQUENCE_RESET')
    assert response == AdminResponse.PROCESS_SEQUENCE_RESET
    assert state_machine.state == AdminState.LOGGED_ON

    response = state_machine.transition('LOGOUT')
    assert response == AdminResponse.PROCESS_LOGOUT
    assert state_machine.state == AdminState.LOGGED_OUT


def test_initiator_connection_state():
    state_machine = ConnectionStateMachine()

    assert state_machine.state == ConnectionState.DISCONNECTED

    response = state_machine.transition('connected')
    assert response == ConnectionResponse.PROCESS_CONNECTED
    assert state_machine.state == ConnectionState.CONNECTED

    response = state_machine.transition('fix')
    assert response == ConnectionResponse.PROCESS_FIX
    assert state_machine.state == ConnectionState.CONNECTED

    response = state_machine.transition('timeout')
    assert response == ConnectionResponse.PROCESS_TIMEOUT
    assert state_machine.state == ConnectionState.CONNECTED

    response = state_machine.transition('error')
    assert response == ConnectionResponse.PROCESS_ERROR
    assert state_machine.state == ConnectionState.DISCONNECTED

    # The error event sets the state to disconnect to manually reset it.
    state_machine.state = ConnectionState.CONNECTED
    response = state_machine.transition('disconnect')
    assert response == ConnectionResponse.PROCESS_DISCONNECT
    assert state_machine.state == ConnectionState.DISCONNECTED
