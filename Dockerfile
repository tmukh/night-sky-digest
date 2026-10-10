# syntax=docker/dockerfile:1

# Base images are pinned by digest: a tag can be moved to different content, a digest can't.
# python:3.12-slim-trixie as of 2026-10-10. Bumping it is a reviewed PR, like any code change.
ARG PYTHON_IMAGE=python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

FROM ghcr.io/astral-sh/uv:0.12.0@sha256:606e70c71c852d03f611b1e56a195d08648507018a7057fab82c4974c4eae105 AS uv

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# Runtime stage: no uv, no build tools, just the venv on the same base.
FROM ${PYTHON_IMAGE}
# pip ships in the base image but the app never installs anything at runtime.
# Removing it drops the only Python CVEs in the image and a tool an attacker could use.
RUN python -m pip uninstall --yes --root-user-action=ignore pip \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1
# Numeric UID so Kubernetes runAsNonRoot can verify it (PSS restricted).
USER 10001
EXPOSE 8000
CMD ["uvicorn", "night_sky_digest.api:app", "--host", "0.0.0.0", "--port", "8000"]
