"""Acceptor helpers"""

import asyncio
from asyncio import StreamReader, StreamWriter
from datetime import time, tzinfo
import logging
from typing import Callable, Optional, Tuple, Type
from ssl import SSLContext

from jetblack_fixparser.meta_data import ProtocolMetaData
from jetblack_fixparser.fix_message import SOH

from ..transports import fix_stream_processor, FixReadBuffer, fix_read_async
from ..types import Handler, Store
from ..utils.cancellation import register_cancellation_event

from .acceptor_handler import AcceptorHandler

LOGGER = logging.getLogger(__name__)

ClientFactory = Callable[[], Handler]

AcceptorFactory = Callable[
    [ProtocolMetaData, str, str, Store, int, asyncio.Event],
    Handler
]


def create_acceptor(
        klass: Type[AcceptorHandler],
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: Store,
        heartbeat_timeout: int,
        cancellation_event: asyncio.Event,
        *,
        heartbeat_threshold: int = 1,
        logon_time_range: Optional[Tuple[time, time]] = None,
        tz: Optional[tzinfo] = None
) -> AcceptorHandler:
    handler = klass(
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
    return handler


def start_acceptor(
        klass: Type[AcceptorHandler],
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
    cancellation_event = asyncio.Event()

    async def accept(reader: StreamReader, writer: StreamWriter) -> None:
        read_buffer = FixReadBuffer(
            sep,
            convert_sep_to_soh_for_checksum,
            validate
        )
        buffered_reader = fix_read_async(read_buffer, reader, 1024)
        handler = create_acceptor(
            klass,
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

    loop = asyncio.get_event_loop()
    register_cancellation_event(cancellation_event, loop)
    factory = asyncio.start_server(accept, host, port, ssl=ssl)
    server = loop.run_until_complete(factory)

    try:
        loop.run_forever()
    except asyncio.CancelledError:
        pass
    finally:
        LOGGER.debug('Closing server')
        server.close()
        loop.run_until_complete(server.wait_closed())
        LOGGER.debug('closing event loop')
        loop.close()
