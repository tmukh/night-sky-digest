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
