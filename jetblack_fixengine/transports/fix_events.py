"""Fix Events"""

from abc import ABCMeta
from enum import IntEnum


class FixReadEventType(IntEnum):
    """The fix read event type"""
    NEEDS_MORE_DATA = 1
    DATA_READY = 2
    EOF = 3


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
        return '<FixReadDataReadEvent: {base}, data={data}>'.format(
            base=super().__str__(),
            data=self.data.decode('ascii')
        )


class FixReadEndOfFile(FixReadEvent):
    """Event indicating the read has reached the end of the input stream"""

    def __init__(self) -> None:
        super().__init__(FixReadEventType.EOF)

    def __str__(self) -> str:
        return f'<FixReadEndOfFile: {super().__str__()}>'


class FixReadError(Exception):
    """A FIX read error"""
