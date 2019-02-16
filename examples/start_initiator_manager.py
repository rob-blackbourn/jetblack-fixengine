import calendar
import datetime
import logging
import os.path
from aiofix.persistence import FileInitiatorStore
from aiofix.managers import start_initator_manager
from aiofix.loader import load_protocol

logging.basicConfig(level=logging.DEBUG)

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
etc = os.path.join(root, 'etc')

store = FileInitiatorStore(os.path.join(root, 'store'))
HOST = '127.0.0.1'
PORT = 10101
SENDER_COMP_ID = 'CLIENT'
TARGET_COMP_ID = 'SERVER'

protocol = load_protocol(os.path.join(etc, 'FIX44.xml'))

start_initator_manager(
    HOST,
    PORT,
    protocol,
    SENDER_COMP_ID,
    TARGET_COMP_ID,
    store,
    session_dow_range=(calendar.MONDAY, calendar.FRIDAY)
)
