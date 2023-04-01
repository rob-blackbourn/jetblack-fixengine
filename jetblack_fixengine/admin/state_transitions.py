"""Admin state"""

from __future__ import annotations

import logging
from typing import Mapping

from ..types import InvalidStateTransitionError

from .types import AdminEvent, AdminState

LOGGER = logging.getLogger(__name__)


class AdminStateTransition:
    """State machine for the admin messages"""

    def __init__(
            self,
            transitions: Mapping[AdminState, Mapping[AdminEvent, AdminState]]
    ) -> None:
        self.transitions = transitions
        self.state = AdminState.DISCONNECTED

    def transition(self, event: AdminEvent) -> AdminState:
        """Transition to a new state.

        Args:
            event (AdminEvent): The event.

        Raises:
            InvalidStateTransitionError: If there is not valid transition.

        Returns:
            AdminState: The new state.
        """
        LOGGER.debug('Transition from %s with %s', self.state, event)
        try:
            self.state = self.transitions[self.state][event]
            return self.state
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled event {self.state.name} -> {event}.',
            ) from error

    def __str__(self) -> str:
        return f"AdminStateMachine: state={self.state}"

    __repr__ = __str__
