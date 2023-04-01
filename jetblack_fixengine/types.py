"""Types"""

from abc import ABCMeta, abstractmethod
from typing import Any, Mapping, Optional, Tuple

from jetblack_fixparser.fix_message import FixMessageFactory


class Session(metaclass=ABCMeta):

    @property
    @abstractmethod
    def sender_comp_id(self) -> str:
        raise NotImplementedError

    @property
    def target_comp_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_seqnums(self) -> Tuple[int, int]:
        raise NotImplementedError

    @abstractmethod
    async def set_seqnums(self, outgoing_seqnum: int, incoming_seqnum: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_outgoing_seqnum(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def set_outgoing_seqnum(self, seqnum: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_incoming_seqnum(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def set_incoming_seqnum(self, seqnum: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save_message(self, buf: bytes) -> None:
        raise NotImplementedError


class Store(metaclass=ABCMeta):

    def get_session(self, sender_comp_id: str, target_comp_id: str) -> Session:
        raise NotImplementedError


class InvalidStateTransitionError(Exception):
    """An invalid state transition"""


class LoginError(Exception):
    """An invalid state transition"""


class AbstractHandler(metaclass=ABCMeta):

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

    async def on_admin_message(self, message: Mapping[str, Any]) -> None:
        """Called when an admin message is received.

        Args:
            message (Mapping[str, Any]): The admin message that was sent by the
                acceptor.
        """

    async def on_heartbeat(self, message: Mapping[str, Any]) -> None:
        """Called when a heartbeat is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
        """

    @abstractmethod
    async def on_application_message(self, message: Mapping[str, Any]) -> None:
        """Called when an application message is received.

        Args:
            message (Mapping[str, Any]): The application message sent by the
                acceptor.
        """

    @abstractmethod
    async def on_logon(self, message: Mapping[str, Any]) -> None:
        """Called when a logon message is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
        """

    @abstractmethod
    async def on_logout(self, message: Mapping[str, Any]) -> None:
        """Called when a logout message is received.

        Args:
            message (Mapping[str, Any]): The message sent by the acceptor.
        """

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
