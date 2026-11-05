import os

from peewee import SqliteDatabase

db = SqliteDatabase(None)


def init_db(models):
    db.init(os.getenv("EDGE_DATABASE_PATH", "storepulse_edge.db"), pragmas={"journal_mode": "wal"})
    with db.connection_context():
        db.create_tables(models, safe=True)
