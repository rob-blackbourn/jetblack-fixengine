"""Helper functions"""

import asyncio
from asyncio import StreamReader, StreamWriter, Event
from datetime import time, tzinfo
import logging
from typing import Callable, Optional, Tuple
from ssl import SSLContext

from jetblack_fixparser.meta_data import ProtocolMetaData
from jetblack_fixparser.fix_message import SOH

from ..transports import (
    fix_stream_processor,
    FixReadBuffer,
    fix_read_async,
    TransportHandler,
)
from ..types import Store, FIXApplication
from ..utils.cancellation import register_cancellation_event

from .acceptor import AcceptorEngine

LOGGER = logging.getLogger(__name__)

ClientFactory = Callable[[], TransportHandler]

AcceptorFactory = Callable[
    [ProtocolMetaData, str, str, Store, int, asyncio.Event],
    TransportHandler
]


async def start_acceptor(
        app: FIXApplication,
        host: str,
        port: int,
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: Store,
        heartbeat_timeout: int,
        *,
        ssl: Optional[SSLContext] = None,
        client_shutdown_timeout: float = 10.0,
        sep: bytes = SOH,
        convert_sep_to_soh_for_checksum: bool = False,
        validate: bool = True,
        heartbeat_threshold: int = 1,
        logon_time_range: Optional[Tuple[time, time]] = None,
        tz: Optional[tzinfo] = None
) -> None:
    cancellation_event = Event()

    async def accept(reader: StreamReader, writer: StreamWriter) -> None:
        LOGGER.info("Accepting initiator")

        read_buffer = FixReadBuffer(
            sep,
            convert_sep_to_soh_for_checksum,
            validate
        )
        buffered_reader = fix_read_async(read_buffer, reader, 1024)
        handler = AcceptorEngine(
            app,
            protocol,
            sender_comp_id,
            target_comp_id,
            store,
            heartbeat_timeout,
            cancellation_event,
            heartbeat_threshold=heartbeat_threshold,
            logon_time_range=logon_time_range,
            tz=tz
        )
        await fix_stream_processor(
            handler,
            client_shutdown_timeout,
            buffered_reader,
            writer,
            cancellation_event
        )

    LOGGER.info(
        "Starting acceptor on %s:%s%s",
        host,
        port,
        " using SSL" if ssl is not None else ""
    )

    loop = asyncio.get_event_loop()
    register_cancellation_event(cancellation_event, loop)

    server = await asyncio.start_server(accept, host, port, ssl=ssl)

    async with server:
        await server.serve_forever()
