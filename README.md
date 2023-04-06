# jetblack-fixengine

A pure python asyncio FIX engine.

## Status

This is work in progress.

## Installation

The package can be install from the pie store.

```bash
pip install jetblack-fixengine
```

## Overview

This project provides a pure Python, asyncio implementation of
a FIX engine, supporting both initiators and acceptors.

The engine uses the [jetblack-fixparser](https://github.com/rob-blackbourn/jetblack-fixparser)
package to present the FIX messages a plain Python objects. For example, a `LOGON` message
can be sent as follows:

```python
await send_message({
    'MsgType': 'LOGON',
    'MsgSeqNum': 42,
    'SenderCompID': 'ME',
    'TargetCompID': 'BANK OF SOMEWHERE',
    'SendingTime': datetime.now(timezone.utc),
    'EncryptMethod': "NONE",
    'HeartBtInt': 30
})
```

### FIX Protocols

The FIX protocol is a combination of *well known* messages (like `LOGON`)
and *custom* messages (like an order to buy or sell). The protocol
has evolved through a number of different versions providing new features.

Because of this the protocols are provided by config files. Historically
`XML` was used. While this is supported, `yaml` is preferred and some
example protocols are provided in the
[etc](https://github.com/rob-blackbourn/jetblack-fixengine/tree/master/etc)
folder.

Currently supported versions are 4.0, 4.1, 4.2, 4.3, 4.4.

### Initiators

An initiator is a class which inherits from `FIXApplication`, and implements a
few methods, and has access to `send_message` from the `fix_engine`. Here is an example.

```python
import asyncio
import logging
from pathlib import Path
from typing import Mapping, Any

from jetblack_fixparser import load_yaml_protocol
from jetblack_fixengine import (
    FileStore,
    start_initiator,
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


PROTOCOL = load_yaml_protocol(Path('etc') / 'FIX44.yaml')
STORE = FileStore(Path('store'))
HOST = '127.0.0.1'
PORT = 9801
SENDER_COMP_ID = 'INITIATOR1'
TARGET_COMP_ID = 'ACCEPTOR'
LOGON_TIMEOUT = 60
HEARTBEAT_TIMEOUT = 30

logging.basicConfig(level=logging.DEBUG)

asyncio.run(
    start_initiator(
        MyInitiator(),
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
)
```

### Acceptor

The acceptor works in the same way as the initiator. Here is an example:

```python
import asyncio
import logging
from pathlib import Path
from typing import Mapping, Any

from jetblack_fixparser import load_yaml_protocol
from jetblack_fixengine import (
    FileStore,
    start_acceptor,
    FIXApplication,
    FIXEngine
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
        MyAcceptor(),
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
```

Note that throwing the exception `LogonError` from `on_logon` will reject
the logon request.

### Stores

The engines need to store their state. Two stores are currently provided:
a file store (`FileStore`) and sqlite (`SqlStore`).

## Implementation

The engines are implemented as state machines. This means they can be
tested without the need for IO.
