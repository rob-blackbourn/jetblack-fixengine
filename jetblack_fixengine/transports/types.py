"""Transport types"""

from enum import Enum, auto
from typing import Callable, Awaitable, Mapping, Optional


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


class TransportMessage:
    """A transport message"""

    def __init__(
            self,
            event: TransportEvent,
            buffer: Optional[bytes] = None
    ) -> None:
        self.event = event
        self.buffer = buffer if buffer is not None else b''

    def __str__(self) -> str:
        return f'{self.event}: {self.buffer!r}'


TransportEventHandler = Callable[
    [TransportMessage],
    Awaitable[Optional[TransportMessage]]
]
TransportEventHandlerMapping = Mapping[
    TransportState,
    Mapping[TransportEvent, TransportEventHandler]
]
