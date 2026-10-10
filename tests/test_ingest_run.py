from datetime import date, timedelta
from pathlib import Path

import psycopg
import pytest

from night_sky_digest.ingest.oai import Response
from night_sky_digest.ingest.run import _windows, ingest
from tests.fakes import FakeClock, ScriptedServer, ok

FIXTURES = Path(__file__).parent / "fixtures" / "oai"
FIRST = (FIXTURES / "list_records_first.xml").read_bytes()
LAST = (FIXTURES / "list_records_last.xml").read_bytes()
NO_RECORDS = (FIXTURES / "no_records_match.xml").read_bytes()
TODAY = date(2026, 10, 10)


def checkpoint(conn: psycopg.Connection) -> date | None:
    row = conn.execute("SELECT harvested_through FROM harvest_state").fetchone()
    return row[0] if row else None


def last_run(conn: psycopg.Connection) -> tuple:
    row = conn.execute(
        "SELECT status, pages, inserted, from_date, until_date FROM harvest_runs ORDER BY id DESC"
    ).fetchone()
    assert row is not None
    return row


def test_windows_cover_the_range_exactly() -> None:
    ws = list(_windows(date(2026, 1, 1), date(2026, 3, 15), 31))
    assert ws[0][0] == date(2026, 1, 1) and ws[-1][1] == date(2026, 3, 15)
    assert all(b[0] == a[1] + timedelta(days=1) for a, b in zip(ws, ws[1:], strict=False))


def test_first_run_needs_backfill_from(conn: psycopg.Connection) -> None:
    clock = FakeClock()
    with pytest.raises(ValueError):
        ingest(conn, ScriptedServer(clock, []), clock, today=TODAY)


def test_backfill_stores_pages_and_sets_checkpoint(conn: psycopg.Connection) -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(FIRST), ok(LAST)])
    result = ingest(conn, server, clock, today=TODAY, backfill_from=date(2026, 10, 1))
    assert result.pages == 2 and result.stats.inserted == 4
    assert checkpoint(conn) == date(2026, 10, 9)  # through yesterday
    assert last_run(conn) == ("success", 2, 4, date(2026, 10, 1), date(2026, 10, 9))


def test_next_run_starts_on_the_checkpoint_day(conn: psycopg.Connection) -> None:
    clock = FakeClock()
    ingest(
        conn, ScriptedServer(clock, [ok(LAST)]), clock, today=TODAY, backfill_from=date(2026, 10, 1)
    )
    server = ScriptedServer(clock, [ok(NO_RECORDS)])
    ingest(conn, server, clock, today=TODAY + timedelta(days=1))
    assert server.calls[0][1]["from"] == "2026-10-09"  # overlap of one day, on purpose
    assert checkpoint(conn) == date(2026, 10, 10)


def test_windows_are_politely_spaced(conn: psycopg.Connection) -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(NO_RECORDS)] * 3)
    ingest(conn, server, clock, today=TODAY, backfill_from=date(2026, 8, 1))  # 3 windows
    starts = [t for t, _ in server.calls]
    assert len(starts) == 3
    assert all(b - a >= 3.0 for a, b in zip(starts, starts[1:], strict=False))


def test_crash_keeps_stored_pages_and_old_checkpoint(conn: psycopg.Connection) -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(FIRST), Response(500, b"", {})])
    with pytest.raises(Exception):  # noqa: B017
        ingest(conn, server, clock, today=TODAY, backfill_from=date(2026, 10, 1))
    assert conn.execute("SELECT count(*) FROM papers").fetchone() == (3,)  # page 1 kept
    assert checkpoint(conn) is None  # window not finished, so no checkpoint
    assert last_run(conn)[0] == "failed"
