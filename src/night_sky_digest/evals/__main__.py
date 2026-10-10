"""python -m night_sky_digest.evals {pool,judge,agree}"""

import argparse
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

POOL = EVAL_DIR / "pool.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(prog="night_sky_digest.evals")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pool", help="build eval/pool.jsonl from the three search modes")
    p_judge = sub.add_parser("judge", help="judge the pool with one Ollama model (resumable)")
    p_judge.add_argument("--model", required=True)
    p_agree = sub.add_parser("agree", help="agreement between two judges")
    p_agree.add_argument("model_a")
    p_agree.add_argument("model_b")
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


if __name__ == "__main__":
    main()
