"""Types"""

from abc import abstractmethod, ABCMeta
from datetime import datetime, time, tzinfo
from typing import Optional, Tuple

from ..types import FIXEngine


class AbstractAcceptorEngine(FIXEngine, metaclass=ABCMeta):
    """The interface for an acceptor"""

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
