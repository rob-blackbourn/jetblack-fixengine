"""Connection State"""

from enum import Enum, auto
import logging
from typing import Awaitable, Callable, Mapping, Optional

from .types import Message

LOGGER = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTED = auto()
    FIX = auto()
    TIMEOUT = auto()


class ConnectionEvent(Enum):
    CONNECTION_RECEIVED = 'connected'
    FIX_RECEIVED = 'fix'
    FIX_HANDLED = 'fix.handled'
    TIMEOUT_RECEIVED = 'timeout'
    TIMEOUT_HANDLED = 'timeout.handled'
    DISCONNECT_RECEIVED = 'disconnect'


ConnectionTransitionMapping = Mapping[
    ConnectionState,
    Mapping[ConnectionEvent, ConnectionState]
]

ConnectionEventHandler = Callable[
    [Optional[Message]],
    Awaitable[Optional[Message]]
]
ConnectionEventHandlerMapping = Mapping[
    ConnectionState,
    Mapping[ConnectionEvent, ConnectionEventHandler]
]


class ConnectionStateMachine:

    TRANSITIONS: ConnectionTransitionMapping = {
        ConnectionState.DISCONNECTED:  {
            ConnectionEvent.CONNECTION_RECEIVED: ConnectionState.CONNECTED
        },
        ConnectionState.CONNECTED: {
            ConnectionEvent.FIX_RECEIVED: ConnectionState.FIX,
            ConnectionEvent.TIMEOUT_RECEIVED: ConnectionState.TIMEOUT,
            ConnectionEvent.DISCONNECT_RECEIVED: ConnectionState.DISCONNECTED
        },
        ConnectionState.FIX: {
            ConnectionEvent.FIX_HANDLED: ConnectionState.CONNECTED
        },
        ConnectionState.TIMEOUT: {
            ConnectionEvent.TIMEOUT_HANDLED: ConnectionState.CONNECTED
        },
    }

    def __init__(self) -> None:
        self.state = ConnectionState.DISCONNECTED

    def transition(self, event_type: ConnectionEvent) -> ConnectionState:
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

    async def process(
            self,
            message: Optional[Message]
    ) -> ConnectionState:
        while message is not None:
            event = ConnectionEvent(message['type'])
            handler = self._handlers.get(self.state, {}).get(event)
            self.transition(event)
            if handler is None:
                break
            message = await handler(message)
        return self.state
