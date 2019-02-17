import asyncio
from datetime import tzinfo, time
import logging
from ssl import SSLContext
from typing import Optional, Callable, Type, Tuple
from ..types import Handler, InitiatorStore
from ..meta_data import ProtocolMetaData
from ..utils.cancellation import register_cancellation_token
from ..middlewares import mw, FixMessageMiddleware
from .fix_transport import fix_stream_processor
from .initiator_handler import InitiatorHandler

logger = logging.getLogger(__name__)

InitiatorFactory = Callable[[ProtocolMetaData, str, str, InitiatorStore, int, asyncio.Event], Handler]


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


def create_initiator(
        klass: Type[InitiatorHandler],
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: InitiatorStore,
        heartbeat_timeout: int,
        cancellation_token: asyncio.Event,
        *,
        heartbeat_threshold: int = 1,
        logon_time_range: Optional[Tuple[time, time]] = None,
        tz: tzinfo = None
) -> InitiatorHandler:
    handler: Handler = klass(
        protocol,
        sender_comp_id,
        target_comp_id,
        store,
        heartbeat_timeout,
        cancellation_token,
        heartbeat_threshold=heartbeat_threshold,
        logon_time_range=logon_time_range,
        tz=tz
    )
    middleware = FixMessageMiddleware(protocol)
    handler: InitiatorHandler = mw([middleware], handler=handler)
    return handler


def start_initiator(
        klass: Type[InitiatorHandler],
        host: str,
        port: int,
        protocol: ProtocolMetaData,
        sender_comp_id: str,
        target_comp_id: str,
        store: InitiatorStore,
        heartbeat_timeout: int,
        *,
        ssl: Optional[SSLContext] = None,
        shutdown_timeout: float = 10.0,
        heartbeat_threshold: int = 1,
        logon_time_range: Optional[Tuple[time, time]] = None,
        tz: tzinfo = None

) -> None:
    cancellation_token = asyncio.Event()
    loop = asyncio.get_event_loop()
    register_cancellation_token(cancellation_token, loop)

    handler = create_initiator(
        klass,
        protocol,
        sender_comp_id,
        target_comp_id,
        store,
        heartbeat_timeout,
        cancellation_token,
        heartbeat_threshold=heartbeat_threshold,
        logon_time_range=logon_time_range,
        tz=tz
    )

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
