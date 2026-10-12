"""Ranking metrics live in test_eval_metrics.py; this file covers the Prometheus side."""

from datetime import date, datetime

import httpx
import psycopg
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from night_sky_digest.api import app, get_embedder, get_pool
from night_sky_digest.metrics import BERLIN, PipelineCollector, on_time_days, registry
from night_sky_digest.search import search_for_user
from tests.fakes import FakeEmbedder
from tests.test_search import seed


def berlin(y: int, m: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=BERLIN)


# --- freshness SLI ----------------------------------------------------------------------------


def test_digest_written_before_seven_counts_as_on_time() -> None:
    now = berlin(2026, 10, 15, 12)
    digests = [
        (date(2026, 10, 13), berlin(2026, 10, 14, 6, 5)),  # on time
        (date(2026, 10, 14), berlin(2026, 10, 15, 7, 30)),  # late
    ]
    assert on_time_days(digests, now, start=date(2026, 10, 13)) == (1, 2)


def test_days_before_the_deadline_or_the_start_date_are_not_counted() -> None:
    now = berlin(2026, 10, 15, 6, 30)  # today's 07:00 deadline (for the 14th) hasn't passed yet
    digests = [(date(2026, 10, 13), berlin(2026, 10, 14, 6, 0))]
    assert on_time_days(digests, now, start=date(2026, 10, 13)) == (1, 1)
    assert on_time_days(digests, now, start=None) == (0, 0)


def test_missing_digest_is_a_bad_day() -> None:
    now = berlin(2026, 10, 15, 12)
    assert on_time_days([], now, start=date(2026, 10, 14)) == (0, 1)


# --- graceful degradation -----------------------------------------------------------------------


class DownEmbedder:
    model = "fake-bow"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise httpx.ConnectError("ollama unreachable")


def test_hybrid_falls_back_to_lexical_when_embedding_fails(conn: psycopg.Connection) -> None:
    seed(conn, FakeEmbedder())
    result = search_for_user(conn, DownEmbedder(), "JWST")
    assert result.degraded is True
    assert [h.arxiv_id for h in result.hits] == ["2610.00003"]


def test_explicit_semantic_mode_does_not_hide_the_failure(conn: psycopg.Connection) -> None:
    seed(conn, FakeEmbedder())
    try:
        search_for_user(conn, DownEmbedder(), "JWST", mode="semantic")
    except httpx.ConnectError:
        return
    raise AssertionError("expected the embedding error to surface")


# --- /metrics -----------------------------------------------------------------------------------


def test_metrics_endpoint_reports_requests_and_pipeline_state(
    conn: psycopg.Connection, db_url: str
) -> None:
    seed(conn, FakeEmbedder())
    with ConnectionPool(db_url, min_size=1, max_size=2) as pool:
        collector = PipelineCollector(pool)
        registry.register(collector)
        app.dependency_overrides[get_pool] = lambda: pool
        app.dependency_overrides[get_embedder] = FakeEmbedder
        try:
            client = TestClient(app)
            assert client.get("/search", params={"q": "radio bursts"}).status_code == 200
            body = client.get("/metrics").text
        finally:
            app.dependency_overrides.clear()
            registry.unregister(collector)
    assert (
        'night_sky_http_request_duration_seconds_count{method="GET",route="/search",status="200"}'
        in body
    )
    assert "night_sky_papers 3.0" in body
    assert "night_sky_ingest_last_success_timestamp_seconds NaN" in body  # no ingest run yet
    assert "night_sky_digest_expected_days 0.0" in body
