"""Initiator State"""

from enum import Enum
from typing import Mapping, Tuple

from ..connection_state import InvalidStateTransitionError


class AdminState(Enum):
    LOGON_REQUIRED = 'logon.required'
    LOGGED_ON = 'logon.ok'
    LOGGED_OUT = 'logout.done'


class AdminResponse(Enum):
    PROCESS_LOGON = 'logon.process'
    PROCESS_HEARTBEAT = 'heartbeat.process'
    PROCESS_TEST_REQUEST = 'test_request.process'
    PROCESS_RESEND_REQUEST = 'resend_request.process'
    PROCESS_SEQUENCE_RESET = 'sequence_reset.process'
    PROCESS_LOGOUT = 'logout.process'


AdminTransitionKey = Tuple[AdminState, str]
AdminTransitionValue = Tuple[AdminResponse, AdminState]
AdminTransitionMapping = Mapping[AdminTransitionKey, AdminTransitionValue]

ADMIN_TRANSITIONS: AdminTransitionMapping = {
    (AdminState.LOGON_REQUIRED, 'LOGON'): (
        AdminResponse.PROCESS_LOGON,
        AdminState.LOGGED_ON
    ),
    (AdminState.LOGGED_ON, 'HEARTBEAT'): (
        AdminResponse.PROCESS_HEARTBEAT,
        AdminState.LOGGED_ON
    ),
    (AdminState.LOGGED_ON, 'TEST_REQUEST'): (
        AdminResponse.PROCESS_TEST_REQUEST,
        AdminState.LOGGED_ON
    ),
    (AdminState.LOGGED_ON, 'RESEND_REQUEST'): (
        AdminResponse.PROCESS_RESEND_REQUEST,
        AdminState.LOGGED_ON
    ),
    (AdminState.LOGGED_ON, 'SEQUENCE_RESET'): (
        AdminResponse.PROCESS_SEQUENCE_RESET,
        AdminState.LOGGED_ON
    ),
    (AdminState.LOGGED_ON, 'LOGOUT'): (
        AdminResponse.PROCESS_LOGOUT,
        AdminState.LOGGED_OUT
    )
}


class AdminStateMachine:

    def __init__(self) -> None:
        self.state = AdminState.LOGON_REQUIRED

    def transition(self, msg_type: str) -> AdminResponse:
        try:
            response, self.state = ADMIN_TRANSITIONS[(self.state, msg_type)]
            return response
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled admin message type {self.state.name}"{msg_type}".',
            ) from error
