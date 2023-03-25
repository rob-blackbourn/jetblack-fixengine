"""Connection State"""

from enum import Enum, auto
import logging
from typing import Callable, Awaitable, Mapping, Optional

LOGGER = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class TransportState(Enum):
    DISCONNECTED = auto()
    CONNECTED = auto()
    FIX = auto()
    TIMEOUT = auto()


class TransportEvent(Enum):
    CONNECTION_RECEIVED = 'connected'
    FIX_RECEIVED = 'fix'
    FIX_HANDLED = 'fix.handled'
    TIMEOUT_RECEIVED = 'timeout'
    TIMEOUT_HANDLED = 'timeout.handled'
    DISCONNECT_RECEIVED = 'disconnect'


TransportTransitionMapping = Mapping[
    TransportState,
    Mapping[TransportEvent, TransportState]
]


class TransportStateMachine:

    TRANSITIONS: TransportTransitionMapping = {
        TransportState.DISCONNECTED:  {
            TransportEvent.CONNECTION_RECEIVED: TransportState.CONNECTED
        },
        TransportState.CONNECTED: {
            TransportEvent.FIX_RECEIVED: TransportState.FIX,
            TransportEvent.TIMEOUT_RECEIVED: TransportState.TIMEOUT,
            TransportEvent.DISCONNECT_RECEIVED: TransportState.DISCONNECTED
        },
        TransportState.FIX: {
            TransportEvent.FIX_HANDLED: TransportState.CONNECTED
        },
        TransportState.TIMEOUT: {
            TransportEvent.TIMEOUT_HANDLED: TransportState.CONNECTED
        },
    }

    def __init__(self) -> None:
        self.state = TransportState.DISCONNECTED

    def transition(self, event_type: TransportEvent) -> TransportState:
        LOGGER.debug('Transition from %s with %s', self.state, event_type)
        try:
            self.state = self.TRANSITIONS[self.state][event_type]
            return self.state
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled event {self.state.name} -> {event_type}.',
            ) from error


class TransportMessage:

    def __init__(
            self,
            event: TransportEvent,
            buffer: Optional[bytes] = None
    ) -> None:
        self.event = event
        self.buffer = buffer

    def __str__(self) -> str:
        return f'{self.event}: {self.buffer!r}'


TransportEventHandler = Callable[
    [Optional[TransportMessage]],
    Awaitable[Optional[TransportMessage]]
]
TransportEventHandlerMapping = Mapping[
    TransportState,
    Mapping[TransportEvent, TransportEventHandler]
]


class TransportStateMachineAsync(TransportStateMachine):

    def __init__(
            self,
            handlers: TransportEventHandlerMapping
    ) -> None:
        super().__init__()
        self._handlers = handlers

    async def process(
            self,
            message: Optional[TransportMessage]
    ) -> TransportState:
        while message is not None:
            handler = self._handlers.get(self.state, {}).get(message.event)
            self.transition(message.event)
            if handler is None:
                break
            message = await handler(message)
        return self.state


Send = Callable[[TransportMessage], Awaitable[None]]
Receive = Callable[[], Awaitable[TransportMessage]]
TransportHandler = Callable[[Send, Receive], Awaitable[None]]
Middleware = Callable[[Send, Receive, TransportHandler], Awaitable[None]]
