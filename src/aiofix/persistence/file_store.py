import aiofiles
import os.path
from typing import MutableMapping, Tuple
from ..types import Session, InitiatorStore


class FileSession(Session):

    def __init__(
            self,
            directory: str,
            sender_comp_id: str,
            target_comp_id: str
    ) -> None:
        self.filename = os.path.join(directory, f'{sender_comp_id}-{target_comp_id}-session.txt')
        if not os.path.exists(self.filename):
            with open(self.filename, 'wt') as f:
                f.write("0:0\n")
        elif not os.path.isfile(self.filename):
            raise RuntimeError(f'session file "{self.filename}" is not a file.')

        with open(self.filename) as f:
            line = f.readline() or '0:0'
            outgoing_seqnum, incoming_seqnum = line.rstrip('\n').split(':')

        self._sender_comp_id = sender_comp_id
        self._target_comp_id = target_comp_id
        self._outgoing_seqnum = int(outgoing_seqnum)
        self._incoming_seqnum = int(incoming_seqnum)

    async def _save(self) -> None:
        async with aiofiles.open(self.filename, 'wt') as f:
            await f.write(f'{self._outgoing_seqnum}:{self._incoming_seqnum}\n')

    @property
    def sender_comp_id(self) -> str:
        return self._sender_comp_id

    @property
    def target_comp_id(self) -> str:
        return self._target_comp_id

    async def get_seqnums(self) -> Tuple[int, int]:
        return self._outgoing_seqnum, self._incoming_seqnum

    async def set_seqnums(self, outgoing_seqnum: int, incoming_seqnums: int) -> None:
        self._outgoing_seqnum, self._incoming_seqnum = outgoing_seqnum, incoming_seqnums
        await self._save()

    async def get_outgoing_seqnum(self) -> int:
        return self._outgoing_seqnum

    async def set_outgoing_seqnum(self, seqnum: int) -> None:
        self._outgoing_seqnum = seqnum
        await self._save()

    async def get_incoming_seqnum(self) -> int:
        return self._incoming_seqnum

    async def set_incoming_seqnum(self, seqnum: int) -> None:
        self._incoming_seqnum = seqnum
        await self._save()


class FileInitiatorStore(InitiatorStore):

    def __init__(self, directory: str) -> None:
        if not os.path.exists(directory):
            os.makedirs(directory)
        elif not os.path.isdir(directory):
            raise RuntimeError(f'not a directory "{directory}"')

        self.directory = directory
        self._sessions: MutableMapping[str, FileSession] = dict()

    def get_session(self, sender_comp_id: str, target_comp_id: str) -> Session:
        key = sender_comp_id + '\x01' + target_comp_id

        if key in self._sessions:
            return self._sessions[key]

        session = FileSession(self.directory, sender_comp_id, target_comp_id)
        self._sessions[key] = session
        return session
