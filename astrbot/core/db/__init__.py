"""Database engine and session lifecycle ownership."""

import abc
import typing as T
from contextlib import asynccontextmanager
from weakref import WeakSet

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class BaseDatabase(abc.ABC):
    """Own the database engine, session factory, and their lifecycle."""

    DATABASE_URL = ""

    def __init__(self) -> None:
        # SQLite only supports a single writer at a time. Without a busy
        # timeout the driver raises "database is locked" instantly when a
        # second write is attempted. Setting timeout=30 tells SQLite to wait
        # up to 30 s for the lock, which is enough for brief write bursts.
        is_sqlite = "sqlite" in self.DATABASE_URL
        connect_args = {"timeout": 30} if is_sqlite else {}
        self.engine = create_async_engine(
            self.DATABASE_URL,
            echo=False,
            future=True,
            connect_args=connect_args,
        )
        self.AsyncSessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._active_sessions: WeakSet[AsyncSession] = WeakSet()
        self.inited = False

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Initialize the database schema and connection settings."""

    @asynccontextmanager
    async def get_db(self) -> T.AsyncGenerator[AsyncSession]:
        """Yield a tracked database session."""
        if not self.inited:
            await self.initialize()
            self.inited = True
        session = self.AsyncSessionLocal()
        self._active_sessions.add(session)
        try:
            yield session
        finally:
            try:
                await session.close()
            finally:
                self._active_sessions.discard(session)

    async def close(self) -> None:
        """Close tracked sessions and dispose the database engine."""
        for session in list(self._active_sessions):
            try:
                await session.close()
            finally:
                self._active_sessions.discard(session)
        await self.engine.dispose()
        self.inited = False
