"""Admin state"""

from __future__ import annotations

import logging
from typing import Mapping, Optional

from .state_transitions import AdminStateTransition
from .types import (
    AdminEvent,
    AdminState,
    AdminEventHandlerMapping,
    AdminMessage
)

LOGGER = logging.getLogger(__name__)


class AdminStateProcessor(AdminStateTransition):
    """An admin state machine with async handlers"""

    def __init__(
            self,
            transitions: Mapping[AdminState, Mapping[AdminEvent, AdminState]],
            state_handlers: AdminEventHandlerMapping
    ) -> None:
        super().__init__(transitions)
        self._handlers = state_handlers

    async def process(
            self,
            message: Optional[AdminMessage]
    ) -> AdminState:
        """Process an admin message.

        Args:
            message (Optional[AdminMessage]): The message.

        Returns:
            AdminState: The new state.
        """
        while message is not None:
            handler = self._handlers.get(self.state, {}).get(message.event)
            self.transition(message.event)
            if handler is None:
                break
            message = await handler(message)
        return self.state
