"""Connection State"""

from enum import Enum, auto
import logging
from typing import Callable, Awaitable, Mapping, Optional

LOGGER = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class TransportState(Enum):
    """Transport states"""
    DISCONNECTED = auto()
    CONNECTED = auto()
    FIX = auto()
    TIMEOUT = auto()


class TransportEvent(Enum):
    """Transport events"""
    CONNECTION_RECEIVED = auto()
    FIX_RECEIVED = auto()
    FIX_HANDLED = auto()
    TIMEOUT_RECEIVED = auto()
    TIMEOUT_HANDLED = auto()
    DISCONNECT_RECEIVED = auto()


TransportTransitionMapping = Mapping[
    TransportState,
    Mapping[TransportEvent, TransportState]
]


class TransportStateMachine:
    """The transport state machine"""

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

    def transition(self, event: TransportEvent) -> TransportState:
        """Transition from the current state to a new state given an event.

        Args:
            event (TransportEvent): The event.

        Raises:
            InvalidStateTransitionError: If the transition was invalid.

        Returns:
            TransportState: The new state.
        """
        LOGGER.debug('Transition from %s with %s', self.state, event)
        try:
            self.state = self.TRANSITIONS[self.state][event]
            return self.state
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled event {self.state.name} -> {event.name}.',
            ) from error


class TransportMessage:
    """A transport message"""

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
    """A transport state machine with async bindings"""

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
        """Process a transport message

        Args:
            message (Optional[TransportMessage]): The message

        Returns:
            TransportState: The new state.
        """
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
