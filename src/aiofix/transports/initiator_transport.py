import asyncio
import logging
from ssl import SSLContext
from typing import Optional
from ..types import Handler
from ..utils.cancellation import register_cancellation_token
from .fix_transport import fix_stream_processor

logger = logging.getLogger(__name__)


async def initiate(
        host: str,
        port: int,
        handler: Handler,
        cancellation_token: asyncio.Event,
        *,
        ssl: Optional[SSLContext] = None,
        shutdown_timeout: float = 10.0
) -> None:
    logger.info(f'connecting to {host}:{port}{" over ssl" if ssl else ""}')

    reader, writer = await asyncio.open_connection(host, port, ssl=ssl)
    await fix_stream_processor(handler, shutdown_timeout, reader, writer, cancellation_token)

    logger.info(f'disconnected from {host}:{port}{" over ssl" if ssl else ""}')


def start_initiator(
        host: str,
        port: int,
        handler: Handler,
        ssl: Optional[SSLContext] = None,
        shutdown_timeout: float = 10.0
) -> None:
    cancellation_token = asyncio.Event()
    loop = asyncio.get_event_loop()
    register_cancellation_token(cancellation_token, loop)
    loop.run_until_complete(
        initiate(
            host,
            port,
            handler,
            cancellation_token,
            ssl=ssl,
            shutdown_timeout=shutdown_timeout
        )
    )
