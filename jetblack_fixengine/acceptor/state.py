"""Acceptor state"""

from __future__ import annotations

from enum import Enum, auto
import logging
from typing import Any, Awaitable, Callable, Mapping, Optional, cast

LOGGER = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class AdminState(Enum):
    DISCONNECTED = auto()
    LOGON_EXPECTED = auto()
    AUTHENTICATING = auto()
    AUTHENTICATED = auto()
    REJECT_LOGON = auto()
    LOGGED_OUT = auto()
    TEST_HEARTBEAT = auto()
    SYNCHRONISING = auto()
    TEST_REQUEST_REQUESTED = auto()
    SEND_SEQUENCE_RESET = auto()
    SEQUENCE_RESET_RECEIVED = auto()
    SET_INCOMING_SEQNUM = auto()
    SEND_TEST_HEARTBEAT = auto()
    VALIDATE_TEST_HEARTBEAT = auto()


class AdminEvent(Enum):
    CONNECTED = auto()
    LOGON_RECEIVED = auto()
    LOGON_ACCEPTED = auto()
    LOGON_REJECTED = auto()
    LOGOUT_RECEIVED = auto()
    SEND_LOGOUT = auto()
    HEARTBEAT_RECEIVED = auto()
    TEST_REQUEST_RECEIVED = auto()
    TEST_REQUEST_SENT = auto()
    RESEND_REQUEST_RECEIVED = auto()
    SEQUENCE_RESET_RECEIVED = auto()
    SEQUENCE_RESET_SENT = auto()
    INCOMING_SEQNUM_SET = auto()
    TEST_HEARTBEAT_REQUIRED = auto()
    TEST_HEARTBEAT_SENT = auto()
    TEST_HEARTBEAT_VALID = auto()
    TEST_HEARTBEAT_INVALID = auto()

    @classmethod
    def from_msg_type(cls, msg_type: str) -> AdminEvent:
        if msg_type == 'LOGON':
            return cls.LOGON_RECEIVED
        elif msg_type == 'LOGOUT':
            return cls.LOGOUT_RECEIVED
        elif msg_type == 'HEARTBEAT':
            return cls.HEARTBEAT_RECEIVED
        elif msg_type == 'TEST_REQUEST':
            return cls.TEST_REQUEST_RECEIVED
        elif msg_type == 'RESEND_REQUEST':
            return cls.RESEND_REQUEST_RECEIVED
        elif msg_type == 'SEQUENCE_RESET':
            return cls.SEQUENCE_RESET_RECEIVED
        else:
            raise ValueError(f'invalid msg_type "{msg_type}"')


class AdminStateMachine:
    """State machine for the admin messages"""

    TRANSITIONS: Mapping[AdminState, Mapping[AdminEvent, AdminState]] = {
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

    def __init__(self):
        self.state = AdminState.DISCONNECTED

    def transition(self, event: AdminEvent) -> AdminState:
        LOGGER.debug('Transition from %s with %s', self.state, event)
        try:
            self.state = self.TRANSITIONS[self.state][event]
            return self.state
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled event {self.state.name} -> {event}.',
            ) from error

    def __str__(self) -> str:
        return f"AdminStateMachine: state={self.state}"

    __repr__ = __str__


class AdminMessage:

    def __init__(
            self,
            event: AdminEvent,
            body: Optional[Mapping[str, Any]] = None
    ) -> None:
        self.event = event
        self.body = body if body is not None else cast(Mapping[str, Any], {})

    def __str__(self) -> str:
        return f'{self.event}: {self.body}'


AdminEventHandler = Callable[
    [AdminMessage],
    Awaitable[Optional[AdminMessage]]
]
AdminEventHandlerMapping = Mapping[
    AdminState,
    Mapping[AdminEvent, AdminEventHandler]
]


class AdminStateMachineAsync(AdminStateMachine):

    def __init__(
            self,
            state_handlers: AdminEventHandlerMapping
    ) -> None:
        super().__init__()
        self._handlers = state_handlers

    async def process(
            self,
            message: Optional[AdminMessage]
    ) -> AdminState:
        while message is not None:
            handler = self._handlers.get(self.state, {}).get(message.event)
            self.transition(message.event)
            if handler is None:
                break
            message = await handler(message)
        return self.state
