"""The acceptor transport"""

import asyncio
import logging
from typing import Callable, Optional
from ssl import SSLContext
from .fix_transport import fix_stream_processor
from ..types import Handler
from ..utils.cancellation import register_cancellation_event

logger = logging.getLogger(__name__)

ClientFactory = Callable[[], Handler]


def start_acceptor(
        host: str,
        port: int,
        client_factory: ClientFactory,
        *,
        ssl: Optional[SSLContext],
        client_shutdown_timeout: float = 10.0

) -> None:
    cancellation_event = asyncio.Event()

    async def accept(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        handler = client_factory()
        await fix_stream_processor(
            handler,
            client_shutdown_timeout,
            reader,
            writer,
            cancellation_event
        )

    loop = asyncio.get_event_loop()
    register_cancellation_event(cancellation_event, loop)
    factory = asyncio.start_server(accept, host, port, ssl=ssl)
    server = loop.run_until_complete(factory)

    try:
        loop.run_forever()
    except asyncio.CancelledError:
        pass
    finally:
        logger.debug('Closing server')
        server.close()
        loop.run_until_complete(server.wait_closed())
        logger.debug('closing event loop')
        loop.close()
