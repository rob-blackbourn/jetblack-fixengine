"""Types"""

from abc import abstractmethod, ABCMeta
from datetime import datetime, time, tzinfo
from typing import Any, Mapping, Optional, Tuple

from jetblack_fixparser.fix_message import FixMessageFactory

from ..types import Session


class AbstractAcceptor(metaclass=ABCMeta):
    """The interface for an acceptor"""

    @property
    @abstractmethod
    def session(self) -> Session:
        """The session"""

    @property
    @abstractmethod
    def fix_message_factory(self) -> FixMessageFactory:
        """The FIX message factory"""

    @property
    @abstractmethod
    def heartbeat_timeout(self) -> int:
        """The heartbeat timeout"""

    @property
    @abstractmethod
    def heartbeat_threshold(self) -> int:
        """The heartbeat threshold"""

    @property
    @abstractmethod
    def logon_time_range(self) -> Optional[Tuple[time, time]]:
        """The logon time range"""

    @property
    @abstractmethod
    def logout_time(self) -> Optional[datetime]:
        """The logout time"""

    @logout_time.setter
    @abstractmethod
    def logout_time(self, value: datetime) -> None:
        """The logout time setter"""

    @property
    def tz(self) -> Optional[tzinfo]:
        """The time zone"""

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
