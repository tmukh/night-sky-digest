"""Server-rendered website: today's digest, earlier days, and search. No JavaScript."""

from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from psycopg_pool import ConnectionPool

from night_sky_digest.deps import get_embedder, get_pool
from night_sky_digest.embed import Embedder
from night_sky_digest.search import Mode, search_for_user

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")  # autoescapes .html
router = APIRouter(include_in_schema=False)


def _render_day(request: Request, pool: ConnectionPool, day: date | None) -> HTMLResponse:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT digest_date, model, sections, stats FROM digests"
            " WHERE (%(day)s::date IS NULL OR digest_date = %(day)s::date)"
            " ORDER BY digest_date DESC LIMIT 1",
            {"day": day},
        ).fetchone()
        if row is None and day is not None:
            raise HTTPException(status_code=404, detail="no digest for that day")
        shown = row[0] if row else None
        previous = next_ = None
        if shown:
            previous = conn.execute(
                "SELECT max(digest_date) FROM digests WHERE digest_date < %s", (shown,)
            ).fetchone()[0]
            next_ = conn.execute(
                "SELECT min(digest_date) FROM digests WHERE digest_date > %s", (shown,)
            ).fetchone()[0]
    digest = {"model": row[1], "sections": row[2], "stats": row[3]} if row else None
    return templates.TemplateResponse(
        request,
        "digest.html",
        {"day": shown, "digest": digest, "previous": previous, "next": next_},
    )


@router.get("/", response_class=HTMLResponse)
def home(request: Request, pool: Annotated[ConnectionPool, Depends(get_pool)]) -> HTMLResponse:
    return _render_day(request, pool, None)


@router.get("/days/{day}", response_class=HTMLResponse)
def day_page(
    request: Request, day: date, pool: Annotated[ConnectionPool, Depends(get_pool)]
) -> HTMLResponse:
    return _render_day(request, pool, day)


@router.get("/find", response_class=HTMLResponse)
def find(
    request: Request,
    q: Annotated[str, Query(min_length=2, max_length=500)],
    pool: Annotated[ConnectionPool, Depends(get_pool)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    mode: Mode = "hybrid",
) -> HTMLResponse:
    with pool.connection() as conn:
        result = search_for_user(conn, embedder, q, k=20, mode=mode)
    return templates.TemplateResponse(
        request,
        "find.html",
        {"query": q, "mode": mode, "hits": result.hits, "degraded": result.degraded},
    )
