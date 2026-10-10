"""python -m night_sky_digest.evals {pool,judge,agree,resolve,audit,score}"""

import argparse
import json
import logging
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from night_sky_digest.db import connect
from night_sky_digest.embed import OllamaEmbedder
from night_sky_digest.evals.agreement import cohen_kappa, confusion
from night_sky_digest.evals.jsonl import read_jsonl, write_jsonl
from night_sky_digest.evals.judge import OllamaJudge, judge_pool, judgments_path
from night_sky_digest.evals.pool import build_pool
from night_sky_digest.evals.queries import EVAL_DIR, load_queries
from night_sky_digest.evals.resolve import audit_sample, resolve, write_audit
from night_sky_digest.evals.score import score

POOL = EVAL_DIR / "pool.jsonl"
QRELS = EVAL_DIR / "qrels.jsonl"
JUDGES = ("qwen2.5:7b", "gemma4:12b")
TIEBREAKER = "llama3.1:8b"


def main() -> None:
    parser = argparse.ArgumentParser(prog="night_sky_digest.evals")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pool", help="build eval/pool.jsonl from the three search modes")
    p_judge = sub.add_parser("judge", help="judge the pool with one Ollama model (resumable)")
    p_judge.add_argument("--model", required=True)
    p_agree = sub.add_parser("agree", help="agreement between two judges")
    p_agree.add_argument("model_a")
    p_agree.add_argument("model_b")
    sub.add_parser("resolve", help=f"final labels: {JUDGES} plus {TIEBREAKER} where they differ")
    sub.add_parser("audit", help="write eval/audit.yaml, a random sample of labels to check")
    p_score = sub.add_parser("score", help="recall@k, nDCG@k, MRR per search mode")
    p_score.add_argument("-k", type=int, default=10)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_dotenv()
    queries = load_queries()

    if args.command == "pool":
        embedder = OllamaEmbedder()
        with connect() as conn:
            rows = build_pool(conn, embedder, queries)
        embedder.close()
        write_jsonl(POOL, rows)
        per_query = Counter(r["query_id"] for r in rows)
        logging.info(
            "pool: %d pairs for %d queries (min %d, max %d per query)",
            len(rows), len(per_query), min(per_query.values()), max(per_query.values()),
        )  # fmt: skip
    elif args.command == "judge":
        judge = OllamaJudge(args.model)
        with connect() as conn:
            n = judge_pool(conn, judge, queries, read_jsonl(POOL), judgments_path(args.model))
        judge.close()
        logging.info("judged %d new pairs with %s", n, args.model)
    elif args.command == "agree":
        report_agreement(judgments_path(args.model_a), judgments_path(args.model_b))
    elif args.command == "resolve":
        judge = OllamaJudge(TIEBREAKER)
        with connect() as conn:
            qrels = resolve(
                conn, queries, read_jsonl(POOL),
                judgments_path(JUDGES[0]), judgments_path(JUDGES[1]),
                judge, judgments_path(TIEBREAKER),
            )  # fmt: skip
        judge.close()
        write_jsonl(QRELS, qrels)
        logging.info(
            "qrels: %d labels, %s, grades %s",
            len(qrels),
            dict(Counter(r["source"] for r in qrels)),
            dict(sorted(Counter(r["grade"] for r in qrels).items())),
        )
    elif args.command == "audit":
        paths = [judgments_path(m) for m in (*JUDGES, TIEBREAKER)]
        with connect() as conn:
            items = audit_sample(conn, queries, read_jsonl(QRELS), paths)
        write_audit(EVAL_DIR / "audit.yaml", items)
        logging.info("wrote %d items to eval/audit.yaml", len(items))
    elif args.command == "score":
        embedder = OllamaEmbedder()
        with connect() as conn:
            result = score(conn, embedder, queries, read_jsonl(QRELS), k=args.k)
        embedder.close()
        (EVAL_DIR / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print_summary(result)


def report_agreement(path_a: Path, path_b: Path) -> None:
    a = {(j["query_id"], j["arxiv_id"]): j["grade"] for j in read_jsonl(path_a)}
    b = {(j["query_id"], j["arxiv_id"]): j["grade"] for j in read_jsonl(path_b)}
    keys = sorted(a.keys() & b.keys())
    ga, gb = [a[k] for k in keys], [b[k] for k in keys]
    agree = sum(x == y for x, y in zip(ga, gb, strict=True))
    print(f"pairs judged by both: {len(keys)}")
    print(f"exact agreement: {agree / len(keys):.1%}")
    print(f"Cohen's kappa: {cohen_kappa(ga, gb):.3f}   linear-weighted: "
          f"{cohen_kappa(ga, gb, 'linear'):.3f}")  # fmt: skip
    print(f"grade counts  {path_a.stem}: {dict(sorted(Counter(ga).items()))}  "
          f"{path_b.stem}: {dict(sorted(Counter(gb).items()))}")  # fmt: skip
    print(f"confusion (rows {path_a.stem}, columns {path_b.stem}):")
    m = confusion(ga, gb)
    for x in (0, 1, 2):
        print(f"  {x}: " + "  ".join(f"{m[(x, y)]:5d}" for y in (0, 1, 2)))


def print_summary(result: dict) -> None:
    k, summary = result["k"], result["summary"]
    cols = (f"recall@{k}", f"ndcg@{k}", "rr")
    sections = (
        ("overall", {"all": summary["overall"]}),
        ("by kind", summary["by_kind"]),
        ("by subfield", summary["by_subfield"]),
    )
    for section, rows in sections:
        print(f"\n{section}: recall@{k} / nDCG@{k} / MRR")
        for name, modes in rows.items():
            cells = "   ".join(
                f"{m}: " + " / ".join(f"{modes[m][c]:.2f}" for c in cols) for m in modes
            )
            print(f"  {name:<11} n={next(iter(modes.values()))['n']:<3} {cells}")


if __name__ == "__main__":
    main()
