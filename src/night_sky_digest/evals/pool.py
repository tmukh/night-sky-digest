"""Pooling: the papers worth judging for each query are the union of what each search mode
returns in its top `depth`. Judging only this pool (TREC-style) keeps labelling affordable while
still covering anything any method would show a user."""

import psycopg

from night_sky_digest.embed import Embedder
from night_sky_digest.evals.queries import Query
from night_sky_digest.search import search

MODES = ("lexical", "semantic", "hybrid")
POOL_DEPTH = 20


def build_pool(
    conn: psycopg.Connection, embedder: Embedder, queries: list[Query], depth: int = POOL_DEPTH
) -> list[dict]:
    rows: list[dict] = []
    for q in queries:
        ranks: dict[str, dict[str, int]] = {}
        for mode in MODES:
            for rank, hit in enumerate(search(conn, embedder, q.query, k=depth, mode=mode), 1):
                ranks.setdefault(hit.arxiv_id, {})[mode] = rank
        for arxiv_id in sorted(ranks):
            rows.append(
                {
                    "query_id": q.id,
                    "arxiv_id": arxiv_id,
                    **{f"{mode}_rank": ranks[arxiv_id].get(mode) for mode in MODES},
                }
            )
    return rows
