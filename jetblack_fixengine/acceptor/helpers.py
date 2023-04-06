"""Helper functions"""

import asyncio
from asyncio import StreamReader, StreamWriter, Event
import logging
from typing import Callable

from jetblack_fixparser.meta_data import ProtocolMetaData

from ..transports import (
    fix_stream_processor,
    FixReadBuffer,
    fix_read_async,
    TransportHandler,
)
from ..types import Store, FIXApplication
from ..utils.cancellation import register_cancellation_event

from .acceptor import AcceptorEngine
from .types import AcceptorConfig

LOGGER = logging.getLogger(__name__)

ClientFactory = Callable[[], TransportHandler]

AcceptorFactory = Callable[
    [ProtocolMetaData, str, str, Store, int, asyncio.Event],
    TransportHandler
]


async def start_acceptor(
        app: FIXApplication,
        config: AcceptorConfig
) -> None:
    cancellation_event = Event()

    async def accept(reader: StreamReader, writer: StreamWriter) -> None:
        LOGGER.info("Accepting initiator")

        read_buffer = FixReadBuffer(
            config.sep,
            config.convert_sep_to_soh_for_checksum,
            config.validate
        )
        buffered_reader = fix_read_async(read_buffer, reader, 1024)
        handler = AcceptorEngine(
            app,
            config.protocol,
            config.sender_comp_id,
            config.target_comp_id,
            config.store,
            config.heartbeat_timeout,
            cancellation_event,
            heartbeat_threshold=config.heartbeat_threshold,
            logon_time_range=config.logon_time_range,
            tz=config.tz
        )
        await fix_stream_processor(
            handler,
            config.client_shutdown_timeout,
            buffered_reader,
            writer,
            cancellation_event
        )

    LOGGER.info(
        "Starting acceptor on %s:%s%s",
        config.host,
        config.port,
        " using SSL" if config.ssl is not None else ""
    )

    loop = asyncio.get_event_loop()
    register_cancellation_event(cancellation_event, loop)

    server = await asyncio.start_server(
        accept,
        config.host,
        config.port,
        ssl=config.ssl
    )

    async with server:
        await server.serve_forever()
