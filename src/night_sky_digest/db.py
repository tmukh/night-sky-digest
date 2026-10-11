"""Database connection and schema migrations.

Migrations are numbered SQL files in night_sky_digest/migrations, applied in order and recorded
in schema_migrations, like Flyway. Postgres DDL is transactional, so a failing migration rolls
back completely (unlike Oracle, where DDL commits implicitly).
"""

import logging
import os
from importlib.resources import files

import psycopg

log = logging.getLogger(__name__)

# Arbitrary constant: concurrent migrate() calls (two pods starting at once) queue on this lock.
_MIGRATION_LOCK_ID = 7_202_610


def connect(url: str | None = None) -> psycopg.Connection:
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(url)


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations in one transaction. Returns the versions applied."""
    scripts = sorted(
        (f for f in files("night_sky_digest.migrations").iterdir() if f.name.endswith(".sql")),
        key=lambda f: f.name,
    )
    applied_now: list[str] = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK_ID,))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for script in scripts:
            version = script.name.removesuffix(".sql")
            if version in done:
                continue
            log.info("applying migration %s", version)
            conn.execute(script.read_text(encoding="utf-8"))  # type: ignore[arg-type]
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            applied_now.append(version)
    return applied_now


TEST_DB = "night_sky_test"


def test_database_url() -> str | None:
    """URL of the throwaway test database: TEST_DATABASE_URL (CI), otherwise DATABASE_URL with the
    database name swapped for night_sky_test, created if missing. None if neither is set."""
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    base = os.environ.get("DATABASE_URL")
    if not base:
        return None
    with psycopg.connect(base, autocommit=True) as admin:  # CREATE DATABASE can't run in a tx
        if (
            admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)).fetchone()
            is None
        ):
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))
    return make_conninfo(base, dbname=TEST_DB)


def reset_test_schema(conn: psycopg.Connection) -> None:
    """Drop everything and re-run migrations. Refuses to touch a database not named *_test."""
    dbname = conn.info.dbname
    if not dbname.endswith("_test"):
        raise RuntimeError(f"refusing to wipe non-test database {dbname!r}")
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")
    conn.commit()
    migrate(conn)
