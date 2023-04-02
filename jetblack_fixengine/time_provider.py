"""The Initiator handler class"""

from abc import ABCMeta, abstractmethod
from datetime import datetime, tzinfo


class TimeProvider(metaclass=ABCMeta):
    """A bas class for time providers"""

    @abstractmethod
    def now(self, tz: tzinfo) -> datetime:
        """The current time"""

    @abstractmethod
    def min(self, tz: tzinfo) -> datetime:
        """The minimum time"""


class DefaultTimeProvider(TimeProvider):
    """The default time provider"""

    def now(self, tz: tzinfo) -> datetime:
        return datetime.now(tz)

    def min(self, tz: tzinfo) -> datetime:
        return datetime.fromtimestamp(0, tz)
