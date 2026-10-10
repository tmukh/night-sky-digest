"""Command line: python -m night_sky_digest {migrate,ingest}"""

import argparse
import logging
from datetime import UTC, date, datetime

from dotenv import load_dotenv

from night_sky_digest.db import connect, migrate
from night_sky_digest.ingest.oai import HttpFetch, SystemClock
from night_sky_digest.ingest.run import ingest


def main() -> None:
    parser = argparse.ArgumentParser(prog="night_sky_digest")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply pending schema migrations")
    p_ingest = sub.add_parser("ingest", help="harvest new astro-ph metadata from arXiv")
    p_ingest.add_argument("--backfill-from", type=date.fromisoformat, help="first run only")
    p_ingest.add_argument("--until", type=date.fromisoformat, help="default: yesterday (UTC)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
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


if __name__ == "__main__":
    main()
