"""Transport state transitions"""

import logging

from ..types import InvalidStateTransitionError

from .types import (
    TransportState,
    TransportEvent,
    TransportTransitionMapping,
)

LOGGER = logging.getLogger(__name__)


class TransportStateTransitions:
    """A class to manage state transitions for the transport"""

    TRANSITIONS: TransportTransitionMapping = {
        TransportState.DISCONNECTED:  {
            TransportEvent.CONNECTION_RECEIVED: TransportState.CONNECTED
        },
        TransportState.CONNECTED: {
            TransportEvent.FIX_RECEIVED: TransportState.FIX,
            TransportEvent.TIMEOUT_RECEIVED: TransportState.TIMEOUT,
            TransportEvent.DISCONNECT_RECEIVED: TransportState.DISCONNECTED
        },
        TransportState.FIX: {
            TransportEvent.FIX_HANDLED: TransportState.CONNECTED
        },
        TransportState.TIMEOUT: {
            TransportEvent.TIMEOUT_HANDLED: TransportState.CONNECTED
        },
    }

    def __init__(self) -> None:
        self.state = TransportState.DISCONNECTED

    def transition(self, event: TransportEvent) -> TransportState:
        """Transition from the current state to a new state given an event.

        Args:
            event (TransportEvent): The event.

        Raises:
            InvalidStateTransitionError: If the transition was invalid.

        Returns:
            TransportState: The new state.
        """
        LOGGER.debug('Transition from %s with %s', self.state, event)
        try:
            self.state = self.TRANSITIONS[self.state][event]
            return self.state
        except KeyError as error:
            raise InvalidStateTransitionError(
                f'unhandled event {self.state.name} -> {event.name}.',
            ) from error
