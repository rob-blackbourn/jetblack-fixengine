"""File storage"""

from pathlib import Path
from typing import Literal, MutableMapping, Tuple, Union
from urllib.parse import quote_from_bytes

import aiofiles
from jetblack_fixparser.fix_message import SOH

from ..types import Session, Store

MessageStyle = Literal['text', 'urlencode', 'hex']


class FileSession(Session):
    """A session using files for persistence"""

    def __init__(
            self,
            folder: Path,
            sender_comp_id: str,
            target_comp_id: str,
            message_style: MessageStyle
    ) -> None:
        # The file for the sequence numbers.
        self.seqnum_path = (
            folder / f'{sender_comp_id}-{target_comp_id}-initiator-seqnum.txt'
        )
        if not self.seqnum_path.exists():
            with self.seqnum_path.open('wt', encoding='utf8') as file_ptr:
                file_ptr.write("0:0\n")
        elif not self.seqnum_path.is_file():
            raise RuntimeError(
                f'session file "{self.seqnum_path}" is not a file.'
            )

        with self.seqnum_path.open(encoding="utf8") as file_ptr:
            line = file_ptr.readline() or '0:0'
            outgoing_seqnum, incoming_seqnum = line.rstrip('\n').split(':')

        self._sender_comp_id = sender_comp_id
        self._target_comp_id = target_comp_id
        self._outgoing_seqnum = int(outgoing_seqnum)
        self._incoming_seqnum = int(incoming_seqnum)

        # The file for the messages
        self.message_path = (
            folder / f'{sender_comp_id}-{target_comp_id}-initiator-message.txt'
        )
        self.message_style = message_style

    async def _save(self) -> None:
        async with aiofiles.open(self.seqnum_path, 'wt') as file_ptr:
            await file_ptr.write(
                f'{self._outgoing_seqnum}:{self._incoming_seqnum}\n'
            )

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

        async with aiofiles.open(self.message_path, 'at') as file_ptr:
            if self.message_style == 'text':
                await file_ptr.write(buf.replace(SOH, b'|').decode() + '\n')
            elif self.message_style == 'urlencode':
                await file_ptr.write(quote_from_bytes(buf) + '\n')
            elif self.message_style == 'hex':
                await file_ptr.write(buf.hex())
            else:
                raise ValueError(
                    'invalid message style "{self.message_style}"'
                )
            await file_ptr.flush()


class FileStore(Store):
    """A store using files for persistence"""

    def __init__(
            self,
            folder: Union[str, Path],
            *,
            message_style: MessageStyle = 'text'
    ) -> None:
        if not isinstance(folder, Path):
            folder = Path(folder)

        if not folder.exists():
            folder.mkdir()
        elif not folder.is_dir():
            raise RuntimeError(f'not a directory "{folder}"')

        self.folder = folder
        self._sessions: MutableMapping[str, FileSession] = dict()
        self.message_style: MessageStyle = message_style

    def get_session(self, sender_comp_id: str, target_comp_id: str) -> Session:
        key = sender_comp_id + '\x01' + target_comp_id

        if key in self._sessions:
            return self._sessions[key]

        session = FileSession(
            self.folder,
            sender_comp_id,
            target_comp_id,
            self.message_style
        )
        self._sessions[key] = session
        return session
