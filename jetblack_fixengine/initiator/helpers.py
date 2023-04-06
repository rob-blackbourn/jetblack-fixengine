"""Helper functions"""

import asyncio
from asyncio import Event
import logging
from ssl import SSLContext
from typing import Optional

from jetblack_fixparser.fix_message import SOH

from ..transports import TransportHandler
from ..types import FIXApplication
from ..utils.cancellation import register_cancellation_event

from ..transports import FixReadBuffer, fix_read_async, fix_stream_processor

from .initiator import InitiatorEngine
from .types import InitiatorConfig

LOGGER = logging.getLogger(__name__)


async def initiate(
        host: str,
        port: int,
        handler: TransportHandler,
        cancellation_event: asyncio.Event,
        *,
        ssl: Optional[SSLContext] = None,
        shutdown_timeout: float = 10.0,
        sep: bytes = SOH,
        convert_sep_to_soh_for_checksum: bool = False,
        validate: bool = True
) -> None:
    LOGGER.info(
        'connecting to %s:%s%s',
        host,
        port,
        " over ssl" if ssl else ""
    )

    reader, writer = await asyncio.open_connection(host, port, ssl=ssl)
    read_buffer = FixReadBuffer(sep, convert_sep_to_soh_for_checksum, validate)
    buffered_reader = fix_read_async(read_buffer, reader, 1024)
    await fix_stream_processor(
        handler,
        shutdown_timeout,
        buffered_reader,
        writer,
        cancellation_event
    )

    LOGGER.info(
        'disconnected from %s:%s%s',
        host,
        port,
        " over ssl" if ssl else ""
    )


async def start_initiator(
        app: FIXApplication,
        config: InitiatorConfig,
) -> None:
    """Start the initiator.

    Args:
        app (FIXApplication): The FIX application.
        config (InitiatorConfig): The initiator configuration.
    """
    cancellation_event = Event()
    loop = asyncio.get_event_loop()
    register_cancellation_event(cancellation_event, loop)

    engine = InitiatorEngine(
        app,
        config.protocol,
        config.sender_comp_id,
        config.target_comp_id,
        config.store,
        config.logon_timeout,
        config.heartbeat_timeout,
        cancellation_event,
        heartbeat_threshold=config.heartbeat_threshold
    )

    await initiate(
        config.host,
        config.port,
        engine,
        cancellation_event,
        ssl=config.ssl,
        shutdown_timeout=config.shutdown_timeout
    )
