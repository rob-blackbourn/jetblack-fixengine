"""An async fix reader"""

from asyncio import StreamReader
from typing import AsyncIterator, cast

from .fix_events import (
    FixReadEventType,
    FixReadDataReady
)
from .fix_read_buffer import FixReadBuffer


async def fix_read_async(
        read_buffer: FixReadBuffer,
        stream_reader: StreamReader,
        blksiz: int
) -> AsyncIterator[bytes]:
    done = False
    while not done:
        fix_event = read_buffer.next_event()
        if fix_event.event_type == FixReadEventType.EOF:
            done = True
        elif fix_event.event_type == FixReadEventType.NEEDS_MORE_DATA:
            buf = await stream_reader.read(blksiz)
            read_buffer.receive(buf)
        elif fix_event.event_type == FixReadEventType.DATA_READY:
            data_ready = cast(FixReadDataReady, fix_event)
            yield data_ready.data
        else:
            raise Exception('Invalid state')
    print('done')
