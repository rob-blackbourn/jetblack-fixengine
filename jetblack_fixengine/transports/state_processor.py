"""A transport state processor"""

import logging
from typing import Callable, Awaitable, Optional

from .state_transitions import TransportStateTransitions
from .types import (
    TransportState,
    TransportMessage,
    TransportEventHandlerMapping
)

LOGGER = logging.getLogger(__name__)


class TransportStateProcessor(TransportStateTransitions):
    """A transport state processor with async bindings"""

    def __init__(
            self,
            handlers: TransportEventHandlerMapping
    ) -> None:
        super().__init__()
        self._handlers = handlers

    async def process(
            self,
            message: Optional[TransportMessage]
    ) -> TransportState:
        """Process a transport message

        Args:
            message (Optional[TransportMessage]): The message

        Returns:
            TransportState: The new state.
        """
        while message is not None:
            handler = self._handlers.get(self.state, {}).get(message.event)
            self.transition(message.event)
            if handler is None:
                break
            message = await handler(message)
        return self.state


Send = Callable[[TransportMessage], Awaitable[None]]
Receive = Callable[[], Awaitable[TransportMessage]]
TransportHandler = Callable[[Send, Receive], Awaitable[None]]
