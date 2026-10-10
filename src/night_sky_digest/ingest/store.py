"""Write harvested records to Postgres, idempotently."""

from dataclasses import dataclass

import psycopg

from night_sky_digest.ingest.oai import Deleted, Paper

# Insert new papers; update existing ones only if arXiv's copy is newer, or the same day's copy
# actually differs. Re-running a harvest therefore changes nothing (idempotent), an older
# window can never overwrite newer data, and modified_at only moves on real changes, which
# M2 uses to re-embed just the papers that changed.
_UPSERT = """
INSERT INTO papers AS p (
    arxiv_id, title, abstract, authors, categories, primary_category,
    created, updated, datestamp, license, doi, comments
) VALUES (
    %(arxiv_id)s, %(title)s, %(abstract)s, %(authors)s, %(categories)s, %(primary_category)s,
    %(created)s, %(updated)s, %(datestamp)s, %(license)s, %(doi)s, %(comments)s
)
ON CONFLICT (arxiv_id) DO UPDATE SET
    title = EXCLUDED.title,
    abstract = EXCLUDED.abstract,
    authors = EXCLUDED.authors,
    categories = EXCLUDED.categories,
    primary_category = EXCLUDED.primary_category,
    created = EXCLUDED.created,
    updated = EXCLUDED.updated,
    datestamp = EXCLUDED.datestamp,
    license = EXCLUDED.license,
    doi = EXCLUDED.doi,
    comments = EXCLUDED.comments,
    deleted = false,
    modified_at = now()
WHERE EXCLUDED.datestamp > p.datestamp
   OR (EXCLUDED.datestamp = p.datestamp
       AND (p.title, p.abstract, p.authors, p.categories, p.updated,
            p.license, p.doi, p.comments, p.deleted)
           IS DISTINCT FROM
           (EXCLUDED.title, EXCLUDED.abstract, EXCLUDED.authors, EXCLUDED.categories,
            EXCLUDED.updated, EXCLUDED.license, EXCLUDED.doi, EXCLUDED.comments, false))
RETURNING (xmax = 0) AS inserted  -- xmax is 0 for a freshly inserted row version
"""

# A deletion marker only knows the ID. Keep the row (search can filter it), flag it.
_MARK_DELETED = """
UPDATE papers
   SET deleted = true, datestamp = %(datestamp)s, modified_at = now()
 WHERE arxiv_id = %(arxiv_id)s AND NOT deleted AND datestamp <= %(datestamp)s
"""


@dataclass
class StoreStats:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0

    def __iadd__(self, other: "StoreStats") -> "StoreStats":
        self.inserted += other.inserted
        self.updated += other.updated
        self.unchanged += other.unchanged
        self.deleted += other.deleted
        return self


def store_page(conn: psycopg.Connection, records: list[Paper | Deleted]) -> StoreStats:
    """Upsert one page. Does not commit; the caller decides the transaction boundary."""
    papers = [r for r in records if isinstance(r, Paper)]
    deletions = [r for r in records if isinstance(r, Deleted)]
    stats = StoreStats()

    with conn.cursor() as cur:
        if papers:
            cur.executemany(_UPSERT, [_row(p) for p in papers], returning=True)
            # One result set per paper: a row if inserted/updated, empty if unchanged.
            while True:
                row = cur.fetchone()
                if row is not None:
                    if row[0]:
                        stats.inserted += 1
                    else:
                        stats.updated += 1
                if not cur.nextset():
                    break
            stats.unchanged = len(papers) - stats.inserted - stats.updated
        if deletions:
            cur.executemany(
                _MARK_DELETED,
                [{"arxiv_id": d.arxiv_id, "datestamp": d.datestamp} for d in deletions],
            )
            stats.deleted = cur.rowcount
    return stats


def _row(p: Paper) -> dict[str, object]:
    return {
        "arxiv_id": p.arxiv_id,
        "title": p.title,
        "abstract": p.abstract,
        "authors": p.authors,
        "categories": p.categories,
        "primary_category": p.primary_category,
        "created": p.created,
        "updated": p.updated,
        "datestamp": p.datestamp,
        "license": p.license,
        "doi": p.doi,
        "comments": p.comments,
    }
