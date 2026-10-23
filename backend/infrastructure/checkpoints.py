"""Use the official SQLite saver through Agent Server's documented lifecycle."""
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.config.settings import DATA


@asynccontextmanager
async def checkpointer():
    async with AsyncSqliteSaver.from_conn_string(str(DATA / 'checkpoints.sqlite')) as saver:
        await saver.setup()
        yield saver
