import asyncio
from asyncio import Queue, StreamReader, StreamWriter
import logging
from ..types import Handler, Event

logger = logging.getLogger(__name__)

SOH = b'\x01'

CHECKSUM_LENGTH = len(b'10=000\x01')

STATE_READ_BEGIN_STRING = 'BeginString'
STATE_READ_BODY_LENGTH = 'BodyLength'
STATE_READ_BODY = 'Body'
STATE_READ_EOF = 'EOF'
STATE_HANDLER_COMPLETED = 'handler.completed'
STATE_HANDLER_CLOSED = 'handler.closed'
STATE_CANCELLED = 'cancelled'

STATE_READ = (STATE_READ_BEGIN_STRING, STATE_READ_BODY_LENGTH, STATE_READ_BODY)


async def _send_event(queue: Queue, event: Event) -> None:
    await queue.put(event)


async def _send_event_connected(queue: Queue) -> None:
    event = {
        'type': 'connected'
    }
    await _send_event(queue, event)


async def _send_event_disconnect(queue: Queue) -> None:
    event = {
        'type': 'disconnect'
    }
    await _send_event(queue, event)


async def _send_event_error(queue: Queue, reason: str, message: bytes) -> None:
    event = {
        'type': 'error',
        'reason': reason,
        'message': message
    }
    await _send_event(queue, event)


async def _send_event_fix(queue: Queue, message: bytes) -> None:
    event = {
        'type': 'fix',
        'message': message
    }
    await _send_event(queue, event)


async def fix_stream_processor(
        handler: Handler,
        shutdown_timeout: float,
        reader: StreamReader,
        writer: StreamWriter,
        cancellation_token: asyncio.Event
) -> None:
    if cancellation_token.is_set():
        return

    read_queue = Queue()
    write_queue = Queue()

    async def receive() -> Event:
        return await read_queue.get()

    async def send(evt: Event) -> None:
        await write_queue.put(evt)

    await _send_event_connected(read_queue)

    state = STATE_READ_BEGIN_STRING
    message: bytes = b''

    # Create initial tasks.
    handler_task = asyncio.create_task(handler(send, receive))
    read_task = asyncio.create_task(reader.readuntil(SOH))
    write_task = asyncio.create_task(write_queue.get())
    cancellation_task = asyncio.create_task(cancellation_token.wait())

    # Start the task service loop.
    while state in STATE_READ and not cancellation_token.is_set():

        # Wait for a task to be completed.
        completed, pending = await asyncio.wait([
            read_task,
            write_task,
            handler_task,
            cancellation_task
        ], return_when=asyncio.FIRST_COMPLETED)

        # Handle the completed tasks. The pending tasks are left to become completed.
        for task in completed:

            if task == handler_task:

                state = STATE_HANDLER_COMPLETED
                continue

            elif task == cancellation_task:

                state = STATE_CANCELLED
                continue

            elif task == write_task:

                # Fetch the event sent by the handler.
                event: Event = task.result()

                if event['type'] == 'fix':
                    # Send data to the handler and renew the write task.
                    logger.debug(f'Sending "{event["message"]}"')
                    writer.write(event['message'])
                    await writer.drain()
                    write_task = asyncio.create_task(write_queue.get())
                elif event['type'] == 'close':
                    # Close the connection and exit the task service loop.
                    await writer.close()
                    state = STATE_HANDLER_CLOSED
                    continue
                else:
                    logger.debug(f'Invalid event "{event["type"]}"')
                    raise RuntimeError(f'Invalid event "{event["type"]}"')

            elif task == read_task:

                try:
                    result: bytes = task.result()
                except asyncio.IncompleteReadError:
                    result = None

                if not result:
                    # An empty read indicates the connection has closed.
                    state = STATE_READ_EOF
                    continue

                # Accumulate the result.
                message += result

                if state == STATE_READ_BEGIN_STRING:
                    # Should have read the BeginString tag: e.g. b'8=FIX.4.2\x01'.
                    if not result.startswith(b'8='):
                        await _send_event_error(read_queue, 'Expected BeginString', message)
                        state = STATE_READ_EOF
                        continue
                    read_task = asyncio.create_task(reader.readuntil(SOH))
                    state = STATE_READ_BODY_LENGTH
                elif state == STATE_READ_BODY_LENGTH:
                    # Should have read the BodyLength: e.g. b'9=129\x01'.
                    if not result.startswith(b'9='):
                        await _send_event_error(read_queue, 'Expected BodyLength', message)
                        state = STATE_READ_EOF
                        continue
                    value = result[2:-1]
                    # It is within the specification for the length to be zero padded.
                    if len(value) > 1 and value.startswith(b'0'):
                        value = value.lstrip(b'0')
                    body_length = int(value)
                    # The total length includes the checksum.
                    total_length = body_length + CHECKSUM_LENGTH
                    # Read the rest of the message.
                    read_task = asyncio.create_task(reader.readexactly(total_length))
                    state = STATE_READ_BODY
                elif state == STATE_READ_BODY:
                    logger.debug(f'Received "{message}"')
                    # Notify the client and reset the state.
                    await _send_event_fix(read_queue, message)
                    message = b''
                    # Read the field.
                    read_task = asyncio.create_task(reader.readuntil(SOH))
                    state = STATE_READ_BEGIN_STRING
                else:
                    raise AssertionError('Invalid read state')
            else:
                raise AssertionError('Invalid task')

    if state == STATE_HANDLER_COMPLETED:
        # When the handler task has finished the session if over.
        # Calling done will re-raise an exception.
        handler_task.done()
        read_task.cancel()
        write_task.cancel()
        try:
            await read_task
            await write_task
        except asyncio.CancelledError:
            pass
        writer.close()
    else:
        # Notify the client of the disconnection.
        await _send_event_disconnect(read_queue)

        write_task.cancel()
        try:
            await write_task
        except asyncio.CancelledError:
            pass

        if state != STATE_READ_EOF:
            writer.close()
            read_task.cancel()
            try:
                await read_task
            except asyncio.CancelledError:
                pass

        logger.info(f'Waiting {shutdown_timeout} seconds for the handler to complete.')
        try:
            await asyncio.wait_for(handler_task, timeout=shutdown_timeout)
        except asyncio.TimeoutError:
            logger.error('Cancelling the handler')
            handler_task.cancel()
            try:
                await handler_task
            except asyncio.CancelledError:
                logger.warning('The handler task did not complete and has been cancelled')

        logger.debug('Shutdown complete.')
