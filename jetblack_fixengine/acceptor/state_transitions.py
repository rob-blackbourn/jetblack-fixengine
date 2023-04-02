"""Admin state transitions"""

from typing import Mapping

from ..admin.state_processor import AdminEvent, AdminState

ACCEPTOR_ADMIN_TRANSITIONS: Mapping[AdminState, Mapping[AdminEvent, AdminState]] = {
    AdminState.DISCONNECTED: {
        AdminEvent.CONNECTED: AdminState.LOGON_EXPECTED
    },
    AdminState.LOGON_EXPECTED: {
        AdminEvent.LOGON_RECEIVED: AdminState.AUTHENTICATING
    },
    AdminState.AUTHENTICATING: {
        AdminEvent.LOGON_ACCEPTED: AdminState.AUTHENTICATED,
        AdminEvent.LOGON_REJECTED: AdminState.REJECT_LOGON
    },
    AdminState.REJECT_LOGON: {
        AdminEvent.SEND_LOGOUT: AdminState.DISCONNECTED
    },
    AdminState.AUTHENTICATED: {
        AdminEvent.HEARTBEAT_RECEIVED: AdminState.AUTHENTICATED,
        AdminEvent.TEST_REQUEST_RECEIVED: AdminState.TEST_REQUEST_REQUESTED,
        AdminEvent.RESEND_REQUEST_RECEIVED: AdminState.SEND_SEQUENCE_RESET,
        AdminEvent.SEQUENCE_RESET_RECEIVED: AdminState.SET_INCOMING_SEQNUM,
        AdminEvent.LOGOUT_RECEIVED: AdminState.DISCONNECTED,
        AdminEvent.TEST_HEARTBEAT_REQUIRED: AdminState.SEND_TEST_HEARTBEAT
    },
    AdminState.TEST_REQUEST_REQUESTED: {
        AdminEvent.TEST_REQUEST_SENT: AdminState.AUTHENTICATED
    },
    AdminState.SEND_SEQUENCE_RESET: {
        AdminEvent.SEQUENCE_RESET_SENT: AdminState.AUTHENTICATED
    },
    AdminState.SET_INCOMING_SEQNUM: {
        AdminEvent.INCOMING_SEQNUM_SET: AdminState.AUTHENTICATED
    },
    AdminState.SEND_TEST_HEARTBEAT: {
        AdminEvent.TEST_HEARTBEAT_SENT: AdminState.VALIDATE_TEST_HEARTBEAT
    },
    AdminState.VALIDATE_TEST_HEARTBEAT: {
        AdminEvent.TEST_HEARTBEAT_VALID: AdminState.AUTHENTICATED,
        AdminEvent.TEST_HEARTBEAT_INVALID: AdminState.REJECT_LOGON
    }
}
