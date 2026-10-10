"""Spec for harvest(). A fake clock and a scripted server: no network, no real sleeping."""

from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest

from night_sky_digest.ingest.oai import HarvestError, Response, harvest

FIXTURES = Path(__file__).parent / "fixtures" / "oai"
FIRST = (FIXTURES / "list_records_first.xml").read_bytes()
LAST = (FIXTURES / "list_records_last.xml").read_bytes()
NO_RECORDS = (FIXTURES / "no_records_match.xml").read_bytes()


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


def run(server: ScriptedServer, clock: FakeClock, **kwargs: object) -> list:
    kwargs.setdefault("from_", date(2026, 9, 1))
    return list(harvest(server, clock, **kwargs))  # type: ignore[arg-type]


# 1-3: protocol


def test_first_request_parameters() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(LAST)])
    run(server, clock, from_=date(2026, 9, 1), until=date(2026, 10, 8))
    assert server.calls[0][1] == {
        "verb": "ListRecords",
        "metadataPrefix": "arXiv",
        "set": "physics:astro-ph",
        "from": "2026-09-01",
        "until": "2026-10-08",
    }


def test_until_is_optional() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(LAST)])
    run(server, clock)
    assert "until" not in server.calls[0][1]


def test_follow_up_request_sends_only_the_token() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(FIRST), ok(LAST)])
    run(server, clock)
    params = server.calls[1][1]
    assert params.keys() == {"verb", "resumptionToken"}
    assert params["resumptionToken"].startswith("verb%3DListRecords")


def test_stops_after_last_page() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(FIRST), ok(LAST)])
    pages = run(server, clock)
    assert len(pages) == 2 and len(server.calls) == 2
    assert [len(p.records) for p in pages] == [3, 2]


def test_no_records_match_yields_one_empty_page() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(NO_RECORDS)])
    pages = run(server, clock)
    assert len(pages) == 1 and pages[0].records == []


def test_yields_each_page_before_fetching_the_next() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(FIRST), ok(LAST)])
    pages = harvest(server, clock, from_=date(2026, 9, 1))
    next(pages)
    assert len(server.calls) == 1


# 4: politeness


def test_request_starts_are_min_interval_apart() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(FIRST), ok(FIRST), ok(LAST)])
    run(server, clock)
    assert [t for t, _ in server.calls] == [0.0, 3.0, 6.0]


def test_no_sleep_before_first_request() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(LAST)])
    run(server, clock)
    assert clock.slept == [] or clock.slept == [0.0]


def test_slow_responses_need_no_extra_wait() -> None:
    # arXiv takes ~10 s per big page; the 3 s are already used up by then.
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(FIRST), ok(LAST)], latency=10.0)
    run(server, clock)
    assert [t for t, _ in server.calls] == [0.0, 10.0]
    assert sum(clock.slept) == 0.0


def test_partially_slow_response_waits_only_the_rest() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [ok(FIRST), ok(LAST)], latency=1.0)
    run(server, clock)
    assert [t for t, _ in server.calls] == [0.0, 3.0]


# 5-6: errors


def test_503_waits_retry_after_then_retries_same_request() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [unavailable("20"), ok(LAST)])
    pages = run(server, clock)
    assert len(pages) == 1
    (t0, p0), (t1, p1) = server.calls
    assert p0 == p1
    assert t1 - t0 >= 20.0


def test_503_without_retry_after_still_respects_min_interval() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [unavailable(), ok(LAST)])
    run(server, clock)
    assert server.calls[1][0] - server.calls[0][0] >= 3.0


def test_gives_up_after_max_retries() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [unavailable("5")] * 4)
    with pytest.raises(HarvestError):
        run(server, clock, max_retries=3)
    assert len(server.calls) == 4  # 1 attempt + 3 retries


def test_other_http_errors_raise() -> None:
    clock = FakeClock()
    server = ScriptedServer(clock, [Response(500, b"boom", {})])
    with pytest.raises(HarvestError):
        run(server, clock)
