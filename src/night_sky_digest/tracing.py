"""LLM tracing. Langfuse when LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL are
set, otherwise a no-op, so the digest runs the same with or without a tracing backend."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol


class Observation(Protocol):
    def update(self, **fields: Any) -> None: ...


class Tracer(Protocol):
    def trace(self, name: str, input: Any) -> Any: ...  # context manager -> Observation
    def generation(self, name: str, model: str, input: Any) -> Any: ...  # same
    def score(self, name: str, value: float) -> None: ...
    def flush(self) -> None: ...


class _Noop:
    def update(self, **fields: Any) -> None:
        pass


class NoTracer:
    @contextmanager
    def trace(self, name: str, input: Any) -> Iterator[Observation]:
        yield _Noop()

    @contextmanager
    def generation(self, name: str, model: str, input: Any) -> Iterator[Observation]:
        yield _Noop()

    def score(self, name: str, value: float) -> None:
        pass

    def flush(self) -> None:
        pass


class _LangfuseGeneration:
    """Maps our field names onto Langfuse's: tokens go into usage_details so Langfuse can chart
    them and compute cost. Local models cost nothing, so cost stays empty."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def update(self, **fields: Any) -> None:
        prompt, completion = (
            fields.pop("prompt_tokens", None),
            fields.pop("completion_tokens", None),
        )
        if prompt is not None or completion is not None:
            fields["usage_details"] = {"input": prompt or 0, "output": completion or 0}
        self._inner.update(**fields)


class LangfuseTracer:
    def __init__(self) -> None:
        from langfuse import Langfuse  # optional dependency path; only imported when configured

        # Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL from the environment.
        self._client = Langfuse()

    @contextmanager
    def trace(self, name: str, input: Any) -> Iterator[Observation]:
        with self._client.start_as_current_observation(name=name, as_type="span", input=input) as o:
            yield o

    @contextmanager
    def generation(self, name: str, model: str, input: Any) -> Iterator[Observation]:
        with self._client.start_as_current_observation(
            name=name, as_type="generation", model=model, input=input
        ) as o:
            yield _LangfuseGeneration(o)

    def score(self, name: str, value: float) -> None:
        self._client.score_current_trace(name=name, value=value)

    def flush(self) -> None:
        self._client.flush()


def make_tracer() -> Tracer:
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        return LangfuseTracer()
    return NoTracer()
