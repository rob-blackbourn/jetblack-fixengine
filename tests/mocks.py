"""Mocks"""

from typing import Tuple

from jetblack_fixengine import Session, Store


class MockSession(Session):
    """A mock session"""

    def __init__(
            self,
            sender_comp_id: str,
            target_comp_id: str,
            outgoing_seqnum: int,
            incoming_seqnum: int,
    ) -> None:
        super().__init__()
        self._sender_comp_id = sender_comp_id
        self._target_comp_id = target_comp_id
        self._outgoing_seqnum = outgoing_seqnum
        self._incoming_seqnum = incoming_seqnum

    @property
    def sender_comp_id(self) -> str:
        return self._sender_comp_id

    @property
    def target_comp_id(self) -> str:
        return self._target_comp_id

    async def get_seqnums(self) -> Tuple[int, int]:
        return self._outgoing_seqnum, self._incoming_seqnum

    async def set_seqnums(self, outgoing_seqnum: int, incoming_seqnum: int) -> None:
        self._outgoing_seqnum = outgoing_seqnum
        self._incoming_seqnum = incoming_seqnum

    async def get_outgoing_seqnum(self) -> int:
        return self._outgoing_seqnum

    async def set_outgoing_seqnum(self, seqnum: int) -> None:
        self._outgoing_seqnum = seqnum

    async def get_incoming_seqnum(self) -> int:
        return self._incoming_seqnum

    async def set_incoming_seqnum(self, seqnum: int) -> None:
        self._incoming_seqnum = seqnum

    async def save_message(self, buf: bytes) -> None:
        pass


class MockStore(Store):

    def get_session(self, sender_comp_id: str, target_comp_id: str) -> Session:
        return MockSession(sender_comp_id, target_comp_id, 1, 1)
