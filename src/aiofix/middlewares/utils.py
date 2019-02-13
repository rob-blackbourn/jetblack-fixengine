from typing import Sequence
from ..types import Handler, Middleware
from functools import partial


def mw(middlewares: Sequence[Middleware], handler: Handler) -> Handler:
    for middleware in reversed(middlewares):
        handler = partial(middleware, handler=handler)
    return handler
