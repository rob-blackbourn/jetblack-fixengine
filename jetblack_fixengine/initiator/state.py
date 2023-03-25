"""Initiator state management"""

from __future__ import annotations

from enum import Enum, auto
import logging
from typing import Any, Awaitable, Callable, Mapping, Optional

LOGGER = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class AdminState(Enum):
    """The state for initiator admin messages"""
    DISCONNECTED = auto()
    LOGON_REQUESTED = auto()
    LOGON_EXPECTED = auto()
    AUTHENTICATED = auto()
    ACKNOWLEDGE_HEARTBEAT = auto()
    TEST_REQUEST_REQUESTED = auto()
    SEQUENCE_RESET_REQUESTED = auto()
    SET_INCOMING_SEQNUM = auto()
    ACKNOWLEDGE_LOGOUT = auto()


class AdminEvent(Enum):
    CONNECTED = auto()
    LOGON_RECEIVED = auto()
    LOGON_SENT = auto()
    REJECT_RECEIVED = auto()
    HEARTBEAT_RECEIVED = auto()
    HEARTBEAT_ACKNOWLEDGED = auto()
    TEST_REQUEST_RECEIVED = auto()
    TEST_REQUEST_SENT = auto()
    RESEND_REQUEST_RECEIVED = auto()
    SEQUENCE_RESET_RECEIVED = auto()
    SEQUENCE_RESET_SENT = auto()
    INCOMING_SEQNUM_SET = auto()
    XML_MESSAGE_RECEIVED = auto()
    LOGOUT_RECEIVED = auto()
    LOGOUT_ACKNOWLEDGED = auto()

    @classmethod
    def from_msg_type(cls, msg_type: str) -> AdminEvent:
        if msg_type == 'LOGON':
            return cls.LOGON_RECEIVED
        elif msg_type == 'REJECT':
            return cls.REJECT_RECEIVED
        elif msg_type == 'HEARTBEAT':
            return cls.HEARTBEAT_RECEIVED
        elif msg_type == 'TEST_REQUEST':
            return cls.TEST_REQUEST_RECEIVED
        elif msg_type == 'RESEND_REQUEST':
            return cls.RESEND_REQUEST_RECEIVED
        elif msg_type == 'SEQUENCE_RESET':
            return cls.SEQUENCE_RESET_RECEIVED
        elif msg_type == 'XML_MESSAGE':
            return cls.XML_MESSAGE_RECEIVED
        elif msg_type == 'LOGOUT':
            return cls.LOGON_RECEIVED
        else:
            raise ValueError(f'invalid msg_type "{msg_type}"')


class AdminStateMachine:
    """State machine for the initiator admin messages"""

    TRANSITIONS: Mapping[AdminState, Mapping[AdminEvent, AdminState]] = {
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
            AdminEvent.LOGOUT_RECEIVED: AdminState.ACKNOWLEDGE_LOGOUT
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
            message: Optional[Mapping[str, Any]] = None
    ) -> None:
        self.event = event
        self.message = message

    def __str__(self) -> str:
        return f'{self.event}: {self.message}'


AdminEventHandler = Callable[
    [Optional[AdminMessage]],
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

    async def handle_event(
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
