"""Database fixtures. DB tests run against a dedicated *_test database, never the real one.

URL: TEST_DATABASE_URL if set (CI), otherwise DATABASE_URL from .env with the database name
swapped for night_sky_test (local development against the cluster). No URL: DB tests skip.
"""

from collections.abc import Iterator

import psycopg
import pytest
from dotenv import load_dotenv

from night_sky_digest.db import reset_test_schema, test_database_url


@pytest.fixture(scope="session")
def db_url() -> str:
    load_dotenv()
    url = test_database_url()
    if url is None:
        pytest.skip("no TEST_DATABASE_URL or DATABASE_URL")
    return url


@pytest.fixture
def conn(db_url: str) -> Iterator[psycopg.Connection]:
    """A freshly migrated, empty schema for every test."""
    with psycopg.connect(db_url) as c:
        reset_test_schema(c)
        yield c
