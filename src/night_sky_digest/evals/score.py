"""Score each search mode against the final labels."""

from collections import defaultdict
from statistics import mean

import psycopg

from night_sky_digest.embed import Embedder
from night_sky_digest.evals.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from night_sky_digest.evals.pool import MODES
from night_sky_digest.evals.queries import Query
from night_sky_digest.search import search

RELEVANT_FROM = 1  # grade >= 1 counts as relevant for recall and MRR


def score(
    conn: psycopg.Connection,
    embedder: Embedder,
    queries: list[Query],
    qrels: list[dict],
    k: int = 10,
) -> dict:
    """Per-query metrics for every mode, then means overall, by kind and by subfield."""
    grades: dict[str, dict[str, int]] = defaultdict(dict)
    for r in qrels:
        grades[r["query_id"]][r["arxiv_id"]] = r["grade"]

    per_query = []
    for mode in MODES:
        for q in queries:
            g = grades[q.id]
            relevant = {a for a, grade in g.items() if grade >= RELEVANT_FROM}
            if not relevant:
                continue
            ranked = [h.arxiv_id for h in search(conn, embedder, q.query, k=k, mode=mode)]
            per_query.append(
                {
                    "mode": mode,
                    "query_id": q.id,
                    "kind": q.kind,
                    "subfield": q.subfield,
                    f"recall@{k}": recall_at_k(ranked, relevant, k),
                    f"ndcg@{k}": ndcg_at_k(ranked, g, k),
                    "rr": reciprocal_rank(ranked, relevant),
                }
            )

    metrics = (f"recall@{k}", f"ndcg@{k}", "rr")

    def summarise(rows: list[dict]) -> dict:
        return {m: round(mean(r[m] for r in rows), 3) for m in metrics} | {"n": len(rows)}

    summary: dict = {"overall": {}, "by_kind": defaultdict(dict), "by_subfield": defaultdict(dict)}
    for mode in MODES:
        rows = [r for r in per_query if r["mode"] == mode]
        summary["overall"][mode] = summarise(rows)
        for group in ("kind", "subfield"):
            for value in sorted({r[group] for r in rows}):
                summary[f"by_{group}"][value][mode] = summarise(
                    [r for r in rows if r[group] == value]
                )
    return {"k": k, "summary": summary, "per_query": per_query}
