"""FastAPI dependencies shared by the JSON API and the website (tests override these)."""

from fastapi import Request
from psycopg_pool import ConnectionPool

from night_sky_digest.embed import Embedder


def get_pool(request: Request) -> ConnectionPool:
    return request.app.state.pool


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder
