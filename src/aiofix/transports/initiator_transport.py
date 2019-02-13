import asyncio
import logging
from ssl import SSLContext
from typing import Optional
from ..types import Handler
from .fix_transport import fix_stream_processor

logger = logging.getLogger(__name__)


async def initiate(
        host: str,
        port: int,
        handler: Handler,
        *,
        ssl: Optional[SSLContext] = None,
        shutdown_timeout: float = 10.0
) -> None:
    logger.info(f'connecting to {host}:{port}{" over ssl" if ssl else ""}')

    reader, writer = await asyncio.open_connection(host, port, ssl=ssl)
    await fix_stream_processor(handler, shutdown_timeout, reader, writer)

    logger.info(f'disconnected from {host}:{port}{" over ssl" if ssl else ""}')


def start_initiator(
        host: str,
        port: int,
        handler: Handler,
        ssl: Optional[SSLContext] = None,
        shutdown_timeout: float = 10.0
) -> None:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(initiate(host, port, handler, ssl=ssl, shutdown_timeout=shutdown_timeout))
