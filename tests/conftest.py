"""Database fixtures. DB tests run against a dedicated *_test database, never the real one.

URL: TEST_DATABASE_URL if set (CI), otherwise DATABASE_URL from .env with the database name
swapped for night_sky_test (local development against the cluster). No URL: DB tests skip.
"""

import os
from collections.abc import Iterator

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from night_sky_digest.db import migrate

TEST_DB = "night_sky_test"


def _test_url() -> str | None:
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    load_dotenv()
    base = os.environ.get("DATABASE_URL")
    if not base:
        return None
    with psycopg.connect(base, autocommit=True) as admin:  # CREATE DATABASE can't run in a tx
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
        if exists.fetchone() is None:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))
    return make_conninfo(base, dbname=TEST_DB)


@pytest.fixture(scope="session")
def db_url() -> str:
    url = _test_url()
    if url is None:
        pytest.skip("no TEST_DATABASE_URL or DATABASE_URL")
    dbname = conninfo_to_dict(url).get("dbname", "")
    assert str(dbname).endswith("_test"), f"refusing to wipe non-test database {dbname!r}"
    return url


@pytest.fixture
def conn(db_url: str) -> Iterator[psycopg.Connection]:
    """A freshly migrated, empty schema for every test."""
    with psycopg.connect(db_url) as c:
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
        c.commit()
        migrate(c)
        yield c
