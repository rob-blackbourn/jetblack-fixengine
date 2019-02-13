import logging
import os.path
from aiofix.loader import load_protocol
from aiofix.persistence import FileInitiatorStore
from aiofix.transports import start_initiator, InitiatorHandler
from aiofix.middlewares import FixMessageMiddleware, mw

logging.basicConfig(level=logging.DEBUG)

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
etc = os.path.join(root, 'etc')

store = FileInitiatorStore(os.path.join(root, 'store'))

HOST = '127.0.0.1'
PORT = 10101
SENDER_COMP_ID = 'CLIENT'
TARGET_COMP_ID = 'SERVER'

protocol = load_protocol('etc/FIX44.xml')

initator_handler = InitiatorHandler(protocol, SENDER_COMP_ID, TARGET_COMP_ID, store, heartbeat_timeout=30)
middleware = FixMessageMiddleware(protocol)

start_initiator(HOST, PORT, mw([middleware], handler=initator_handler), shutdown_timeout=10)
