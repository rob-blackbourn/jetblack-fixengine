"""A sqlite3 store"""

import sqlite3
from typing import Any, List, Mapping, MutableMapping, Tuple

import aiosqlite

from ..types import Session, Store

CREATE_SEQNUM_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS initiator_seqnums
(
    sender_comp_id VARCHAR(64) NOT NULL,
    target_comp_id VARCHAR(64) NOT NULL,
    outgoing_seqnum INT NOT NULL,
    incoming_seqnum INT NOT NULL,
    PRIMARY KEY (sender_comp_id, target_comp_id)
)
"""

SEQNUM_QUERY = """
SELECT outgoing_seqnum, incoming_seqnum
FROM initiator_seqnums
WHERE sender_comp_id = ? AND target_comp_id = ?
"""

SEQNUM_INSERT = """
INSERT INTO initiator_seqnums(sender_comp_id, target_comp_id, outgoing_seqnum, incoming_seqnum)
VALUES ( ?, ?, ?, ?)
"""

SEQNUM_UPDATE = """
UPDATE initiator_seqnums
SET outgoing_seqnum = ?, incoming_seqnum = ?
WHERE sender_comp_id = ? AND target_comp_id = ?
"""

SEQNUM_UPDATE_OUTGOING = """
UPDATE initiator_seqnums
SET outgoing_seqnum = ?
WHERE sender_comp_id = ? AND target_comp_id = ?
"""

SEQNUM_UPDATE_INCOMING = """
UPDATE initiator_seqnums
SET incoming_seqnum = ?
WHERE sender_comp_id = ? AND target_comp_id = ?
"""

CREATE_MESSAGE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS initiator_messages
(
    sender_comp_id VARCHAR(64) NOT NULL,
    target_comp_id VARCHAR(64) NOT NULL,
    outgoing_seqnum INT NOT NULL,
    incoming_seqnum INT NOT NULL,
    message VARCHAR(2048) NOT NULL,
    PRIMARY KEY (sender_comp_id, target_comp_id)
)
"""

MESSAGE_INSERT = """
INSERT INTO initiator_messages(sender_comp_id, target_comp_id, outgoing_seqnum, incoming_seqnum, message)
VALUES ( ?, ?, ?, ?, ?)
"""


class SqlSession(Session):
    """A persistent session backed by sqlite"""

    def __init__(
            self,
            conn_args: List[Any],
            conn_kwargs: Mapping[str, Any],
            sender_comp_id: str,
            target_comp_id: str
    ) -> None:
        self.conn_args = conn_args
        self.conn_kwargs = conn_kwargs

        conn = sqlite3.connect(*self.conn_args, **self.conn_kwargs)
        cursor = conn.cursor()

        cursor.execute(SEQNUM_QUERY, (sender_comp_id, target_comp_id))
        result = cursor.fetchone()
        if result:
            self._outgoing_seqnum, self._incoming_seqnum = result
        else:
            cursor.execute(
                SEQNUM_INSERT,
                (sender_comp_id, target_comp_id, 0, 0)
            )
            conn.commit()
            self._outgoing_seqnum, self._incoming_seqnum = 0, 0

        self._sender_comp_id = sender_comp_id
        self._target_comp_id = target_comp_id

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
        async with aiosqlite.connect(*self.conn_args, **self.conn_kwargs) as db:
            await db.execute(
                SEQNUM_UPDATE,
                (
                    self._outgoing_seqnum,
                    self._incoming_seqnum,
                    self.sender_comp_id,
                    self.target_comp_id
                )
            )
            await db.commit()

    async def get_outgoing_seqnum(self) -> int:
        return self._outgoing_seqnum

    async def set_outgoing_seqnum(self, seqnum: int) -> None:
        self._outgoing_seqnum = seqnum
        async with aiosqlite.connect(*self.conn_args, **self.conn_kwargs) as db:
            await db.execute(
                SEQNUM_UPDATE_OUTGOING,
                (
                    self._outgoing_seqnum,
                    self.sender_comp_id,
                    self.target_comp_id
                )
            )
            await db.commit()

    async def get_incoming_seqnum(self) -> int:
        return self._incoming_seqnum

    async def set_incoming_seqnum(self, seqnum: int) -> None:
        self._incoming_seqnum = seqnum
        async with aiosqlite.connect(*self.conn_args, **self.conn_kwargs) as db:
            await db.execute(
                SEQNUM_UPDATE_INCOMING,
                (
                    self._incoming_seqnum,
                    self.sender_comp_id,
                    self.target_comp_id
                )
            )
            await db.commit()

    async def save_message(self, buf: bytes) -> None:
        async with aiosqlite.connect(*self.conn_args, **self.conn_kwargs) as db:
            message = buf.decode('ascii')
            await db.execute(
                MESSAGE_INSERT,
                (
                    self.sender_comp_id,
                    self.target_comp_id,
                    self._outgoing_seqnum,
                    self._incoming_seqnum,
                    message
                )
            )
            await db.commit()


class SqlStore(Store):
    """A session store back by sqlite"""

    def __init__(
            self,
            conn_args: List[Any],
            conn_kwargs: Mapping[str, Any]
    ) -> None:
        self.conn_args = conn_args
        self.conn_kwargs = conn_kwargs
        conn = sqlite3.connect(*self.conn_args, **self.conn_kwargs)
        cursor = conn.cursor()
        cursor.execute(CREATE_SEQNUM_TABLE_SQL)
        cursor.execute(CREATE_MESSAGE_TABLE_SQL)
        self._sessions: MutableMapping[str, SqlSession] = dict()

    def get_session(self, sender_comp_id: str, target_comp_id: str) -> Session:
        key = sender_comp_id + '\x01' + target_comp_id

        if key in self._sessions:
            return self._sessions[key]

        session = SqlSession(
            self.conn_args,
            self.conn_kwargs,
            sender_comp_id,
            target_comp_id
        )
        self._sessions[key] = session
        return session
