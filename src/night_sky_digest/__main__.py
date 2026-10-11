"""Command line: python -m night_sky_digest {migrate,ingest,embed,digest}"""

import argparse
import logging
from datetime import UTC, date, datetime, timedelta

from dotenv import load_dotenv

from night_sky_digest.db import connect, migrate
from night_sky_digest.digest import OllamaChat, build_digest, save_digest
from night_sky_digest.embed import OllamaEmbedder, embed_pending
from night_sky_digest.ingest.oai import HttpFetch, SystemClock
from night_sky_digest.ingest.run import ingest
from night_sky_digest.tracing import make_tracer


def main() -> None:
    parser = argparse.ArgumentParser(prog="night_sky_digest")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply pending schema migrations")
    p_ingest = sub.add_parser("ingest", help="harvest new astro-ph metadata from arXiv")
    p_ingest.add_argument("--backfill-from", type=date.fromisoformat, help="first run only")
    p_ingest.add_argument("--until", type=date.fromisoformat, help="default: yesterday (UTC)")
    sub.add_parser("embed", help="embed new and changed papers with bge-m3 via Ollama")
    p_digest = sub.add_parser("digest", help="write the digest for one day's new papers")
    p_digest.add_argument(
        "--date", type=date.fromisoformat, help="submission day covered; default: yesterday (UTC)"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request drowns progress
    load_dotenv()  # local development; in the cluster DATABASE_URL comes from the environment

    with connect() as conn:
        if args.command == "migrate":
            applied = migrate(conn)
            logging.info("migrations applied: %s", applied or "none, schema is current")
        elif args.command == "ingest":
            fetch = HttpFetch()
            try:
                result = ingest(
                    conn,
                    fetch,
                    SystemClock(),
                    today=datetime.now(UTC).date(),
                    backfill_from=args.backfill_from,
                    until=args.until,
                )
            finally:
                fetch.close()
            logging.info("ingest done: %s", result)
        elif args.command == "embed":
            embedder = OllamaEmbedder()
            try:
                logging.info("embed done: %d papers", embed_pending(conn, embedder))
            finally:
                embedder.close()
        elif args.command == "digest":
            day = args.date or datetime.now(UTC).date() - timedelta(days=1)
            llm = OllamaChat()
            try:
                digest = build_digest(conn, llm, day, make_tracer())
            finally:
                llm.close()
            save_digest(conn, digest)
            print(digest.markdown)


if __name__ == "__main__":
    main()
