"""A simple Initiator"""

from datetime import time
import logging
import os.path
from typing import Mapping, Any, Optional

import pytz

from jetblack_fixparser.loader import load_yaml_protocol
from aiofix.persistence import FileStore
from aiofix.transports import start_initiator, InitiatorHandler

logging.basicConfig(level=logging.DEBUG)

LOGGER = logging.getLogger(__name__)

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
etc = os.path.join(root, 'etc')

STORE = FileStore(os.path.join(root, 'store'))
HOST = '127.0.0.1'
PORT = 9801
SENDER_COMP_ID = 'INITIATOR1'
TARGET_COMP_ID = 'ACCEPTOR'
HEARTBEAT_TIMEOUT = 30
PROTOCOL = load_yaml_protocol('etc/FIX44.yaml')
TZ = pytz.timezone('Europe/London')


class MyInitiatorHandler(InitiatorHandler):
    """An instance of the initiator"""

    async def on_logon(self) -> None:
        LOGGER.info('on_logon')

    async def on_logout(self) -> None:
        LOGGER.info('on_logout')

    async def on_admin_message(self, message: Mapping[str, Any]) -> Optional[bool]:
        LOGGER.info('on_admin_message %s', message)
        return None

    async def on_application_message(self, message: Mapping[str, Any]) -> bool:
        LOGGER.info('on_application_message %s', message)
        return True


start_initiator(
    MyInitiatorHandler,
    HOST,
    PORT,
    PROTOCOL,
    SENDER_COMP_ID,
    TARGET_COMP_ID,
    STORE,
    HEARTBEAT_TIMEOUT,
    shutdown_timeout=10,
    logon_time_range=(time(0, 30, 0), time(23, 30, 0)),
    tz=TZ
)
