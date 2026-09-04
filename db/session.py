# db/session.py

"""
Engine/session setup for the Phase 9 supplier repository layer.

Kept intentionally simple: one function to build an engine from a
database URL, one to build a session factory from that engine. No
connection pooling config, no migrations tooling (Alembic) — this is
a small foundation layer, not a production database setup.

Default points at a local SQLite file so a demo run leaves behind
something inspectable. Tests override this with an in-memory database
instead (see tests/test_supplier_repository.py), so test runs never
touch this file.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///db/mock_supplier_data.db"


def get_engine(database_url: str = DEFAULT_DATABASE_URL):
    return create_engine(database_url, echo=False)


def get_session_factory(engine):
    return sessionmaker(bind=engine)