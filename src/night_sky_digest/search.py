"""Hybrid search: Postgres full-text and pgvector nearest neighbours, merged with
reciprocal-rank fusion."""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Literal

import httpx
import psycopg

from night_sky_digest.embed import Embedder, to_pgvector
from night_sky_digest.metrics import SEARCH_DEGRADED

log = logging.getLogger(__name__)

Mode = Literal["hybrid", "lexical", "semantic"]

# HNSW looks at ef_search candidates per query; pgvector's default (40) would cap a LIMIT 50.
_EF_SEARCH = 100

_LEXICAL = """
SELECT arxiv_id
  FROM papers, websearch_to_tsquery('english', %(q)s) AS query
 WHERE search_tsv @@ query AND NOT deleted
 ORDER BY ts_rank_cd(search_tsv, query) DESC, arxiv_id
 LIMIT %(n)s
"""

_SEMANTIC = """
SELECT e.arxiv_id
  FROM paper_embeddings e
  JOIN papers p USING (arxiv_id)
 WHERE e.model = %(model)s AND NOT p.deleted
 ORDER BY e.embedding <=> %(v)s::vector
 LIMIT %(n)s
"""

_DETAILS = """
SELECT arxiv_id, title, authors, primary_category, created
  FROM papers
 WHERE arxiv_id = ANY(%(ids)s)
"""


@dataclass(frozen=True)
class Hit:
    arxiv_id: str
    title: str
    authors: list[str]
    primary_category: str
    created: date
    score: float
    lexical_rank: int | None  # 1-based position in the full-text list, None if absent
    semantic_rank: int | None

    @property
    def url(self) -> str:
        return f"https://arxiv.org/abs/{self.arxiv_id}"


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal-rank fusion: merge ranked lists of IDs into one ranking.

    Spec in tests/test_rrf.py.

    Each list is ordered best first. An ID at 1-based position r in a list earns 1 / (k + r)
    from that list; its fused score is the sum over all lists it appears in. Return
    (id, score) pairs sorted by score, highest first; break ties by ID so results are stable.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, arxiv_id in enumerate(ranking, start=1):
            scores[arxiv_id] = scores.get(arxiv_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def search(
    conn: psycopg.Connection,
    embedder: Embedder,
    query: str,
    *,
    k: int = 10,
    mode: Mode = "hybrid",
    candidates: int = 50,
) -> list[Hit]:
    lexical: list[str] = []
    semantic: list[str] = []
    with conn.transaction():
        if mode in ("hybrid", "lexical"):
            rows = conn.execute(_LEXICAL, {"q": query, "n": candidates}).fetchall()
            lexical = [r[0] for r in rows]
        if mode in ("hybrid", "semantic"):
            conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(_EF_SEARCH),))
            vector = to_pgvector(embedder.embed([query])[0])
            rows = conn.execute(
                _SEMANTIC, {"model": embedder.model, "v": vector, "n": candidates}
            ).fetchall()
            semantic = [r[0] for r in rows]

    fused = rrf([ranking for ranking in (lexical, semantic) if ranking])[:k]
    if not fused:
        return []
    ids = [arxiv_id for arxiv_id, _ in fused]
    details = {r[0]: r for r in conn.execute(_DETAILS, {"ids": ids}).fetchall()}
    lexical_pos = {a: i + 1 for i, a in enumerate(lexical)}
    semantic_pos = {a: i + 1 for i, a in enumerate(semantic)}
    return [
        Hit(
            arxiv_id=arxiv_id,
            title=details[arxiv_id][1],
            authors=details[arxiv_id][2],
            primary_category=details[arxiv_id][3],
            created=details[arxiv_id][4],
            score=score,
            lexical_rank=lexical_pos.get(arxiv_id),
            semantic_rank=semantic_pos.get(arxiv_id),
        )
        for arxiv_id, score in fused
    ]


@dataclass(frozen=True)
class SearchResult:
    hits: list[Hit]
    degraded: bool  # True: embedding failed, hits are lexical only


def search_for_user(
    conn: psycopg.Connection, embedder: Embedder, query: str, *, k: int = 10, mode: Mode = "hybrid"
) -> SearchResult:
    """search() for the public API: if the embedding service is down (Ollama runs on a PC that may
    be off, ADR 0002), hybrid search falls back to lexical results instead of failing. The eval
    keeps calling search() directly, so it fails loudly instead of scoring degraded results."""
    try:
        return SearchResult(search(conn, embedder, query, k=k, mode=mode), degraded=False)
    except (httpx.HTTPError, OSError) as exc:
        if mode != "hybrid":
            raise
        log.warning("embedding failed, falling back to lexical search: %r", exc)
        SEARCH_DEGRADED.inc()
        return SearchResult(search(conn, embedder, query, k=k, mode="lexical"), degraded=True)
