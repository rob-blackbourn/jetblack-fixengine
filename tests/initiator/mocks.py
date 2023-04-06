"""Mocks"""

from typing import Any, Awaitable, Callable, Mapping, Optional

from jetblack_fixparser.fix_message import FixMessageFactory

from jetblack_fixengine import Session
from jetblack_fixengine.initiator.types import AbstractInitiator
from jetblack_fixengine.types import FIXApp

SendMessage = Callable[[str, Optional[Mapping[str, Any]]], Awaitable[None]]


class MockInitiator(AbstractInitiator):

    def __init__(
            self,
            session: Session,
            fix_message_factory: FixMessageFactory,
            heartbeat_timeout: int,
            heartbeat_threshold: int,
            send_message: SendMessage
    ) -> None:
        super().__init__()
        self._session = session
        self._fix_message_factory = fix_message_factory
        self._heartbeat_timeout = heartbeat_timeout
        self._heartbeat_threshold = heartbeat_threshold
        self._send_message = send_message

    @property
    def session(self) -> Session:
        return self._session

    @property
    def fix_message_factory(self) -> FixMessageFactory:
        return self._fix_message_factory

    @property
    def heartbeat_timeout(self) -> int:
        return self._heartbeat_timeout

    @property
    def heartbeat_threshold(self) -> int:
        return self._heartbeat_threshold

    async def send_message(
            self,
            msg_type: str,
            message: Optional[Mapping[str, Any]] = None
    ) -> None:
        await self._send_message(msg_type, message)


class InitiatorApp(FIXApp):

    async def on_admin_message(self, message: Mapping[str, Any]) -> None:
        pass

    async def on_heartbeat(self, message: Mapping[str, Any]) -> None:
        pass

    async def on_application_message(self, message: Mapping[str, Any]) -> None:
        pass

    async def on_logon(self, message: Mapping[str, Any]) -> None:
        pass

    async def on_logout(self, message: Mapping[str, Any]) -> None:
        pass
