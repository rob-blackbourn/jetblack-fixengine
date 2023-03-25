"""Connection State"""

from enum import Enum, auto
import logging
from typing import Awaitable, Callable, Mapping, Optional, Tuple

from .types import Event

LOGGER = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTED = auto()
    FIX = auto()
    TIMEOUT = auto()


class ConnectionEventType(Enum):
    CONNECTION_RECEIVED = 'connected'
    FIX_RECEIVED = 'fix'
    FIX_HANDLED = 'fix.handled'
    TIMEOUT_RECEIVED = 'timeout'
    TIMEOUT_HANDLED = 'timeout.handled'
    DISCONNECT_RECEIVED = 'disconnect'


ConnectionTransitionMapping = Mapping[
    ConnectionState,
    Mapping[ConnectionEventType, ConnectionState]
]

ConnectionEventHandler = Callable[
    [Optional[Event]],
    Awaitable[Optional[Event]]
]
ConnectionEventHandlerMapping = Mapping[
    ConnectionState,
    Mapping[ConnectionEventType, ConnectionEventHandler]
]


class ConnectionStateMachine:

    TRANSITIONS: ConnectionTransitionMapping = {
        ConnectionState.DISCONNECTED:  {
            ConnectionEventType.CONNECTION_RECEIVED: ConnectionState.CONNECTED
        },
        ConnectionState.CONNECTED: {
            ConnectionEventType.FIX_RECEIVED: ConnectionState.FIX,
            ConnectionEventType.TIMEOUT_RECEIVED: ConnectionState.TIMEOUT,
            ConnectionEventType.DISCONNECT_RECEIVED: ConnectionState.DISCONNECTED
        },
        ConnectionState.FIX: {
            ConnectionEventType.FIX_HANDLED: ConnectionState.CONNECTED
        },
        ConnectionState.TIMEOUT: {
            ConnectionEventType.TIMEOUT_HANDLED: ConnectionState.CONNECTED
        },
    }

    def __init__(self) -> None:
        self.state = ConnectionState.DISCONNECTED

    def transition(self, event_type: ConnectionEventType) -> ConnectionState:
        LOGGER.debug('Transition from %s with %s', self.state, event_type)
        try:
            self.state = self.TRANSITIONS[self.state][event_type]
            return self.state
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled event {self.state.name} -> {event_type}.',
            ) from error


class ConnectionStateMachineAsync(ConnectionStateMachine):

    def __init__(
            self,
            handlers: ConnectionEventHandlerMapping
    ) -> None:
        super().__init__()
        self._handlers = handlers

    async def handle_event(
            self,
            event: Optional[Event]
    ) -> ConnectionState:
        while event is not None:
            event_type = ConnectionEventType(event['type'])
            handler = self._handlers.get(self.state, {}).get(event_type)
            self.transition(event_type)
            if handler is None:
                break
            event = await handler(event)
        return self.state
