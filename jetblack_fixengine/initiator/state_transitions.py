"""Admin state transitions"""

from typing import Mapping

from ..admin import (
    AdminEvent,
    AdminState
)


INITIATOR_ADMIN_TRANSITIONS: Mapping[AdminState, Mapping[AdminEvent, AdminState]] = {
    AdminState.DISCONNECTED: {
        AdminEvent.CONNECTED: AdminState.LOGON_REQUESTED
    },
    AdminState.LOGON_REQUESTED: {
        AdminEvent.LOGON_SENT: AdminState.LOGON_EXPECTED
    },
    AdminState.LOGON_EXPECTED: {
        AdminEvent.LOGON_RECEIVED: AdminState.AUTHENTICATED,
        AdminEvent.REJECT_RECEIVED: AdminState.DISCONNECTED
    },
    AdminState.AUTHENTICATED: {
        AdminEvent.HEARTBEAT_RECEIVED: AdminState.ACKNOWLEDGE_HEARTBEAT,
        AdminEvent.TEST_REQUEST_RECEIVED: AdminState.TEST_REQUEST_REQUESTED,
        AdminEvent.RESEND_REQUEST_RECEIVED: AdminState.SEQUENCE_RESET_REQUESTED,
        AdminEvent.SEQUENCE_RESET_RECEIVED: AdminState.SET_INCOMING_SEQNUM,
        AdminEvent.LOGOUT_RECEIVED: AdminState.ACKNOWLEDGE_LOGOUT,
        AdminEvent.TEST_HEARTBEAT_REQUIRED: AdminState.SEND_TEST_HEARTBEAT
    },
    AdminState.ACKNOWLEDGE_HEARTBEAT: {
        AdminEvent.HEARTBEAT_ACKNOWLEDGED: AdminState.AUTHENTICATED
    },
    AdminState.TEST_REQUEST_REQUESTED: {
        AdminEvent.TEST_REQUEST_SENT: AdminState.AUTHENTICATED
    },
    AdminState.SEQUENCE_RESET_REQUESTED: {
        AdminEvent.SEQUENCE_RESET_SENT: AdminState.AUTHENTICATED
    },
    AdminState.SET_INCOMING_SEQNUM: {
        AdminEvent.INCOMING_SEQNUM_SET: AdminState.AUTHENTICATED
    },
    AdminState.ACKNOWLEDGE_LOGOUT: {
        AdminEvent.LOGOUT_ACKNOWLEDGED: AdminState.DISCONNECTED
    },
    AdminState.SEND_TEST_HEARTBEAT: {
        AdminEvent.TEST_HEARTBEAT_SENT: AdminState.VALIDATE_TEST_HEARTBEAT
    },
    AdminState.VALIDATE_TEST_HEARTBEAT: {
        AdminEvent.TEST_HEARTBEAT_VALID: AdminState.AUTHENTICATED,
        AdminEvent.TEST_HEARTBEAT_INVALID: AdminState.REJECT_LOGON
    }
}
