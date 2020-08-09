"""Fix Events"""

from abc import ABCMeta
from enum import IntEnum


class FixReadEventType(IntEnum):
    """The fix read event type"""
    ERROR = 1
    NEEDS_MORE_DATA = 2
    DATA_READY = 3
    EOF = 4


class FixReadEvent(metaclass=ABCMeta):
    """The base class for fix events"""

    def __init__(self, event_type: FixReadEventType) -> None:
        self.event_type = event_type

    def __str__(self) -> str:
        return f'event_type={self.event_type}'


class FixReadNeedsMoreData(FixReadEvent):
    """An event indicating more data is required for reading"""

    def __init__(self, length: int = -1) -> None:
        super().__init__(FixReadEventType.NEEDS_MORE_DATA)
        self.length = length

    def __str__(self) -> str:
        return f'<FixReadNeedsMoreData: {super().__str__()}, length={self.length}>'


class FixReadDataReady(FixReadEvent):
    """Indicates a fix message has been read"""

    def __init__(self, data: bytes) -> None:
        super().__init__(FixReadEventType.DATA_READY)
        self.data = data

    def __str__(self) -> str:
        return f'<FixReadDataReadEvent: {super().__str__()}, data={self.data}>'


class FixReadError(FixReadEvent):
    """An event indicating an error has occurred"""

    def __init__(self, reason: str) -> None:
        super().__init__(FixReadEventType.ERROR)
        self.reason = reason

    def __str__(self) -> str:
        return f'<FixErrorEvent: {super().__str__()}, reason={self.reason}>'


class FixReadEndOfFile(FixReadEvent):
    """Event indicating the read has reaced the end of the input stream"""

    def __init__(self) -> None:
        super().__init__(FixReadEventType.EOF)

    def __str__(self) -> str:
        return f'<FixReadEndOfFile: {super().__str__()}>'
