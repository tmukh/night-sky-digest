import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from night_sky_digest.embed import Embedder, OllamaEmbedder
from night_sky_digest.metrics import PipelineCollector, registry, track_requests
from night_sky_digest.search import Mode, search_for_user


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_dotenv()  # local development; in the cluster these come from the environment
    app.state.pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=5)
    app.state.embedder = OllamaEmbedder()
    collector = PipelineCollector(app.state.pool)
    registry.register(collector)
    try:
        yield
    finally:
        registry.unregister(collector)
        app.state.pool.close()
        app.state.embedder.close()


app = FastAPI(title="Night Sky Digest", lifespan=lifespan)
app.middleware("http")(track_requests)


class SearchHit(BaseModel):
    arxiv_id: str
    url: str
    title: str
    authors: list[str]
    primary_category: str
    created: date
    score: float
    lexical_rank: int | None
    semantic_rank: int | None


class SearchResponse(BaseModel):
    query: str
    mode: Mode
    degraded: bool  # True: embedding failed, these are lexical-only results
    hits: list[SearchHit]


def get_pool(request: Request) -> ConnectionPool:
    return request.app.state.pool


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
def search_endpoint(
    q: Annotated[str, Query(min_length=2, max_length=500)],
    pool: Annotated[ConnectionPool, Depends(get_pool)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    k: Annotated[int, Query(ge=1, le=50)] = 10,
    mode: Mode = "hybrid",
) -> SearchResponse:
    with pool.connection() as conn:
        result = search_for_user(conn, embedder, q, k=k, mode=mode)
    return SearchResponse(
        query=q,
        mode=mode,
        degraded=result.degraded,
        hits=[SearchHit(url=h.url, **h.__dict__) for h in result.hits],
    )


class DigestResponse(BaseModel):
    date: date
    created_at: str
    model: str
    sections: list[dict]
    markdown: str
    stats: dict


def _digest(pool: ConnectionPool, day: date | None) -> DigestResponse:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT digest_date, created_at, model, sections, markdown, stats FROM digests"
            " WHERE (%(day)s::date IS NULL OR digest_date = %(day)s::date)"
            " ORDER BY digest_date DESC LIMIT 1",
            {"day": day},
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="no digest for that day")
    return DigestResponse(
        date=row[0],
        created_at=row[1].isoformat(),
        model=row[2],
        sections=row[3],
        markdown=row[4],
        stats=row[5],
    )


@app.get("/digest/latest")
def digest_latest(pool: Annotated[ConnectionPool, Depends(get_pool)]) -> DigestResponse:
    return _digest(pool, None)


@app.get("/digest/{day}.md", response_class=PlainTextResponse)
def digest_markdown(day: date, pool: Annotated[ConnectionPool, Depends(get_pool)]) -> str:
    return _digest(pool, day).markdown


@app.get("/digest/{day}")
def digest_for_day(day: date, pool: Annotated[ConnectionPool, Depends(get_pool)]) -> DigestResponse:
    return _digest(pool, day)
