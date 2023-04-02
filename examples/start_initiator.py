"""A simple Initiator"""

import logging
import os.path
from typing import Mapping, Any

from jetblack_fixparser.loader import load_yaml_protocol
from jetblack_fixengine import FileStore
from jetblack_fixengine import start_initiator, Initiator

LOGGER = logging.getLogger(__name__)


class MyInitiator(Initiator):
    """An instance of the initiator"""

    async def on_logon(self, _message: Mapping[str, Any]) -> None:
        LOGGER.info('on_logon')

    async def on_logout(self, _message: Mapping[str, Any]) -> None:
        LOGGER.info('on_logout')

    async def on_application_message(self, _message: Mapping[str, Any]) -> None:
        LOGGER.info('on_application_message')


root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
etc = os.path.join(root, 'etc')

STORE = FileStore(os.path.join(root, 'store'))
HOST = '127.0.0.1'
PORT = 9801
SENDER_COMP_ID = 'INITIATOR1'
TARGET_COMP_ID = 'ACCEPTOR'
LOGON_TIMEOUT = 60
HEARTBEAT_TIMEOUT = 30
PROTOCOL = load_yaml_protocol('etc/FIX44.yaml')

logging.basicConfig(level=logging.DEBUG)

start_initiator(
    MyInitiator,
    HOST,
    PORT,
    PROTOCOL,
    SENDER_COMP_ID,
    TARGET_COMP_ID,
    STORE,
    LOGON_TIMEOUT,
    HEARTBEAT_TIMEOUT,
    shutdown_timeout=10
)
