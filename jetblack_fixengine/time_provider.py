"""The Initiator handler class"""

from abc import ABCMeta, abstractmethod
from datetime import datetime, tzinfo


class TimeProvider(metaclass=ABCMeta):

    @abstractmethod
    def now(self, tz: tzinfo) -> datetime:
        ...

    @abstractmethod
    def min(self, tz: tzinfo) -> datetime:
        ...


class UTCTimeProvider(TimeProvider):

    def now(self, tz: tzinfo) -> datetime:
        return datetime.now(tz)

    def min(self, tz: tzinfo) -> datetime:
        return datetime.fromtimestamp(0, tz)
