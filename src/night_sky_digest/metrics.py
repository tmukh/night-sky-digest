"""Prometheus metrics: HTTP latency/errors per route (search SLO) and pipeline state read from the
database at scrape time (freshness SLO). The CronJobs are short-lived, so instead of pushing their
metrics somewhere, the API reports what they left behind in harvest_runs and digests."""

import os
import time
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from datetime import time as dtime
from zoneinfo import ZoneInfo

from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from psycopg_pool import ConnectionPool
from starlette.requests import Request
from starlette.responses import Response

BERLIN = ZoneInfo("Europe/Berlin")
DIGEST_DEADLINE = dtime(7, 0)  # freshness SLO: digest ready by 07:00 Europe/Berlin
SLO_WINDOW_DAYS = 28
# Days before this don't count for the freshness SLO (the system didn't run nightly yet).
SLO_START_ENV = "NIGHT_SKY_SLO_START"

registry = CollectorRegistry()

REQUEST_SECONDS = Histogram(
    "night_sky_http_request_duration_seconds",
    "HTTP request latency by route template and status code.",
    ["route", "method", "status"],
    # 0.8 s is the search SLO threshold, so it must be a bucket boundary.
    buckets=(0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4),
    registry=registry,
)

SEARCH_DEGRADED = Counter(
    "night_sky_search_degraded_total",
    "Hybrid searches answered with lexical results only because embedding failed.",
    registry=registry,
)


async def track_requests(request: Request, call_next: Callable) -> Response:
    """Middleware: time every request, labelled by route template (/digest/{day}, not the date)."""
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        if path != "/metrics":
            REQUEST_SECONDS.labels(path, request.method, str(status)).observe(
                time.perf_counter() - start
            )


class PipelineCollector(Collector):
    """Gauges computed from Postgres on every scrape."""

    def __init__(self, pool: ConnectionPool, now: Callable[[], datetime] | None = None) -> None:
        self._pool = pool
        self._now = now or (lambda: datetime.now(BERLIN))

    def collect(self) -> Iterator[GaugeMetricFamily]:
        with self._pool.connection() as conn:
            ingest = conn.execute(
                "SELECT extract(epoch FROM max(finished_at)) FROM harvest_runs"
                " WHERE status = 'success'"
            ).fetchone()
            papers = conn.execute("SELECT count(*) FROM papers WHERE NOT deleted").fetchone()
            latest = conn.execute(
                "SELECT extract(epoch FROM created_at), digest_date,"
                " (stats->>'prompt_tokens')::int, (stats->>'completion_tokens')::int,"
                " (stats->>'llm_seconds')::float, (stats->>'dropped_highlights')::int"
                " FROM digests ORDER BY digest_date DESC LIMIT 1"
            ).fetchone()
            window = conn.execute(
                "SELECT digest_date, created_at FROM digests WHERE digest_date >= %s",
                (self._now().date() - timedelta(days=SLO_WINDOW_DAYS + 1),),
            ).fetchall()
            first = conn.execute("SELECT min(digest_date) FROM digests").fetchone()[0]
        start_env = os.environ.get(SLO_START_ENV)
        slo_start = date.fromisoformat(start_env) if start_env else first

        yield _gauge("night_sky_ingest_last_success_timestamp_seconds",
                     "When the last successful ingest run finished.", ingest[0])  # fmt: skip
        yield _gauge("night_sky_papers", "Papers in the index (not deleted).", papers[0])
        if latest:
            yield _gauge("night_sky_digest_last_success_timestamp_seconds",
                         "When the latest digest was written.", latest[0])  # fmt: skip
            yield _gauge("night_sky_digest_prompt_tokens", "Prompt tokens of the latest digest.",
                         latest[2])  # fmt: skip
            yield _gauge("night_sky_digest_completion_tokens",
                         "Completion tokens of the latest digest.", latest[3])  # fmt: skip
            yield _gauge(
                "night_sky_digest_llm_seconds", "LLM time of the latest digest.", latest[4]
            )
            yield _gauge("night_sky_digest_dropped_highlights",
                         "Highlights dropped by the faithfulness check in the latest digest.",
                         latest[5])  # fmt: skip

        good, total = on_time_days(window, self._now(), slo_start)
        yield _gauge("night_sky_digest_on_time_days",
                     f"Days in the last {SLO_WINDOW_DAYS} with the digest ready by 07:00 Berlin.",
                     good)  # fmt: skip
        yield _gauge("night_sky_digest_expected_days",
                     f"Days in the last {SLO_WINDOW_DAYS} whose digest deadline has passed.",
                     total)  # fmt: skip


def on_time_days(digests: list[tuple], now: datetime, start: date | None) -> tuple[int, int]:
    """Freshness SLI over the window. The digest for announcement day D is due by 07:00 Berlin on
    D+1. A day counts once its deadline has passed and it's not before `start`; it's good if a
    digest was written by the deadline."""
    written = {d: created for d, created in digests}
    good = total = 0
    for back in range(1, SLO_WINDOW_DAYS + 1):
        day = now.date() - timedelta(days=back)
        deadline = datetime.combine(day + timedelta(days=1), DIGEST_DEADLINE, BERLIN)
        if deadline > now or start is None or day < start:
            continue
        total += 1
        created = written.get(day)
        if created is not None and created <= deadline:
            good += 1
    return good, total


def _gauge(name: str, doc: str, value: float | None) -> GaugeMetricFamily:
    g = GaugeMetricFamily(name, doc)
    g.add_metric([], float("nan") if value is None else float(value))
    return g
