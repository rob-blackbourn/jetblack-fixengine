"""FIX Transport"""

import asyncio
from asyncio import Queue, Task, StreamWriter
from enum import IntEnum
import logging
from typing import Any, AsyncIterator, Callable, Optional, cast

from ..types import Handler, Event

logger = logging.getLogger(__name__)


class FixState(IntEnum):
    OK = 0
    EOF = 1
    HANDLER_COMPLETED = 3
    CANCELLED = 4
    HANDLER_CLOSED = 5


async def _cancel_await(
        task: "Task[Any]",
        callback: Optional[Callable[[], None]] = None
) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        if callback is not None:
            callback()


async def fix_stream_processor(
        handler: Handler,
        shutdown_timeout: float,
        reader: AsyncIterator[bytes],
        writer: StreamWriter,
        cancellation_token: asyncio.Event
) -> None:
    if cancellation_token.is_set():
        return

    read_queue: "Queue[Event]" = Queue()
    write_queue: "Queue[Event]" = Queue()

    async def receive() -> Event:
        return await read_queue.get()

    async def send(evt: Event) -> None:
        await write_queue.put(evt)

    await read_queue.put({
        'type': 'connected'
    })

    state = FixState.OK
    message: bytes = b''

    reader_iter = reader.__aiter__()

    # Create initial tasks.
    handler_task = asyncio.create_task(handler(send, receive))
    read_task: Task[bytes] = asyncio.create_task(reader_iter.__anext__())
    write_task = asyncio.create_task(write_queue.get())
    cancellation_task = asyncio.create_task(cancellation_token.wait())

    # Start the task service loop.
    while state == FixState.OK and not cancellation_token.is_set():

        # Wait for a task to be completed.
        completed, _ = await asyncio.wait([
            read_task,
            write_task,
            handler_task,
            cancellation_task
        ], return_when=asyncio.FIRST_COMPLETED)

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
                event = cast(Event, task.result())

                if event['type'] == 'fix':
                    # Send data to the handler and renew the write task.
                    logger.debug('Sending "%s"', event["message"])
                    writer.write(event['message'])
                    await writer.drain()
                    write_task = asyncio.create_task(write_queue.get())
                elif event['type'] == 'close':
                    # Close the connection and exit the task service loop.
                    writer.close()
                    state = FixState.HANDLER_CLOSED
                    continue
                else:
                    logger.debug('Invalid event "%s"', event["type"])
                    raise RuntimeError(f'Invalid event "{event["type"]}"')

            elif task == read_task:

                try:
                    message = cast(bytes, task.result())
                    logger.debug('Received "%s"', message)
                    # Notify the client and reset the state.
                    await read_queue.put({
                        'type': 'fix',
                        'message': message
                    })
                    message = b''
                    # Read the field.
                    read_task = asyncio.create_task(reader_iter.__anext__())
                except StopAsyncIteration:
                    state = FixState.EOF
                    continue
            else:
                raise AssertionError('Invalid task')

    if state == FixState.HANDLER_COMPLETED:
        # When the handler task has finished the session if over.
        # Calling done will re-raise an exception.
        handler_task.done()
        await _cancel_await(read_task)
        await _cancel_await(write_task)
        writer.close()
    else:
        # Notify the client of the disconnection.
        await read_queue.put({
            'type': 'disconnect'
        })

        write_task.cancel()
        try:
            await write_task
        except asyncio.CancelledError:
            pass

        if state != FixState.EOF:
            writer.close()
            await _cancel_await(read_task)

        if not handler_task.cancelled():
            logger.info(
                'Waiting %s seconds for the handler to complete.',
                shutdown_timeout
            )
            try:
                await asyncio.wait_for(handler_task, timeout=shutdown_timeout)
            except asyncio.TimeoutError:
                logger.error('Cancelling the handler')
                handler_task.cancel()
                try:
                    await handler_task
                except asyncio.CancelledError:
                    logger.warning(
                        'The handler task did not complete and has been cancelled')

    logger.debug('Shutdown complete.')
