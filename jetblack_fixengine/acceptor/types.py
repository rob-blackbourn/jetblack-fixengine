"""Types"""

from abc import abstractmethod, ABCMeta
from typing import Any, Mapping


class AbstractAcceptor(metaclass=ABCMeta):
    """The interface for an acceptor"""

    async def on_admin_message(self, message: Mapping[str, Any]) -> None:
        """Handle an admin message.

        Args:
            message (Mapping[str, Any]): The message to handle.
        """

    async def on_heartbeat(self, message: Mapping[str, Any]) -> None:
        """Handle a heartbeat.

        Args:
            message (Mapping[str, Any]): The heartbeat message
        """

    @abstractmethod
    async def on_logon(self, message: Mapping[str, Any]) -> bool:
        """Return True if the login is valid

        Args:
            message (Mapping[str, Any]): The message to handle.
        """

    @abstractmethod
    async def on_logout(self, message: Mapping[str, Any]) -> None:
        """Perform any logout tasks

        Args:
            message (Mapping[str, Any]): The message to handle.
        """

    @abstractmethod
    async def on_application_message(self, message: Mapping[str, Any]) -> None:
        """Handle an application message.

        Args:
            message (Mapping[str, Any]): The message to handle.
        """
