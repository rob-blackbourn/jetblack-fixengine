"""Acceptor state"""

from enum import Enum, auto


class AdminState(Enum):
    LOGGING_ON = auto()
    LOGGED_ON = auto()
    LOGGING_OFF = auto()
    LOGGED_OUT = auto()
    TEST_HEARTBEAT = auto()
    SYNCHRONISING = auto()
