"""Initiator helpers"""

import asyncio
from asyncio import Event
import logging
from ssl import SSLContext
from typing import Optional, Callable, Type

from jetblack_fixparser.meta_data import ProtocolMetaData
from jetblack_fixparser.fix_message import SOH

from ..transports import TransportHandler
from ..types import Store
from ..utils.cancellation import register_cancellation_event

from ..transports import fix_stream_processor,  FixReadBuffer, fix_read_async
from .initiator import Initiator

LOGGER = logging.getLogger(__name__)

InitiatorFactory = Callable[
    [ProtocolMetaData, str, str, Store, int, asyncio.Event],
    TransportHandler
]


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


def create_initiator(
        klass: Type[Initiator],
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: Store,
        logon_timeout: int,
        heartbeat_timeout: int,
        cancellation_event: asyncio.Event,
        *,
        heartbeat_threshold: int = 1
) -> Initiator:
    handler = klass(
        protocol,
        sender_comp_id,
        target_comp_id,
        store,
        logon_timeout,
        heartbeat_timeout,
        cancellation_event,
        heartbeat_threshold=heartbeat_threshold
    )
    return handler


async def start_initiator(
        klass: Type[Initiator],
        host: str,
        port: int,
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: Store,
        logon_timeout: int,
        heartbeat_timeout: int,
        *,
        ssl: Optional[SSLContext] = None,
        shutdown_timeout: float = 10.0,
        heartbeat_threshold: int = 1
) -> None:
    cancellation_event = Event()
    loop = asyncio.get_event_loop()
    register_cancellation_event(cancellation_event, loop)

    handler = create_initiator(
        klass,
        protocol,
        sender_comp_id,
        target_comp_id,
        store,
        logon_timeout,
        heartbeat_timeout,
        cancellation_event,
        heartbeat_threshold=heartbeat_threshold
    )

    await initiate(
        host,
        port,
        handler,
        cancellation_event,
        ssl=ssl,
        shutdown_timeout=shutdown_timeout
    )
