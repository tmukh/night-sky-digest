from dataclasses import replace
from datetime import date

import psycopg

from night_sky_digest.db import migrate
from night_sky_digest.ingest.oai import Deleted, Paper
from night_sky_digest.ingest.store import store_page


def paper(arxiv_id: str = "2410.00001", datestamp: date = date(2026, 10, 8), **kw: object) -> Paper:
    fields: dict = dict(
        arxiv_id=arxiv_id,
        title="Fast radio burst localisation",
        abstract="We localise an FRB.",
        authors=["A. Astronomer"],
        categories=["astro-ph.HE", "astro-ph.CO"],
        created=date(2026, 10, 1),
        updated=None,
        datestamp=datestamp,
        license=None,
        doi=None,
        comments=None,
    )
    fields.update(kw)
    return Paper(**fields)


def fetch_paper(conn: psycopg.Connection, arxiv_id: str) -> tuple:
    row = conn.execute(
        "SELECT title, datestamp, deleted, modified_at FROM papers WHERE arxiv_id = %s",
        (arxiv_id,),
    ).fetchone()
    assert row is not None
    return row


def test_migrate_is_idempotent(conn: psycopg.Connection) -> None:
    assert migrate(conn) == []  # the fixture already applied everything


def test_insert_then_same_page_again_changes_nothing(conn: psycopg.Connection) -> None:
    page = [paper("2410.00001"), paper("2410.00002")]
    first = store_page(conn, page)
    before = fetch_paper(conn, "2410.00001")
    again = store_page(conn, page)
    assert (first.inserted, first.updated) == (2, 0)
    assert (again.inserted, again.updated, again.unchanged) == (0, 0, 2)
    assert fetch_paper(conn, "2410.00001") == before  # not even modified_at moved


def test_newer_datestamp_updates(conn: psycopg.Connection) -> None:
    store_page(conn, [paper()])
    stats = store_page(conn, [paper(title="Revised title", datestamp=date(2026, 10, 9))])
    assert stats.updated == 1
    assert fetch_paper(conn, "2410.00001")[:2] == ("Revised title", date(2026, 10, 9))


def test_older_datestamp_never_overwrites(conn: psycopg.Connection) -> None:
    store_page(conn, [paper(title="Current", datestamp=date(2026, 10, 9))])
    stats = store_page(conn, [paper(title="Stale", datestamp=date(2026, 10, 1))])
    assert stats.unchanged == 1
    assert fetch_paper(conn, "2410.00001")[0] == "Current"


def test_same_day_correction_updates(conn: psycopg.Connection) -> None:
    p = paper()
    store_page(conn, [p])
    stats = store_page(conn, [replace(p, abstract="Corrected abstract.")])
    assert stats.updated == 1


def test_deletion_flags_existing_row(conn: psycopg.Connection) -> None:
    store_page(conn, [paper()])
    stats = store_page(
        conn, [Deleted("2410.00001", date(2026, 10, 9)), Deleted("9999.99999", date(2026, 10, 9))]
    )
    assert stats.deleted == 1  # unknown IDs are ignored
    assert fetch_paper(conn, "2410.00001")[2] is True
