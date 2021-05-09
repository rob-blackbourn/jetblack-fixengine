"""Acceptor state"""

from enum import Enum, auto
from typing import Mapping, Tuple


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class AdminState(Enum):
    LOGGING_ON = auto()
    LOGGED_ON = auto()
    LOGGING_OFF = auto()
    LOGGED_OUT = auto()
    TEST_HEARTBEAT = auto()
    SYNCHRONISING = auto()


class ConnectionState(Enum):
    DISCONNECTED = 'disconnected'
    CONNECTED = 'connected'
    ERROR = 'error'


class ConnectionResponse(Enum):
    PROCESS_CONNECTED = 'connected.process'
    PROCESS_FIX = 'fix.process'
    PROCESS_TIMEOUT = 'timeout.process'
    PROCESS_ERROR = 'error.process'
    PROCESS_DISCONNECT = 'disconnect.process'


ConnectionTransitionKey = Tuple[ConnectionState, str]
ConnectionTransitionValue = Tuple[ConnectionResponse, ConnectionState]
ConnectionTransitionMapping = Mapping[ConnectionTransitionKey,
                                      ConnectionTransitionValue]

CONNECTION_TRANSITIONS: ConnectionTransitionMapping = {
    (ConnectionState.DISCONNECTED, 'connected'): (
        ConnectionResponse.PROCESS_CONNECTED,
        ConnectionState.CONNECTED
    ),
    (ConnectionState.CONNECTED, 'fix'): (
        ConnectionResponse.PROCESS_FIX,
        ConnectionState.CONNECTED
    ),
    (ConnectionState.CONNECTED, 'timeout'): (
        ConnectionResponse.PROCESS_TIMEOUT,
        ConnectionState.CONNECTED
    ),
    (ConnectionState.CONNECTED, 'error'): (
        ConnectionResponse.PROCESS_ERROR,
        ConnectionState.DISCONNECTED
    ),
    (ConnectionState.CONNECTED, 'disconnect'): (
        ConnectionResponse.PROCESS_DISCONNECT,
        ConnectionState.DISCONNECTED
    )
}


class ConnectionStateMachine:

    def __init__(self) -> None:
        self.state = ConnectionState.DISCONNECTED

    def transition(self, event: str) -> ConnectionResponse:
        try:
            response, self.state = CONNECTION_TRANSITIONS[(self.state, event)]
            return response
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled event {self.state.name}"{event}".',
            ) from error
