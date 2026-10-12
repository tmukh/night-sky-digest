"""Embeddings: bge-m3 via Ollama on the Windows PC's GPU (ADR 0002), and the job that keeps
paper_embeddings in sync with papers."""

import logging
import os
from typing import Protocol

import httpx
import psycopg

log = logging.getLogger(__name__)

MODEL = "bge-m3"
DIM = 1024


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    def __init__(self, url: str | None = None, model: str = MODEL, timeout_s: float = 120.0):
        self.model = model
        self._url = (url or os.environ.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self._client = httpx.Client(timeout=timeout_s)
        self._keep_alive = os.environ.get("OLLAMA_EMBED_KEEP_ALIVE", "1h")

    def embed(self, texts: list[str]) -> list[list[float]]:
        r = self._client.post(
            f"{self._url}/api/embed",
            # Ollama unloads idle models after 5 min; reloading bge-m3 takes ~5 s, which would
            # make most searches on a low-traffic site miss the 800 ms latency SLO.
            json={"model": self.model, "input": texts, "keep_alive": self._keep_alive},
        )
        r.raise_for_status()
        vectors = r.json()["embeddings"]
        if len(vectors) != len(texts) or any(len(v) != DIM for v in vectors):
            raise ValueError(f"expected {len(texts)} vectors of {DIM} dims from {self.model}")
        return vectors

    def close(self) -> None:
        self._client.close()


def document_text(title: str, abstract: str) -> str:
    return f"{title}\n\n{abstract}"


def to_pgvector(v: list[float]) -> str:
    """pgvector's text format; cast with ::vector in SQL."""
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


# Papers with no embedding, an embedding from another model, or a change since embedding.
_PENDING = """
SELECT p.arxiv_id, p.title, p.abstract
  FROM papers p
  LEFT JOIN paper_embeddings e USING (arxiv_id)
 WHERE NOT p.deleted
   AND (e.arxiv_id IS NULL OR e.model <> %(model)s OR e.embedded_at < p.modified_at)
 ORDER BY p.arxiv_id
 LIMIT %(limit)s
"""

_UPSERT = """
INSERT INTO paper_embeddings (arxiv_id, model, embedding)
VALUES (%(arxiv_id)s, %(model)s, %(embedding)s::vector)
ON CONFLICT (arxiv_id) DO UPDATE
   SET model = EXCLUDED.model, embedding = EXCLUDED.embedding, embedded_at = now()
"""


def embed_pending(conn: psycopg.Connection, embedder: Embedder, batch_size: int = 64) -> int:
    """Embed everything that needs it, one committed batch at a time. Safe to interrupt."""
    done = 0
    while True:
        rows = conn.execute(_PENDING, {"model": embedder.model, "limit": batch_size}).fetchall()
        if not rows:
            return done
        vectors = embedder.embed([document_text(title, abstract) for _, title, abstract in rows])
        with conn.cursor() as cur:
            cur.executemany(
                _UPSERT,
                [
                    {"arxiv_id": arxiv_id, "model": embedder.model, "embedding": to_pgvector(v)}
                    for (arxiv_id, _, _), v in zip(rows, vectors, strict=True)
                ],
            )
        conn.commit()
        done += len(rows)
        if done % (batch_size * 20) < batch_size:
            log.info("embedded %d papers", done)
