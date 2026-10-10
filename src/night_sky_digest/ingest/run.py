"""One ingest run: work out the date range, harvest it in windows, store, checkpoint."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta

import psycopg

from night_sky_digest.ingest.oai import ASTRO_PH, MIN_INTERVAL_S, Clock, Fetch, harvest
from night_sky_digest.ingest.store import StoreStats, store_page

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    from_date: date | None
    until_date: date
    pages: int = 0
    stats: StoreStats = field(default_factory=StoreStats)


def ingest(
    conn: psycopg.Connection,
    fetch: Fetch,
    clock: Clock,
    *,
    today: date,
    backfill_from: date | None = None,
    until: date | None = None,
    set_spec: str = ASTRO_PH,
    window_days: int = 31,
) -> RunResult:
    """Harvest everything new since the checkpoint, through yesterday by default.

    Resumable: the checkpoint (harvest_state.harvested_through) only advances when a whole
    window is stored, because OAI-PMH pages aren't ordered by date. A crash mid-window
    repeats that window on the next run, which is harmless because store_page is idempotent.
    The next run also starts *on* the checkpoint day, not after it, for the same reason:
    records for that day may have arrived after it was harvested.
    """
    until = until or today - timedelta(days=1)  # today's datestamps can still change
    checkpoint = _harvested_through(conn, set_spec)
    if checkpoint is not None:
        if backfill_from is not None:
            log.warning(
                "checkpoint %s exists, ignoring backfill_from %s", checkpoint, backfill_from
            )
        from_ = checkpoint
    elif backfill_from is not None:
        from_ = backfill_from
    else:
        raise ValueError(f"no checkpoint for {set_spec}: the first run needs backfill_from")

    result = RunResult(from_date=from_, until_date=until)
    if from_ > until:
        log.info("nothing to harvest: %s is after %s", from_, until)
        return result

    run_id = _start_run(conn, set_spec, from_, until)
    try:
        for i, (w_from, w_until) in enumerate(_windows(from_, until, window_days)):
            if i > 0:
                # harvest() spaces requests within a window; this keeps the gap between
                # windows polite too (the previous request ended before we got here).
                clock.sleep(MIN_INTERVAL_S)
            for page in harvest(fetch, clock, from_=w_from, until=w_until, set_spec=set_spec):
                result.stats += store_page(conn, page.records)
                result.pages += 1
                conn.commit()
                log.info("window %s..%s page %d: %s", w_from, w_until, result.pages, result.stats)
            _set_harvested_through(conn, set_spec, w_until)
            conn.commit()
        _finish_run(conn, run_id, "success", result)
        conn.commit()
    except BaseException as exc:
        conn.rollback()
        _finish_run(conn, run_id, "failed", result, error=repr(exc))
        conn.commit()
        raise
    return result


def _windows(start: date, end: date, days: int) -> Iterator[tuple[date, date]]:
    """Inclusive [from, until] date ranges of at most `days` days covering start..end."""
    while start <= end:
        stop = min(start + timedelta(days=days - 1), end)
        yield start, stop
        start = stop + timedelta(days=1)


def _harvested_through(conn: psycopg.Connection, set_spec: str) -> date | None:
    row = conn.execute(
        "SELECT harvested_through FROM harvest_state WHERE set_spec = %s", (set_spec,)
    ).fetchone()
    return row[0] if row else None


def _set_harvested_through(conn: psycopg.Connection, set_spec: str, day: date) -> None:
    conn.execute(
        """
        INSERT INTO harvest_state (set_spec, harvested_through) VALUES (%s, %s)
        ON CONFLICT (set_spec) DO UPDATE
            SET harvested_through = GREATEST(harvest_state.harvested_through,
                                             EXCLUDED.harvested_through),
                updated_at = now()
        """,
        (set_spec, day),
    )


def _start_run(conn: psycopg.Connection, set_spec: str, from_: date, until: date) -> int:
    row = conn.execute(
        "INSERT INTO harvest_runs (set_spec, from_date, until_date)"
        " VALUES (%s, %s, %s) RETURNING id",
        (set_spec, from_, until),
    ).fetchone()
    conn.commit()
    if row is None:
        raise RuntimeError("INSERT ... RETURNING returned no row")
    return row[0]


def _finish_run(
    conn: psycopg.Connection, run_id: int, status: str, r: RunResult, error: str | None = None
) -> None:
    conn.execute(
        """
        UPDATE harvest_runs
           SET finished_at = now(), status = %s, pages = %s, inserted = %s, updated = %s,
               unchanged = %s, deleted = %s, error = %s
         WHERE id = %s
        """,
        (
            status,
            r.pages,
            r.stats.inserted,
            r.stats.updated,
            r.stats.unchanged,
            r.stats.deleted,
            error,
            run_id,
        ),
    )
