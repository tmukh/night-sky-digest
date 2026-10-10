import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Query, Request
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from night_sky_digest.embed import Embedder, OllamaEmbedder
from night_sky_digest.search import Mode, search


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_dotenv()  # local development; in the cluster these come from the environment
    app.state.pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=5)
    app.state.embedder = OllamaEmbedder()
    try:
        yield
    finally:
        app.state.pool.close()
        app.state.embedder.close()


app = FastAPI(title="Night Sky Digest", lifespan=lifespan)


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
    hits: list[SearchHit]


def get_pool(request: Request) -> ConnectionPool:
    return request.app.state.pool


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


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
        hits = search(conn, embedder, q, k=k, mode=mode)
    return SearchResponse(
        query=q,
        mode=mode,
        hits=[SearchHit(url=h.url, **h.__dict__) for h in hits],
    )
