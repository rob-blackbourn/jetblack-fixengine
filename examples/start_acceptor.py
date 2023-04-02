"""Start an acceptor"""

import asyncio
import logging
from pathlib import Path
from typing import Mapping, Any

from jetblack_fixparser import load_yaml_protocol
from jetblack_fixengine import FileStore
from jetblack_fixengine import start_acceptor, Acceptor


LOGGER = logging.getLogger(__name__)


class MyAcceptor(Acceptor):
    """An instance of the acceptor"""

    async def on_logon(self, _message: Mapping[str, Any]):
        LOGGER.info('on_logon')

    async def on_logout(self, _message: Mapping[str, Any]) -> None:
        LOGGER.info('on_logout')

    async def on_application_message(self, _message: Mapping[str, Any]) -> None:
        LOGGER.info('on_application_message')


PROTOCOL = load_yaml_protocol(Path('etc') / 'FIX44.yaml')
STORE = FileStore(Path("store"))
HOST = '0.0.0.0'
PORT = 9801
SENDER_COMP_ID = 'ACCEPTOR'
TARGET_COMP_ID = 'INITIATOR1'
LOGON_TIMEOUT = 60
HEARTBEAT_TIMEOUT = 30

logging.basicConfig(level=logging.DEBUG)

asyncio.run(
    start_acceptor(
        MyAcceptor,
        HOST,
        PORT,
        PROTOCOL,
        SENDER_COMP_ID,
        TARGET_COMP_ID,
        STORE,
        HEARTBEAT_TIMEOUT,
        client_shutdown_timeout=10
    )
)
