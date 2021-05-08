"""Start an acceptor"""

import logging
import os.path
from typing import Mapping, Any

from jetblack_fixparser.loader import load_yaml_protocol
from jetblack_fixengine import FileStore
from jetblack_fixengine.acceptor.helpers import start_acceptor, AcceptorHandler

logging.basicConfig(level=logging.DEBUG)

LOGGER = logging.getLogger(__name__)

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
etc = os.path.join(root, 'etc')

STORE = FileStore(os.path.join(root, 'store'))
HOST = '0.0.0.0'
PORT = 9801
SENDER_COMP_ID = 'ACCEPTOR'
TARGET_COMP_ID = 'INITIATOR1'
LOGON_TIMEOUT = 60
HEARTBEAT_TIMEOUT = 30
PROTOCOL = load_yaml_protocol('etc/FIX44.yaml')


class MyAcceptorHandler(AcceptorHandler):
    """An instance of the acceptor"""

    async def on_logon(self, _message: Mapping[str, Any]) -> None:
        LOGGER.info('on_logon')

    async def on_logout(self, _message: Mapping[str, Any]) -> None:
        LOGGER.info('on_logout')

    async def on_application_message(self, _message: Mapping[str, Any]) -> None:
        LOGGER.info('on_application_message')


start_acceptor(
    MyAcceptorHandler,
    HOST,
    PORT,
    PROTOCOL,
    SENDER_COMP_ID,
    TARGET_COMP_ID,
    STORE,
    HEARTBEAT_TIMEOUT,
    client_shutdown_timeout=10
)
