"""FIX Transport"""

import asyncio
from asyncio import Queue, Task, StreamWriter, Future
from enum import IntEnum
import logging
from typing import AsyncIterator, Set, cast

from jetblack_fixparser.fix_message import SOH

from ..types import Handler, Message
from ..utils.cancellation import cancel_await

LOGGER = logging.getLogger(__name__)


class FixState(IntEnum):
    """The FIX state"""
    OK = 0
    EOF = 1
    HANDLER_COMPLETED = 3
    CANCELLED = 4
    HANDLER_CLOSED = 5


async def fix_stream_processor(
        handler: Handler,
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

    read_queue: "Queue[Message]" = Queue()
    write_queue: "Queue[Message]" = Queue()

    async def receive() -> Message:
        return await read_queue.get()

    async def send(evt: Message) -> None:
        await write_queue.put(evt)

    await read_queue.put({
        'type': 'connected'
    })

    state = FixState.OK
    reader_iter = reader.__aiter__()

    # Create initial tasks.
    handler_task: Task = asyncio.create_task(
        handler(send, receive)  # type: ignore
    )
    read_task: Task[bytes] = asyncio.create_task(
        reader_iter.__anext__()  # type: ignore
    )
    write_task: Task[Message] = asyncio.create_task(write_queue.get())
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

                # Fetch the event sent by the handler.
                event = write_task.result()

                if event['type'] == 'fix':
                    # Send data to the handler and renew the write task.
                    message: bytes = event['message']
                    LOGGER.debug(
                        'Sending "%s"',
                        message.replace(SOH, b'|').decode()
                    )
                    writer.write(message)
                    await writer.drain()
                    write_task = asyncio.create_task(write_queue.get())
                    pending.add(write_task)
                elif event['type'] == 'close':
                    # Close the connection and exit the task service loop.
                    writer.close()
                    state = FixState.HANDLER_CLOSED
                    continue
                else:
                    LOGGER.debug('Invalid event "%s"', event["type"])
                    raise RuntimeError(f'Invalid event "{event["type"]}"')

            elif task == read_task:

                try:
                    message = cast(bytes, task.result())
                    LOGGER.debug(
                        'Received "%s"',
                        message.replace(SOH, b'|').decode()
                    )
                    # Notify the client and reset the state.
                    await read_queue.put({
                        'type': 'fix',
                        'message': message
                    })
                    # Create the new read task.
                    message = b''
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
        await read_queue.put({
            'type': 'disconnect'
        })

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
