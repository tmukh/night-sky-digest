"""Fakes for harvest tests: a clock that never really sleeps and a scripted OAI server."""

import hashlib
import math
import re
from collections.abc import Mapping

from night_sky_digest.ingest.oai import Response


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0, "negative sleep"
        self.slept.append(seconds)
        self.now += seconds


class ScriptedServer:
    """Returns the scripted responses in order and records when and with what it was called.
    `latency` is how long each response takes; the clock advances by that much per call."""

    def __init__(self, clock: FakeClock, responses: list[Response], latency: float = 0.0) -> None:
        self.clock = clock
        self.responses = list(responses)
        self.latency = latency
        self.calls: list[tuple[float, dict[str, str]]] = []

    def __call__(self, params: Mapping[str, str]) -> Response:
        self.calls.append((self.clock.now, dict(params)))
        self.clock.now += self.latency
        return self.responses.pop(0)


def ok(body: bytes) -> Response:
    return Response(200, body, {})


def unavailable(retry_after: str | None = None) -> Response:
    return Response(503, b"", {"retry-after": retry_after} if retry_after else {})


class FakeEmbedder:
    """Deterministic bag-of-words vectors: texts sharing words point in similar directions.
    Good enough to test the plumbing; says nothing about real retrieval quality."""

    model = "fake-bow"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._one(t) for t in texts]

    @staticmethod
    def _one(text: str) -> list[float]:
        v = [0.0] * 1024
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 1024] += 1.0  # noqa: S324
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]
