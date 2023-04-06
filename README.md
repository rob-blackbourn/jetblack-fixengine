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
    AcceptorConfig,
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
```

Note that throwing the exception `LogonError` from `on_logon` will reject
the logon request.

### Stores

The engines need to store their state. Two stores are currently provided:
a file store (`FileStore`) and sqlite (`SqlStore`).

## Implementation

The engines are implemented as state machines. This means they can be
tested without the need for IO.
