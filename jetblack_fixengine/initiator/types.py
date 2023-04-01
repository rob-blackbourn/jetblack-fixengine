"""Types"""

from abc import abstractmethod, ABCMeta
from typing import Any, Mapping, Optional

from jetblack_fixparser.fix_message import FixMessageFactory

from ..types import Session


class AbstractInitiator(metaclass=ABCMeta):
    """The interface for an initiator"""

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
