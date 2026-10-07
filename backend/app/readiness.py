"""Bound readiness latency even when DNS resolution or a DB socket stalls."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Lock

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.session import engine

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="db-readiness")
_lock = Lock()
_pending = None


def _database_ready():
    try:
        expected = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
        with engine.connect() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '2s'"))
            actual = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
        return actual == expected
    except SQLAlchemyError:
        return False


def database_ready():
    global _pending
    with _lock:
        # Reuse one pending probe: repeated outages cannot accumulate worker threads/jobs.
        if _pending is None or _pending.done():
            _pending = _executor.submit(_database_ready)
        probe = _pending
    try:
        return probe.result(timeout=2.5)
    except TimeoutError:
        return False
