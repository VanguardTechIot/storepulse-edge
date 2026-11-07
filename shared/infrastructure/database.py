import os

"""Shared database infrastructure of the StorePulse Edge API.

Provides the single :class:`peewee.SqliteDatabase` instance (``db``) that every
bounded context's ORM models bind to, so the Edge Device keeps all its local
data in one SQLite file and keeps working without internet (EP-09).

Note:
    ``db`` is declared unconfigured and :func:`configure_database` points it to
    the configured file before :func:`init_db` connects it. Peewee keeps one
    connection per thread; the Flask application closes it on teardown.
"""

from pathlib import Path

from peewee import SqliteDatabase

# Shared SQLite database used by the ORM models of every bounded context.
db = SqliteDatabase(None, timeout=30, pragmas={"busy_timeout": 30_000})


def configure_database(database_path: str) -> None:
    """Point the shared database to its file, creating the folder if needed.

    Args:
        database_path: Absolute path of the SQLite file.
    """
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db.init(str(path))


def init_db() -> None:
    """Open the database connection and create the missing tables.

    The ORM models are imported here to avoid import cycles. Calling it again
    is safe: existing tables are left untouched. Each bounded context adds its
    models to the list when it persists data.
    """
    if db.is_closed():
        db.connect()
    from iam.infrastructure.models import Device

    db.create_tables([Device], safe=True)
