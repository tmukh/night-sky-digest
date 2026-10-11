"""Frozen eval snapshot for CI, and the regression gate that runs on it.

CI can't reach the cluster database or the GPU. So the snapshot holds everything search needs:
the pooled papers plus random distractors (so the search isn't trivially easy), their bge-m3
embeddings, and the embeddings of the eval queries. The gate loads it into the CI Postgres,
scores it, and compares against eval/baseline.json.
"""

import gzip
import json
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import psycopg

from night_sky_digest.db import reset_test_schema
from night_sky_digest.embed import Embedder, to_pgvector
from night_sky_digest.evals.queries import Query
from night_sky_digest.evals.score import score
from night_sky_digest.ingest.oai import Paper
from night_sky_digest.ingest.store import store_page

GATED_MODE = "hybrid"
GATED_METRICS = ("recall@10", "ndcg@10")
TOLERANCE = 0.02  # fail when a gated metric drops more than 2 points

_PAPER_FIELDS = (
    "arxiv_id, title, abstract, authors, categories, created, updated, datestamp, "
    "license, doi, comments"
)


def export_snapshot(
    conn: psycopg.Connection,
    embedder: Embedder,
    queries: list[Query],
    pool: list[dict],
    out_dir: Path,
    distractors: int = 2000,
    seed: str = "night-sky-2026",
) -> dict:
    pooled = sorted({p["arxiv_id"] for p in pool})
    # Deterministic "random" sample: order by a hash of the ID, so re-exports pick the same papers.
    extra = [
        r[0]
        for r in conn.execute(
            "SELECT arxiv_id FROM papers WHERE NOT deleted AND arxiv_id <> ALL(%s)"
            " ORDER BY md5(arxiv_id || %s) LIMIT %s",
            (pooled, seed, distractors),
        )
    ]
    rows = conn.execute(
        "SELECT arxiv_id, title, abstract, authors, categories, created, updated, datestamp,"
        " license, doi, comments, e.embedding::text"
        " FROM papers p JOIN paper_embeddings e USING (arxiv_id)"
        " WHERE arxiv_id = ANY(%s) AND e.model = %s ORDER BY arxiv_id",
        (pooled + extra, embedder.model),
    ).fetchall()

    out_dir.mkdir(parents=True, exist_ok=True)
    keys = [k.strip() for k in _PAPER_FIELDS.split(",")]
    with gzip.open(out_dir / "papers.jsonl.gz", "wt", encoding="utf-8", newline="\n") as f:
        for r in rows:
            paper = dict(zip(keys, r[:-1], strict=True))
            for d in ("created", "updated", "datestamp"):
                paper[d] = paper[d].isoformat() if paper[d] else None
            f.write(json.dumps(paper, ensure_ascii=False) + "\n")

    query_vecs = embedder.embed([q.query for q in queries])
    np.savez_compressed(
        out_dir / "vectors.npz",
        paper_ids=np.array([r[0] for r in rows]),
        paper_vecs=np.array([json.loads(r[-1]) for r in rows], dtype=np.float16),
        queries=np.array([q.query for q in queries]),
        query_vecs=np.array(query_vecs, dtype=np.float16),
    )
    manifest = {
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": embedder.model,
        "papers": len(rows),
        "pooled": len(pooled),
        "distractors": len(extra),
        "queries": len(queries),
        "seed": seed,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


class SnapshotEmbedder:
    """Answers query embeddings from the snapshot instead of calling Ollama."""

    def __init__(self, model: str, vectors: dict[str, list[float]]) -> None:
        self.model = model
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in texts if t not in self._vectors]
        if missing:
            raise KeyError(f"not in the snapshot, re-run `evals snapshot`: {missing[:3]}")
        return [self._vectors[t] for t in texts]


def load_snapshot(conn: psycopg.Connection, snap_dir: Path) -> SnapshotEmbedder:
    manifest = json.loads((snap_dir / "manifest.json").read_text(encoding="utf-8"))
    with gzip.open(snap_dir / "papers.jsonl.gz", "rt", encoding="utf-8") as f:
        papers = []
        for line in f:
            p = json.loads(line)
            for d in ("created", "updated", "datestamp"):
                p[d] = date.fromisoformat(p[d]) if p[d] else None
            papers.append(Paper(**p))
    store_page(conn, papers)
    v = np.load(snap_dir / "vectors.npz")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO paper_embeddings (arxiv_id, model, embedding) VALUES (%s, %s, %s::vector)",
            [
                (str(i), manifest["model"], to_pgvector(vec.astype(float).tolist()))
                for i, vec in zip(v["paper_ids"], v["paper_vecs"], strict=True)
            ],
        )
    conn.commit()
    return SnapshotEmbedder(
        manifest["model"],
        {
            str(q): vec.astype(float).tolist()
            for q, vec in zip(v["queries"], v["query_vecs"], strict=True)
        },
    )


def run_gate(
    conn: psycopg.Connection,
    snap_dir: Path,
    queries: list[Query],
    qrels: list[dict],
    baseline_path: Path,
    update: bool = False,
) -> tuple[bool, dict, dict | None]:
    """Score the snapshot. Returns (passed, current overall scores, baseline overall scores)."""
    reset_test_schema(conn)
    embedder = load_snapshot(conn, snap_dir)
    current = score(conn, embedder, queries, qrels)["summary"]["overall"]
    if update or not baseline_path.exists():
        baseline_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        return True, current, None
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    passed = all(
        current[GATED_MODE][m] >= baseline[GATED_MODE][m] - TOLERANCE for m in GATED_METRICS
    )
    return passed, current, baseline
