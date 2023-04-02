"""Admin types"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Awaitable, Callable, Mapping, Optional, cast


class AdminState(Enum):
    """Admin states"""
    DISCONNECTED = auto()
    LOGON_REQUESTED = auto()
    LOGON_EXPECTED = auto()
    AUTHENTICATING = auto()
    AUTHENTICATED = auto()
    REJECT_LOGON = auto()
    LOGGED_OUT = auto()
    ACKNOWLEDGE_LOGOUT = auto()
    ACKNOWLEDGE_HEARTBEAT = auto()
    TEST_HEARTBEAT = auto()
    SEND_TEST_HEARTBEAT = auto()
    VALIDATE_TEST_HEARTBEAT = auto()
    TEST_REQUEST_REQUESTED = auto()
    SEND_SEQUENCE_RESET = auto()
    SEQUENCE_RESET_REQUESTED = auto()
    SEQUENCE_RESET_RECEIVED = auto()
    SET_INCOMING_SEQNUM = auto()


class AdminEvent(Enum):
    """Admin events"""
    CONNECTED = auto()
    LOGON_SENT = auto()
    LOGON_RECEIVED = auto()
    LOGON_ACCEPTED = auto()
    LOGON_REJECTED = auto()
    LOGOUT_ACKNOWLEDGED = auto()
    REJECT_RECEIVED = auto()
    SEND_LOGOUT = auto()
    LOGOUT_RECEIVED = auto()
    HEARTBEAT_RECEIVED = auto()
    HEARTBEAT_ACKNOWLEDGED = auto()
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
    XML_MESSAGE_RECEIVED = auto()

    @classmethod
    def from_msg_type(cls, msg_type: str) -> AdminEvent:
        """Convert from a FIX message type.

        Args:
            msg_type (str): The FIX message type.

        Raises:
            ValueError: If there was no mapping.

        Returns:
            AdminEvent: The event.
        """
        if msg_type == 'LOGON':
            return cls.LOGON_RECEIVED
        elif msg_type == 'LOGOUT':
            return cls.LOGOUT_RECEIVED
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
        else:
            raise ValueError(f'invalid msg_type "{msg_type}"')


class AdminMessage:
    """An admin message"""

    def __init__(
            self,
            event: AdminEvent,
            fix: Optional[Mapping[str, Any]] = None
    ) -> None:
        self.event = event
        self.fix = fix if fix is not None else cast(Mapping[str, Any], {})

    def __str__(self) -> str:
        return f'{self.event}: {self.fix}'


AdminEventHandler = Callable[
    [AdminMessage],
    Awaitable[Optional[AdminMessage]]
]
AdminEventHandlerMapping = Mapping[
    AdminState,
    Mapping[AdminEvent, AdminEventHandler]
]
