"""FIX Transport"""

import asyncio
from asyncio import Queue, Task, StreamWriter, Future
from enum import IntEnum
import logging
from typing import AsyncIterator, Set, cast

from jetblack_fixparser.fix_message import SOH

from ..utils.cancellation import cancel_await
from .types import TransportMessage, TransportEvent
from .state_processor import TransportHandler

LOGGER = logging.getLogger(__name__)


class FixState(IntEnum):
    """The FIX state"""
    OK = 0
    EOF = 1
    HANDLER_COMPLETED = 3
    CANCELLED = 4
    HANDLER_CLOSED = 5


async def fix_stream_processor(
        handler: TransportHandler,
        shutdown_timeout: float,
        reader: AsyncIterator[bytes],
        writer: StreamWriter,
        cancellation_event: asyncio.Event
) -> None:
    """Create a processor for a stream of FIX data.

    Args:
        handler (Handler): The handler.
        shutdown_timeout (float): The time to wait before shutting down.
        reader (AsyncIterator[bytes]): The stream reader.
        writer (StreamWriter): The stream writer.
        cancellation_event (asyncio.Event): An event with which to cancel the processing.

    Raises:
        RuntimeError: If an invalid event was received.
    """
    if cancellation_event.is_set():
        return

    read_queue: "Queue[TransportMessage]" = Queue()
    write_queue: "Queue[TransportMessage]" = Queue()

    async def receive() -> TransportMessage:
        return await read_queue.get()

    async def send(evt: TransportMessage) -> None:
        await write_queue.put(evt)

    await read_queue.put(TransportMessage(TransportEvent.CONNECTION_RECEIVED))

    state = FixState.OK
    reader_iter = reader.__aiter__()

    # Create initial tasks.
    handler_task: Task = asyncio.create_task(
        handler(send, receive)  # type: ignore
    )
    read_task: Task[bytes] = asyncio.create_task(
        reader_iter.__anext__()  # type: ignore
    )
    write_task: Task[TransportMessage] = asyncio.create_task(write_queue.get())
    cancellation_task = asyncio.create_task(cancellation_event.wait())
    pending: Set[Future] = {
        read_task,
        write_task,
        handler_task,
        cancellation_task
    }
    # Start the task service loop.
    while state == FixState.OK and not cancellation_event.is_set():

        # Wait for a task to be completed.
        completed, pending = await asyncio.wait(
            pending,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Handle the completed tasks. The pending tasks are left to become completed.
        for task in completed:

            if task == handler_task:

                state = FixState.HANDLER_COMPLETED
                continue

            elif task == cancellation_task:

                state = FixState.CANCELLED
                continue

            elif task == write_task:

                # Fetch the message sent by the handler.
                message = write_task.result()

                if message.event == TransportEvent.FIX_RECEIVED:
                    # Send data to the handler and renew the write task.
                    assert message.buffer is not None
                    data = message.buffer
                    LOGGER.debug(
                        'Sending "%s"',
                        message.buffer.replace(SOH, b'|').decode()
                    )
                    writer.write(message.buffer)
                    await writer.drain()
                    write_task = asyncio.create_task(write_queue.get())
                    pending.add(write_task)
                elif message.event == TransportEvent.DISCONNECT_RECEIVED:
                    # Close the connection and exit the task service loop.
                    writer.close()
                    state = FixState.HANDLER_CLOSED
                    continue
                else:
                    LOGGER.debug('Invalid event "%s"', message.event.name)
                    raise RuntimeError(f'Invalid event "{message.event.name}"')

            elif task == read_task:

                try:
                    data = cast(bytes, task.result())
                    LOGGER.debug(
                        'Received "%s"',
                        data.replace(SOH, b'|').decode()
                    )
                    # Notify the client and reset the state.
                    await read_queue.put(
                        TransportMessage(
                            TransportEvent.FIX_RECEIVED,
                            data
                        )
                    )
                    # Create the new read task.
                    data = b''
                    # Read the field.
                    read_task = asyncio.create_task(
                        reader_iter.__anext__()  # type: ignore
                    )
                    pending.add(read_task)
                except StopAsyncIteration:
                    state = FixState.EOF
                    continue
            else:
                raise AssertionError('Invalid task')

    # Attempt to shutdown gracefully.

    if state == FixState.HANDLER_COMPLETED:
        # When the handler task has finished the session if over.
        # Calling done will re-raise an exception.
        handler_task.done()
        await cancel_await(read_task)
        await cancel_await(write_task)
        writer.close()
    else:
        # Notify the client of the disconnection.
        await read_queue.put(
            TransportMessage(TransportEvent.DISCONNECT_RECEIVED)
        )

        await cancel_await(write_task)

        if state != FixState.EOF:
            writer.close()
            await cancel_await(read_task)

        if not handler_task.cancelled():
            LOGGER.info(
                'Waiting %s seconds for the handler to complete.',
                shutdown_timeout
            )
            try:
                await asyncio.wait_for(handler_task, timeout=shutdown_timeout)
            except asyncio.TimeoutError:
                LOGGER.error('Cancelling the handler')
                await cancel_await(
                    handler_task,
                    lambda: LOGGER.warning(
                        'The handler task did not complete and has been cancelled'
                    )
                )

    LOGGER.debug('Shutdown complete.')
