import asyncio
import logging
import signal

logger = logging.getLogger(__name__)


def _cancel(signame: str, signum: int, cancellation_token: asyncio.Event) -> None:
    msg = f'received signal {signame}'
    logger.info(msg) if signum == signal.SIGINT else logger.warning(msg)
    cancellation_token.set()


def register_cancellation_token(cancellation_token: asyncio.Event, loop: asyncio.AbstractEventLoop):
    for signame in ('SIGHUP', 'SIGINT', 'SIGTERM'):
        signum = getattr(signal, signame)
        loop.add_signal_handler(signum, _cancel, signame, signum, cancellation_token)
