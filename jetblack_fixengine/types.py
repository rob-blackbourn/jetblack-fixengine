"""Types"""

from abc import ABCMeta, abstractmethod
from typing import Any, Awaitable, Callable, Mapping, Optional, Tuple

from jetblack_fixparser.fix_message import FixMessageFactory


class Session(metaclass=ABCMeta):
    """A FIX session"""

    @property
    @abstractmethod
    def sender_comp_id(self) -> str:
        """The sender comp id."""

    @property
    @abstractmethod
    def target_comp_id(self) -> str:
        """The target comp id."""

    @abstractmethod
    async def get_seqnums(self) -> Tuple[int, int]:
        """Get both seqnums.

        Returns:
            Tuple[int, int]: A tuple of the outgoing and incoming seqnums
        """

    @abstractmethod
    async def set_seqnums(self, outgoing_seqnum: int, incoming_seqnum: int) -> None:
        """Set both seqnums

        Args:
            outgoing_seqnum (int): The outgoing seqnum.
            incoming_seqnum (int): The incoming seqnum.
        """

    @abstractmethod
    async def get_outgoing_seqnum(self) -> int:
        """Get the outgoing seqnum.

        Returns:
            int: The outgoing seqnum.
        """

    @abstractmethod
    async def set_outgoing_seqnum(self, seqnum: int) -> None:
        """Set the outgoing seqnum.

        Args:
            seqnum (int): The outgoing seqnum.
        """

    @abstractmethod
    async def get_incoming_seqnum(self) -> int:
        """Get the incoming seqnum.

        Returns:
            int: The seqnum.
        """

    @abstractmethod
    async def set_incoming_seqnum(self, seqnum: int) -> None:
        """Set the incoming seqnum.

        Args:
            seqnum (int): The seqnum.
        """

    @abstractmethod
    async def save_message(self, buf: bytes) -> None:
        """Save a message

        Args:
            buf (bytes): The message.
        """


class Store(metaclass=ABCMeta):

    @abstractmethod
    def get_session(self, sender_comp_id: str, target_comp_id: str) -> Session:
        """Get a session.

        Args:
            sender_comp_id (str): The sender comp id.
            target_comp_id (str): The target comp id.

        Returns:
            Session: A session for the sender and target.
        """


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class LoginError(Exception):
    """An invalid state transition"""


class FIXEngine(metaclass=ABCMeta):
    """Abstract base class for FIX applications"""

    @property
    @abstractmethod
    def session(self) -> Session:
        """The session

        Returns:
            Session: The session
        """

    @property
    @abstractmethod
    def fix_message_factory(self) -> FixMessageFactory:
        """THe FIX message factory.

        Returns:
            FixMessageFactory: The factory
        """

    @property
    @abstractmethod
    def heartbeat_timeout(self) -> int:
        """The heartbeat timeout"""

    @property
    @abstractmethod
    def heartbeat_threshold(self) -> int:
        """The heartbeat threshold"""

    @abstractmethod
    async def send_message(
            self,
            msg_type: str,
            message: Optional[Mapping[str, Any]] = None
    ) -> None:
        """Send a FIX message

        Args:
            msg_type (str): The message type.
            message (Optional[Mapping[str, Any]], optional): The message.
                Defaults to None.
        """


class FIXApplication:
    """The FIX application"""

    async def on_admin_message(
            self,
            message: Mapping[str, Any],
            fix_engine: FIXEngine
    ) -> None:
        """Called when an admin message is received.

        Args:
            message (Mapping[str, Any]): The admin message that was sent by the
                acceptor.
            fix_engine (FIXEngine): The FIX engine.
        """

    async def on_heartbeat(
            self,
            message: Mapping[str, Any],
            fix_engine: FIXEngine
    ) -> None:
        """Called when a heartbeat is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
            fix_engine (FIXEngine): The FIX engine.
        """

    async def on_application_message(
            self,
            message: Mapping[str, Any],
            fix_engine: FIXEngine
    ) -> None:
        """Called when an application message is received.

        Args:
            message (Mapping[str, Any]): The application message sent by the
                acceptor.
            fix_engine (FIXEngine): The FIX engine.
        """

    async def on_logon(
            self,
            message: Mapping[str, Any],
            fix_engine: FIXEngine
    ) -> None:
        """Called when a logon message is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
            fix_engine (FIXEngine): The FIX engine.
        """

    async def on_logout(
            self,
            message: Mapping[str, Any],
            fix_engine: FIXEngine
    ) -> None:
        """Called when a logout message is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
            fix_engine (FIXEngine): The FIX engine.
        """
