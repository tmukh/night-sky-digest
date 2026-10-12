from collections.abc import Iterator
from datetime import date

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from night_sky_digest.api import app
from night_sky_digest.deps import get_embedder, get_pool
from night_sky_digest.digest import Digest, DigestStats, Highlight, Section, save_digest
from tests.fakes import FakeEmbedder
from tests.test_metrics import DownEmbedder
from tests.test_search import seed


def digest_for(day: date) -> Digest:
    stats = DigestStats(papers=2, highlights=1)
    section = Section(
        "HE", "High-energy astrophysics", 2, [Highlight("An FRB was localised.", ["2610.00001"])]
    )
    return Digest(day, "test-model", [section], stats)


@pytest.fixture
def client(conn: psycopg.Connection, db_url: str) -> Iterator[TestClient]:
    seed(conn, FakeEmbedder())
    save_digest(conn, digest_for(date(2026, 10, 8)))
    save_digest(conn, digest_for(date(2026, 10, 9)))
    with ConnectionPool(db_url, min_size=1, max_size=2) as pool:
        app.dependency_overrides[get_pool] = lambda: pool
        app.dependency_overrides[get_embedder] = FakeEmbedder
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()


def test_home_shows_the_latest_digest(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "Friday, 09 October 2026" in r.text
    assert 'href="https://arxiv.org/abs/2610.00001"' in r.text
    assert 'href="/days/2026-10-08"' in r.text  # link to the previous day
    assert "Thank you to arXiv for use of its open access interoperability" in r.text


def test_day_page_and_missing_day(client: TestClient) -> None:
    assert "Thursday, 08 October 2026" in client.get("/days/2026-10-08").text
    assert client.get("/days/2020-01-01").status_code == 404


def test_find_shows_results_with_how_they_were_found(client: TestClient) -> None:
    r = client.get("/find", params={"q": "fast radio bursts localisation"})
    assert r.status_code == 200
    assert "Localising fast radio bursts" in r.text
    assert ">both</span>" in r.text


def test_find_escapes_the_query(client: TestClient) -> None:
    r = client.get("/find", params={"q": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text


def test_find_says_when_results_are_keyword_only(client: TestClient) -> None:
    app.dependency_overrides[get_embedder] = DownEmbedder
    r = client.get("/find", params={"q": "JWST"})
    assert "keyword matches only" in r.text and "Exoplanet atmospheres" in r.text
