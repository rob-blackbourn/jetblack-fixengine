"""Initiator state management"""

from enum import Enum, auto
import logging
from typing import Any, Awaitable, Callable, Mapping, Optional, Tuple

from ..types import Event

LOGGER = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class AdminState(Enum):
    """The state for initiator admin messages"""
    DISCONNECTED = auto()
    LOGON_REQUESTED = auto()
    LOGON_EXPECTED = auto()
    CONNECTED = auto()
    ACKNOWLEDGE_HEARTBEAT = auto()
    TEST_REQUEST_REQUESTED = auto()
    SEQUENCE_RESET_REQUESTED = auto()
    SET_INCOMING_SEQNUM = auto()
    ACKNOWLEDGE_LOGOUT = auto()


class AdminEventType(Enum):
    CONNECTED = 'connected'
    LOGON_RECEIVED = 'LOGON'
    LOGON_SENT = 'LOGON.sent'
    REJECT_RECEIVED = 'REJECT'
    HEARTBEAT_RECEIVED = 'HEARTBEAT'
    HEARTBEAT_ACK = 'HEARTBEAT.ack'
    TEST_REQUEST_RECEIVED = 'TEST_REQUEST'
    TEST_REQUEST_SENT = 'TEST_REQUEST.sent'
    RESEND_REQUEST_RECEIVED = 'RESEND_REQUEST'
    SEQUENCE_RESET_RECEIVED = 'SEQUENCE_RESET'
    SEQUENCE_RESET_SENT = 'SEQUENCE_RESET.sent'
    INCOMING_SEQNUM_SET = 'SEQUENCE_RESET.ack'
    XML_MESSAGE_RECEIVED = 'XML_MESSAGE'
    LOGOUT_RECEIVED = 'LOGOUT'
    LOGOUT_ACK = 'LOGOUT.ack'


AdminTransitionMapping = Mapping[
    Tuple[AdminState, AdminEventType],
    AdminState
]


class AdminStateMachine:
    """State machine for the initiator admin messages"""

    TRANSITIONS: Mapping[Tuple[AdminState, AdminEventType], AdminState] = {
        (AdminState.DISCONNECTED, AdminEventType.CONNECTED): AdminState.LOGON_REQUESTED,
        (AdminState.LOGON_REQUESTED, AdminEventType.LOGON_SENT): AdminState.LOGON_EXPECTED,
        (AdminState.LOGON_EXPECTED, AdminEventType.LOGON_RECEIVED): AdminState.CONNECTED,
        (AdminState.LOGON_EXPECTED, AdminEventType.REJECT_RECEIVED): AdminState.DISCONNECTED,

        # Acceptor heartbeet
        (AdminState.CONNECTED, AdminEventType.HEARTBEAT_RECEIVED): AdminState.ACKNOWLEDGE_HEARTBEAT,
        (AdminState.ACKNOWLEDGE_HEARTBEAT, AdminEventType.HEARTBEAT_ACK): AdminState.CONNECTED,

        # Test Request
        (AdminState.CONNECTED, AdminEventType.TEST_REQUEST_RECEIVED): AdminState.TEST_REQUEST_REQUESTED,
        (AdminState.TEST_REQUEST_REQUESTED, AdminEventType.TEST_REQUEST_SENT): AdminState.CONNECTED,

        # Resend Request
        (AdminState.CONNECTED, AdminEventType.RESEND_REQUEST_RECEIVED): AdminState.SEQUENCE_RESET_REQUESTED,
        (AdminState.SEQUENCE_RESET_REQUESTED, AdminEventType.SEQUENCE_RESET_SENT): AdminState.CONNECTED,

        # Sequence Reset
        (AdminState.CONNECTED, AdminEventType.SEQUENCE_RESET_RECEIVED): AdminState.SET_INCOMING_SEQNUM,
        (AdminState.SET_INCOMING_SEQNUM, AdminEventType.INCOMING_SEQNUM_SET): AdminState.CONNECTED,

        # Logout
        (AdminState.CONNECTED, AdminEventType.LOGOUT_RECEIVED): AdminState.ACKNOWLEDGE_LOGOUT,
        (AdminState.ACKNOWLEDGE_LOGOUT, AdminEventType.LOGOUT_ACK): AdminState.DISCONNECTED
    }

    def __init__(self):
        self.state = AdminState.DISCONNECTED

    def transition(self, event_type: AdminEventType) -> AdminState:
        LOGGER.debug('Transition from %s with %s', self.state, event_type)
        try:
            self.state = self.TRANSITIONS[(self.state, event_type)]
            return self.state
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled event {self.state.name} -> {event_type}.',
            ) from error

    def __str__(self) -> str:
        return f"InitiatorStateMachine: state={self.state}"

    __repr__ = __str__


class AdminEvent:

    def __init__(
            self,
            event_type: AdminEventType,
            message: Optional[Mapping[str, Any]] = None
    ) -> None:
        self.event_type = event_type
        self.message = message

    def __str__(self) -> str:
        return f'{self.event_type}: {self.message}'


AdminEventHandler = Callable[
    [Optional[AdminEvent]],
    Awaitable[Optional[AdminEvent]]
]
AdminEventHandlerMapping = Mapping[
    Tuple[AdminState, AdminEventType],
    AdminEventHandler
]


class AdminStateMachineHandler(AdminStateMachine):

    def __init__(
            self,
            state_handlers: AdminEventHandlerMapping
    ) -> None:
        super().__init__()
        self._handlers = state_handlers

    async def handle_event(
            self,
            event: Optional[AdminEvent]
    ) -> AdminState:
        while event is not None:
            handler = self._handlers.get((self.state, event.event_type))
            self.transition(event.event_type)
            if handler is None:
                break
            event = await handler(event)
        return self.state
