"""A simple Initiator"""

import asyncio
import logging
from pathlib import Path
from typing import Mapping, Any

from jetblack_fixparser import load_yaml_protocol
from jetblack_fixengine import (
    FileStore,
    start_initiator,
    InitiatorConfig,
    FIXApplication,
    FIXEngine
)

LOGGER = logging.getLogger(__name__)


class MyInitiator(FIXApplication):
    """An instance of the initiator"""

    async def on_logon(
            self,
            _message: Mapping[str, Any],
            fix_engine: FIXEngine
    ) -> None:
        LOGGER.info('on_logon')

    async def on_logout(
            self,
            _message: Mapping[str, Any],
            fix_engine: FIXEngine
    ) -> None:
        LOGGER.info('on_logout')

    async def on_application_message(
            self,
            _message: Mapping[str, Any],
            fix_engine: FIXEngine
    ) -> None:
        LOGGER.info('on_application_message')


app = MyInitiator()
config = InitiatorConfig(
    '127.0.0.1',
    9801,
    load_yaml_protocol(Path('etc') / 'FIX44.yaml'),
    'INITIATOR1',
    'ACCEPTOR',
    FileStore(Path('store'))
)

logging.basicConfig(level=logging.DEBUG)

asyncio.run(
    start_initiator(app, config)
)
