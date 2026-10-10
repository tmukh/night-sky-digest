"""LLM relevance judging with local Ollama models: graded 0/1/2 plus a one-sentence reason."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import psycopg

from night_sky_digest.evals.jsonl import append_jsonl, read_jsonl
from night_sky_digest.evals.queries import Query

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert astrophysicist judging search results for a search engine evaluation.
You get a search query, the searcher's intent, and one paper (title and abstract).
Grade how well the paper satisfies the intent:
2 = relevant: the paper's main topic directly addresses the intent.
1 = partly relevant: the paper addresses part of the intent, or treats it as a secondary topic.
0 = not relevant: off-topic, or a case the intent lists under "Not relevant".
Judge only from the title and abstract. Give a one-sentence reason first, then the grade."""

# Ollama constrains the output to this JSON schema. Reason before grade, so the model commits
# to an argument before it picks a number.
_SCHEMA = {
    "type": "object",
    "properties": {
        "reason": {"type": "string"},
        "grade": {"type": "integer", "enum": [0, 1, 2]},
    },
    "required": ["reason", "grade"],
}


@dataclass(frozen=True)
class Judgment:
    grade: int
    reason: str


class OllamaJudge:
    def __init__(self, model: str, url: str | None = None, timeout_s: float = 300.0) -> None:
        self.model = model
        self._url = (url or os.environ.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self._client = httpx.Client(timeout=timeout_s)

    def judge(self, query: Query, title: str, abstract: str) -> Judgment:
        user = (
            f"Query: {query.query}\n\nIntent: {query.intent.strip()}\n\n"
            f"Paper title: {title}\n\nPaper abstract: {abstract}"
        )
        r = self._client.post(
            f"{self._url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                "format": _SCHEMA,
                # Thinking models (gemma4) otherwise write hidden reasoning first: ~7x slower.
                "think": False,
                "stream": False,
                "options": {"temperature": 0, "num_ctx": 4096},
            },
        )
        r.raise_for_status()
        out = json.loads(r.json()["message"]["content"])
        if out.get("grade") not in (0, 1, 2):
            raise ValueError(f"{self.model} returned an invalid grade: {out!r}")
        return Judgment(grade=out["grade"], reason=str(out.get("reason", "")).strip())

    def close(self) -> None:
        self._client.close()


def judgments_path(model: str, eval_dir: Path = Path("eval")) -> Path:
    return eval_dir / "judgments" / f"{model.replace(':', '_').replace('/', '_')}.jsonl"


def judge_pool(
    conn: psycopg.Connection,
    judge: OllamaJudge,
    queries: list[Query],
    pool: list[dict],
    out: Path,
) -> int:
    """Judge every pooled pair not yet in `out`. Appends one line per judgment, so an interrupted
    run resumes where it stopped (same idea as the ingest checkpoint)."""
    done = {(j["query_id"], j["arxiv_id"]) for j in read_jsonl(out)}
    todo = [p for p in pool if (p["query_id"], p["arxiv_id"]) not in done]
    by_id = {q.id: q for q in queries}
    papers = {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            "SELECT arxiv_id, title, abstract FROM papers WHERE arxiv_id = ANY(%s)",
            ([p["arxiv_id"] for p in todo],),
        )
    }
    log.info("%s: %d judged already, %d to go", judge.model, len(done), len(todo))
    for i, p in enumerate(todo, 1):
        title, abstract = papers[p["arxiv_id"]]
        j = judge.judge(by_id[p["query_id"]], title, abstract)
        append_jsonl(
            out,
            {
                "query_id": p["query_id"],
                "arxiv_id": p["arxiv_id"],
                "grade": j.grade,
                "reason": j.reason,
                "model": judge.model,
            },
        )
        if i % 50 == 0:
            log.info("%s: %d/%d", judge.model, i, len(todo))
    return len(todo)
