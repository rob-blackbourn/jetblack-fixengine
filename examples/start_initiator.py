import logging
import os.path
import tzlocal
from typing import Mapping, Any, Optional
from aiofix.loader import load_protocol
from aiofix.persistence import FileInitiatorStore
from aiofix.transports import start_initiator, InitiatorHandler

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
etc = os.path.join(root, 'etc')

STORE = FileInitiatorStore(os.path.join(root, 'store'))
HOST = '127.0.0.1'
PORT = 10101
SENDER_COMP_ID = 'CLIENT'
TARGET_COMP_ID = 'SERVER'
HEARTBEAT_TIMEOUT = 30
PROTOCOL = load_protocol('etc/FIX44.xml')
TZ = tzlocal.get_localzone()


class MyInitatorHandler(InitiatorHandler):

    async def on_logon(self) -> None:
        logger.info('on_logon')

    async def on_logout(self) -> None:
        logger.info('on_logoout')

    async def on_admin_message(self, message: Mapping[str, Any]) -> Optional[bool]:
        logger.info(f'on_admin_message {message}')
        return None

    async def on_application_message(self, message: Mapping[str, Any]) -> bool:
        logger.info(f'on_application_message {message}')
        return True


start_initiator(
    MyInitatorHandler,
    HOST,
    PORT,
    PROTOCOL,
    SENDER_COMP_ID,
    TARGET_COMP_ID,
    STORE,
    HEARTBEAT_TIMEOUT,
    shutdown_timeout=10
)
