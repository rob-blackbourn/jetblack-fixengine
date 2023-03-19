"""File storage"""

import os.path
from typing import Optional
from urllib.parse import quote_from_bytes
from typing import MutableMapping, Tuple

import aiofiles

from ..types import Session, Store


class FileSession(Session):

    def __init__(
            self,
            directory: str,
            sender_comp_id: str,
            target_comp_id: str,
            *,
            message_style: Optional[str] = 'urlencode'
    ) -> None:
        # The file for the sequence numbers.
        self.seqnum_filename = os.path.join(
            directory, f'{sender_comp_id}-{target_comp_id}-initiator-seqnum.txt')
        if not os.path.exists(self.seqnum_filename):
            with open(self.seqnum_filename, 'wt', encoding='utf8') as file_ptr:
                file_ptr.write("0:0\n")
        elif not os.path.isfile(self.seqnum_filename):
            raise RuntimeError(
                f'session file "{self.seqnum_filename}" is not a file.')

        with open(self.seqnum_filename, encoding="utf8") as file_ptr:
            line = file_ptr.readline() or '0:0'
            outgoing_seqnum, incoming_seqnum = line.rstrip('\n').split(':')

        self._sender_comp_id = sender_comp_id
        self._target_comp_id = target_comp_id
        self._outgoing_seqnum = int(outgoing_seqnum)
        self._incoming_seqnum = int(incoming_seqnum)

        # The file for the messages
        self.message_filename = os.path.join(
            directory, f'{sender_comp_id}-{target_comp_id}-initiator-message.txt')
        self.message_style = message_style

    async def _save(self) -> None:
        async with aiofiles.open(self.seqnum_filename, 'wt') as f:
            await f.write(f'{self._outgoing_seqnum}:{self._incoming_seqnum}\n')

    @property
    def sender_comp_id(self) -> str:
        return self._sender_comp_id

    @property
    def target_comp_id(self) -> str:
        return self._target_comp_id

    async def get_seqnums(self) -> Tuple[int, int]:
        return self._outgoing_seqnum, self._incoming_seqnum

    async def set_seqnums(self, outgoing_seqnum: int, incoming_seqnum: int) -> None:
        self._outgoing_seqnum, self._incoming_seqnum = outgoing_seqnum, incoming_seqnum
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

    async def save_message(self, buf: bytes) -> None:
        async with aiofiles.open(self.message_filename, 'at') as file_ptr:
            if self.message_style == 'urlencode':
                await file_ptr.write(quote_from_bytes(buf) + '\n')
            else:
                await file_ptr.write(buf.decode("utf8"))
            await file_ptr.flush()


class FileStore(Store):

    def __init__(
            self,
            directory: str,
            *,
            message_style: Optional[str] = 'urlencode'
    ) -> None:
        if not os.path.exists(directory):
            os.makedirs(directory)  # type: ignore
        elif not os.path.isdir(directory):
            raise RuntimeError(f'not a directory "{directory}"')

        self.directory = directory
        self._sessions: MutableMapping[str, FileSession] = dict()
        self.message_style = message_style

    def get_session(self, sender_comp_id: str, target_comp_id: str) -> Session:
        key = sender_comp_id + '\x01' + target_comp_id

        if key in self._sessions:
            return self._sessions[key]

        session = FileSession(self.directory, sender_comp_id,
                              target_comp_id, message_style=self.message_style)
        self._sessions[key] = session
        return session
