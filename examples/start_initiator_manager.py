"""Sart the initiator manager"""

import calendar
from datetime import time
import logging
import os.path
import pytz
from typing import Optional, Mapping, Any
from jetblack_fixengine.transports import InitiatorHandler
from jetblack_fixengine.persistence import FileStore
from jetblack_fixengine.managers import start_initiator_manager
from jetblack_fixparser.loader import load_yaml_protocol

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
etc = os.path.join(root, 'etc')

STORE = FileStore(os.path.join(root, 'store'))
HOST = '127.0.0.1'
PORT = 10101
SENDER_COMP_ID = 'CLIENT'
TARGET_COMP_ID = 'SERVER'
PROTOCOL = load_yaml_protocol(os.path.join(etc, 'FIX44.yaml'))
HEARTBEAT_TIMEOUT = 30
TZ = pytz.timezone('Europe/London')


class MyInitatorHandler(InitiatorHandler):

    async def on_logon(self) -> None:
        logger.info('on_logon')

    async def on_logout(self) -> None:
        logger.info('on_logout')

    async def on_admin_message(self, message: Mapping[str, Any]) -> Optional[bool]:
        logger.info(f'on_admin_message {message}')
        return None

    async def on_application_message(self, message: Mapping[str, Any]) -> bool:
        logger.info(f'on_application_message {message}')
        return True


start_initiator_manager(
    MyInitatorHandler,
    HOST,
    PORT,
    PROTOCOL,
    SENDER_COMP_ID,
    TARGET_COMP_ID,
    STORE,
    HEARTBEAT_TIMEOUT,
    tz=TZ,
    # session_dow_range=(calendar.MONDAY, calendar.FRIDAY),
    # session_time_range=(time(6, 0, 0), time(18, 0, 0)),
    # logon_time_range=(time(8, 0, 0), time(17, 0, 0))
)
