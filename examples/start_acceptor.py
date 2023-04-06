"""Start an acceptor"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Mapping

from jetblack_fixparser import load_yaml_protocol

from jetblack_fixengine import (
    AcceptorConfig,
    FileStore,
    FIXApplication,
    FIXEngine,
    start_acceptor
)


LOGGER = logging.getLogger(__name__)


class MyAcceptor(FIXApplication):
    """An instance of the acceptor"""

    async def on_logon(
            self,
            _message: Mapping[str, Any],
            _fix_engine: FIXEngine
    ) -> None:
        LOGGER.info('on_logon')

    async def on_logout(
            self,
            _message: Mapping[str, Any],
            _fix_engine: FIXEngine
    ) -> None:
        LOGGER.info('on_logout')

    async def on_application_message(
            self,
            _message: Mapping[str, Any],
            _fix_engine: FIXEngine
    ) -> None:
        LOGGER.info('on_application_message')


logging.basicConfig(level=logging.DEBUG)

app = MyAcceptor()
config = AcceptorConfig(
    '0.0.0.0',
    9801,
    load_yaml_protocol(Path('etc') / 'FIX44.yaml'),
    'ACCEPTOR',
    'INITIATOR1',
    FileStore(Path("store"))
)

asyncio.run(
    start_acceptor(
        app,
        config
    )
)
