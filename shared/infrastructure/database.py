"""Shared database infrastructure of the StorePulse Edge API.

Provides the single :class:`peewee.SqliteDatabase` instance (``db``) that every
bounded context's ORM models bind to, so the Edge Device keeps all its local
data in one SQLite file and keeps working without internet (EP-09).

Note:
    ``db`` is declared unconfigured: :func:`configure_database` points it to
    the configured file and :func:`init_db` creates the tables. Peewee keeps
    one connection per thread; the Flask application opens it before each
    request and closes it on teardown, and background threads use
    ``db.connection_context()``.
"""

from pathlib import Path

from peewee import Model, SqliteDatabase

# Shared SQLite database used by the ORM models of every bounded context.
# WAL lets the synchronization thread write while requests read.
db = SqliteDatabase(None, timeout=30, pragmas={"journal_mode": "wal", "busy_timeout": 30_000})


def configure_database(database_path: str) -> None:
    """Point the shared database to its file, creating the folder if needed.

    Args:
        database_path: Absolute path of the SQLite file.
    """
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db.init(str(path))


def init_db(models: list[type[Model]]) -> None:
    """Create the missing tables of the given ORM models.

    Calling it again is safe: existing tables are left untouched. The
    application factory passes the models of every bounded context.

    Args:
        models: ORM models to create, parents before the models that reference them.
    """
    with db.connection_context():
        db.create_tables(models, safe=True)
