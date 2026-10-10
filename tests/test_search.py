"""Embedding job, hybrid search and /search, against the test database with a fake embedder."""

from datetime import date

import psycopg
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from night_sky_digest.api import app, get_embedder, get_pool
from night_sky_digest.embed import embed_pending
from night_sky_digest.ingest.oai import Deleted, Paper
from night_sky_digest.ingest.store import store_page
from night_sky_digest.search import search
from tests.fakes import FakeEmbedder


def paper(arxiv_id: str, title: str, abstract: str, **kw: object) -> Paper:
    fields: dict = dict(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=["A. Astronomer"],
        categories=["astro-ph.HE"],
        created=date(2026, 10, 1),
        updated=None,
        datestamp=date(2026, 10, 8),
        license=None,
        doi=None,
        comments=None,
    )
    fields.update(kw)
    return Paper(**fields)


CORPUS = [
    paper(
        "2610.00001", "Localising fast radio bursts", "Interferometric localisation of FRB sources."
    ),
    paper("2610.00002", "Black hole shadows", "Thermodynamics and shadows of charged black holes."),
    paper("2610.00003", "Exoplanet atmospheres", "Transmission spectra of hot Jupiters with JWST."),
]


def seed(conn: psycopg.Connection, embedder: FakeEmbedder) -> None:
    store_page(conn, list(CORPUS))
    conn.commit()
    embed_pending(conn, embedder)


def test_embed_pending_embeds_once_then_only_changes(conn: psycopg.Connection) -> None:
    embedder = FakeEmbedder()
    store_page(conn, list(CORPUS))
    conn.commit()
    assert embed_pending(conn, embedder) == 3
    assert embed_pending(conn, embedder) == 0
    store_page(
        conn,
        [
            paper(
                "2610.00002",
                "Black hole shadows revisited",
                "New abstract.",
                datestamp=date(2026, 10, 9),
            )
        ],
    )
    conn.commit()
    assert embed_pending(conn, embedder) == 1


def test_lexical_finds_exact_terms(conn: psycopg.Connection) -> None:
    seed(conn, FakeEmbedder())
    hits = search(conn, FakeEmbedder(), "JWST", mode="lexical")
    assert [h.arxiv_id for h in hits] == ["2610.00003"]
    assert hits[0].lexical_rank == 1 and hits[0].semantic_rank is None


def test_semantic_ranks_by_similarity(conn: psycopg.Connection) -> None:
    seed(conn, FakeEmbedder())
    hits = search(conn, FakeEmbedder(), "charged black holes", mode="semantic")
    assert hits[0].arxiv_id == "2610.00002"
    assert len(hits) == 3  # nearest neighbours always return something


def test_hybrid_puts_agreement_first(conn: psycopg.Connection) -> None:
    seed(conn, FakeEmbedder())
    hits = search(conn, FakeEmbedder(), "fast radio bursts localisation")
    assert hits[0].arxiv_id == "2610.00001"
    assert hits[0].lexical_rank == 1 and hits[0].semantic_rank == 1


def test_deleted_papers_are_not_returned(conn: psycopg.Connection) -> None:
    seed(conn, FakeEmbedder())
    store_page(conn, [Deleted("2610.00001", date(2026, 10, 9))])
    conn.commit()
    ids = {h.arxiv_id for h in search(conn, FakeEmbedder(), "fast radio bursts")}
    assert "2610.00001" not in ids


def test_search_endpoint(conn: psycopg.Connection, db_url: str) -> None:
    seed(conn, FakeEmbedder())
    with ConnectionPool(db_url, min_size=1, max_size=1) as pool:
        app.dependency_overrides[get_pool] = lambda: pool
        app.dependency_overrides[get_embedder] = FakeEmbedder
        try:
            r = TestClient(app).get("/search", params={"q": "radio bursts", "k": 2})
        finally:
            app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "hybrid" and len(body["hits"]) == 2
    assert body["hits"][0]["url"] == "https://arxiv.org/abs/2610.00001"


def test_search_endpoint_validates_query() -> None:
    app.dependency_overrides[get_pool] = lambda: None
    app.dependency_overrides[get_embedder] = FakeEmbedder
    try:
        assert TestClient(app).get("/search", params={"q": "x"}).status_code == 422
    finally:
        app.dependency_overrides.clear()
