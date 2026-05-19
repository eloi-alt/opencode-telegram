from __future__ import annotations

import aiosqlite

from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.persistence.sqlite_repository import SCHEMA

log = get_logger("opencode_telegram.infrastructure.persistence.database")


class Database:
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> aiosqlite.Connection:
        if self._conn is None:
            path = self._path
            if path.startswith("sqlite+aiosqlite:///"):
                path = path[len("sqlite+aiosqlite:///"):]
            self._conn = await aiosqlite.connect(path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            await self._conn.executescript(SCHEMA)
            log.info("database_connected", path=path)
        return self._conn

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            log.info("database_closed")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn
