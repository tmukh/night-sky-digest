"""Final relevance labels (qrels) from two judges plus a tie-breaker, and an audit sample."""

import random
from pathlib import Path
from statistics import median

import psycopg
import yaml

from night_sky_digest.evals.jsonl import read_jsonl
from night_sky_digest.evals.judge import OllamaJudge, judge_pool
from night_sky_digest.evals.queries import Query

Key = tuple[str, str]


def _by_key(path: Path) -> dict[Key, dict]:
    return {(j["query_id"], j["arxiv_id"]): j for j in read_jsonl(path)}


def resolve(
    conn: psycopg.Connection,
    queries: list[Query],
    pool: list[dict],
    path_a: Path,
    path_b: Path,
    tiebreaker: OllamaJudge,
    path_c: Path,
) -> list[dict]:
    """Where judges A and B give the same grade, that's the label. Where they differ, judge C
    grades the pair too and the label is the median of the three: two agreeing judges win, and
    a 0/1/2 split becomes 1."""
    a, b = _by_key(path_a), _by_key(path_b)
    disputed = [p for p in pool if a[_key(p)]["grade"] != b[_key(p)]["grade"]]
    judge_pool(conn, tiebreaker, queries, disputed, path_c)
    c = _by_key(path_c)
    qrels = []
    for p in pool:
        k = _key(p)
        ga, gb = a[k]["grade"], b[k]["grade"]
        if ga == gb:
            qrels.append({"query_id": k[0], "arxiv_id": k[1], "grade": ga, "source": "agreed"})
        else:
            grade = int(median([ga, gb, c[k]["grade"]]))
            qrels.append({"query_id": k[0], "arxiv_id": k[1], "grade": grade, "source": "tiebreak"})
    return qrels


def audit_sample(
    conn: psycopg.Connection,
    queries: list[Query],
    qrels: list[dict],
    judgment_paths: list[Path],
    n: int = 30,
    seed: int = 20261011,
) -> list[dict]:
    """A fixed random sample of final labels for a human to check. The share the human disagrees
    with estimates the error rate of all labels."""
    sample = random.Random(seed).sample(qrels, n)  # noqa: S311 - sampling, not security
    by_id = {q.id: q for q in queries}
    judges = {p.stem: _by_key(p) for p in judgment_paths}
    papers = {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            "SELECT arxiv_id, title, abstract FROM papers WHERE arxiv_id = ANY(%s)",
            ([s["arxiv_id"] for s in sample],),
        )
    }
    items = []
    for s in sample:
        k = (s["query_id"], s["arxiv_id"])
        q = by_id[s["query_id"]]
        title, abstract = papers[s["arxiv_id"]]
        items.append(
            {
                "query_id": q.id,
                "query": q.query,
                "intent": q.intent.strip(),
                "arxiv_id": s["arxiv_id"],
                "url": f"https://arxiv.org/abs/{s['arxiv_id']}",
                "title": title,
                "abstract": abstract,
                "judges": {
                    name: {"grade": j[k]["grade"], "reason": j[k]["reason"]}
                    for name, j in judges.items()
                    if k in j
                },
                "final_grade": s["grade"],
                "your_grade": None,
            }
        )
    return items


def write_audit(path: Path, items: list[dict]) -> None:
    header = (
        "# Audit: for each item, read the intent, title and abstract, then set your_grade to\n"
        "# 2 (relevant), 1 (partly relevant) or 0 (not relevant). The judges' reasons may help.\n"
    )
    path.write_text(
        header + yaml.safe_dump(items, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
        newline="\n",
    )


def _key(p: dict) -> Key:
    return (p["query_id"], p["arxiv_id"])
