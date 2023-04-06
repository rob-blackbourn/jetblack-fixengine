"""Transport state machine"""

from datetime import timezone
import logging
from typing import Mapping, Any, Optional, cast

from ..admin import (
    AdminState,
    AdminEvent,
    AdminMessage,
    AdminStateProcessor
)
from ..time_provider import TimeProvider

from .types import (
    TransportState,
    TransportEvent,
    TransportMessage,
)
from .state_processor import TransportStateProcessor

from ..types import FIXEngine, FIXApplication

LOGGER = logging.getLogger(__name__)


class TransportStateMachine(TransportStateProcessor):
    """A state machine for the transport layer"""

    def __init__(
            self,
            engine: FIXEngine,
            app: FIXApplication,
            admin_state_machine: AdminStateProcessor,
            time_provider: TimeProvider
    ) -> None:
        super().__init__(
            {
                TransportState.DISCONNECTED: {
                    TransportEvent.CONNECTION_RECEIVED: self._handle_connected
                },
                TransportState.CONNECTED: {
                    TransportEvent.FIX_RECEIVED: self._handle_fix,
                    TransportEvent.TIMEOUT_RECEIVED: self._handle_timeout,
                    TransportEvent.DISCONNECT_RECEIVED: self._handle_disconnect
                }
            }
        )
        self._engine = engine
        self._app = app
        self._admin_state_machine = admin_state_machine
        self._time_provider = time_provider
        self._last_receive_time_utc = self._time_provider.min(timezone.utc)

    async def _handle_connected(
            self,
            _transport_message: TransportMessage
    ) -> Optional[TransportMessage]:
        LOGGER.info('connected')
        await self._admin_state_machine.process(
            AdminMessage(AdminEvent.CONNECTED)
        )
        return None

    async def _handle_fix(
            self,
            transport_message: TransportMessage
    ) -> Optional[TransportMessage]:
        await self._engine.session.save_message(transport_message.buffer)

        fix_message = self._engine.fix_message_factory.decode(
            transport_message.buffer
        )
        LOGGER.info('Received %s', fix_message.message)

        msgcat = cast(str, fix_message.meta_data.msgcat)
        if msgcat == 'admin':
            await self._handle_admin_message(fix_message.message)
        else:
            await self._app.on_application_message(
                fix_message.message,
                self._engine
            )

        msg_seq_num: int = cast(int, fix_message.message['MsgSeqNum'])
        await self._engine.session.set_incoming_seqnum(msg_seq_num)

        self._last_receive_time_utc = self._time_provider.now(timezone.utc)

        return TransportMessage(TransportEvent.FIX_HANDLED)

    async def _handle_admin_message(self, message: Mapping[str, Any]) -> None:
        assert 'MsgType' in message

        LOGGER.info('admin message: %s', message)

        await self._app.on_admin_message(message, self._engine)

        await self._admin_state_machine.process(
            AdminMessage(
                AdminEvent.from_msg_type(message['MsgType']),
                message
            )
        )

    async def _handle_timeout(
            self,
            _transport_message: TransportMessage
    ) -> Optional[TransportMessage]:
        if self._admin_state_machine.state != AdminState.AUTHENTICATED:
            raise RuntimeError('Make a state for this')

        now_utc = self._time_provider.now(timezone.utc)
        seconds_since_last_receive = (
            now_utc - self._last_receive_time_utc
        ).total_seconds()
        elapsed = seconds_since_last_receive - self._engine.heartbeat_timeout
        if elapsed > self._engine.heartbeat_threshold:
            await self._admin_state_machine.process(
                AdminMessage(AdminEvent.TEST_HEARTBEAT_REQUIRED)
            )

        return TransportMessage(TransportEvent.TIMEOUT_HANDLED)

    async def _handle_disconnect(
            self,
            _transport_message: TransportMessage
    ) -> Optional[TransportMessage]:
        LOGGER.info('Disconnected')
        return None
