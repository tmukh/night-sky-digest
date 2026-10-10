"""arXiv OAI-PMH client: response parsing, HTTP fetching and the harvest loop.

Protocol: https://www.openarchives.org/OAI/openarchivesprotocol.html
arXiv rules: https://info.arxiv.org/help/oa/index.html (max 1 request / 3 s, one connection).
"""

import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from xml.etree.ElementTree import Element

import httpx
from defusedxml.ElementTree import fromstring

BASE_URL = "https://oaipmh.arxiv.org/oai"
ASTRO_PH = "physics:astro-ph"
USER_AGENT = "night-sky-digest/0.1 (+https://github.com/tmukh/night-sky-digest)"
MIN_INTERVAL_S = 3.0

_OAI = "{http://www.openarchives.org/OAI/2.0/}"
_ARXIV = "{http://arxiv.org/OAI/arXiv/}"


# --- Data -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]  # first one is the primary category
    created: date
    updated: date | None
    datestamp: date  # last change on arXiv's side; what from/until filter on
    license: str | None
    doi: str | None
    comments: str | None

    @property
    def primary_category(self) -> str:
        return self.categories[0]


@dataclass(frozen=True)
class Deleted:
    arxiv_id: str
    datestamp: date


@dataclass(frozen=True)
class Page:
    records: list[Paper | Deleted]
    resumption_token: str | None  # None: this was the last page


class OAIError(Exception):
    """The repository answered with an OAI-PMH <error>, e.g. badResumptionToken."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class HarvestError(Exception):
    """The harvest can't continue (HTTP errors, retries exhausted)."""


# --- Parsing --------------------------------------------------------------------------------


def parse_page(xml: bytes) -> Page:
    """Parse one ListRecords response. noRecordsMatch is an empty last page, not an error."""
    root = fromstring(xml)  # defusedxml: no entity expansion or external entities
    error = root.find(f"{_OAI}error")
    if error is not None:
        code = error.get("code", "")
        if code == "noRecordsMatch":
            return Page(records=[], resumption_token=None)
        raise OAIError(code, (error.text or "").strip())

    list_records = root.find(f"{_OAI}ListRecords")
    if list_records is None:
        raise OAIError("unexpectedResponse", "no <ListRecords> element")
    records = [_parse_record(r) for r in list_records.iterfind(f"{_OAI}record")]
    token = list_records.findtext(f"{_OAI}resumptionToken", default="").strip()
    return Page(records=records, resumption_token=token or None)


def _parse_record(record: Element) -> Paper | Deleted:
    header = _child(record, f"{_OAI}header")
    arxiv_id = _text(header, f"{_OAI}identifier").removeprefix("oai:arXiv.org:")
    datestamp = date.fromisoformat(_text(header, f"{_OAI}datestamp"))
    if header.get("status") == "deleted":
        return Deleted(arxiv_id=arxiv_id, datestamp=datestamp)

    meta = _child(record, f"{_OAI}metadata/{_ARXIV}arXiv")
    updated = meta.findtext(f"{_ARXIV}updated")
    return Paper(
        arxiv_id=arxiv_id,
        title=_squash(_text(meta, f"{_ARXIV}title")),
        abstract=_squash(_text(meta, f"{_ARXIV}abstract")),
        authors=[_author(a) for a in meta.iterfind(f"{_ARXIV}authors/{_ARXIV}author")],
        categories=_text(meta, f"{_ARXIV}categories").split(),
        created=date.fromisoformat(_text(meta, f"{_ARXIV}created")),
        updated=date.fromisoformat(updated.strip()) if updated else None,
        datestamp=datestamp,
        license=_optional(meta, f"{_ARXIV}license"),
        doi=_optional(meta, f"{_ARXIV}doi"),
        comments=_optional(meta, f"{_ARXIV}comments"),
    )


def _author(author: Element) -> str:
    parts = (author.findtext(f"{_ARXIV}{tag}") for tag in ("forenames", "keyname", "suffix"))
    return " ".join(p.strip() for p in parts if p and p.strip())


def _child(parent: Element, path: str) -> Element:
    child = parent.find(path)
    if child is None:
        raise OAIError("unexpectedResponse", f"missing <{path}>")
    return child


def _text(parent: Element, path: str) -> str:
    return (_child(parent, path).text or "").strip()


def _optional(parent: Element, path: str) -> str | None:
    value = parent.findtext(path)
    return _squash(value) if value and value.strip() else None


def _squash(text: str) -> str:
    """Titles and abstracts arrive hard-wrapped and indented; collapse all whitespace."""
    return " ".join(text.split())


# --- Fetching -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    headers: Mapping[str, str]  # lower-case keys


class Fetch(Protocol):
    def __call__(self, params: Mapping[str, str]) -> Response: ...


class Clock(Protocol):
    def monotonic(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class HttpFetch:
    """GET against the OAI-PMH endpoint: one connection, identifying User-Agent, long timeout
    (a 1,300-record page takes ~10 s to generate)."""

    def __init__(self, url: str = BASE_URL, timeout_s: float = 120.0) -> None:
        self._url = url
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout_s,
            limits=httpx.Limits(max_connections=1),
        )

    def __call__(self, params: Mapping[str, str]) -> Response:
        r = self._client.get(self._url, params=dict(params))
        return Response(r.status_code, r.content, {k.lower(): v for k, v in r.headers.items()})

    def close(self) -> None:
        self._client.close()


# --- Harvesting -----------------------------------------------------------------------------


def harvest(
    fetch: Fetch,
    clock: Clock,
    *,
    from_: date,
    until: date | None = None,
    set_spec: str = ASTRO_PH,
    min_interval: float = MIN_INTERVAL_S,
    max_retries: int = 5,
) -> Iterator[Page]:
    """Yield every page of a ListRecords harvest, politely.

    TODO(M1, Tarik): implement. Each rule is pinned down by a test in tests/test_harvest.py.

    1. First request: verb=ListRecords, metadataPrefix=arXiv, set, from, and until if given.
       Dates as YYYY-MM-DD.
    2. Follow-up requests: verb=ListRecords and resumptionToken, nothing else.
    3. Stop after the page whose resumption_token is None.
    4. Request *starts* are at least min_interval seconds apart, measured with
       clock.monotonic(). Wait with clock.sleep(), and only as long as needed.
       No wait before the very first request.
    5. HTTP 503: wait Retry-After seconds (min_interval if the header is missing) and retry
       the same request. After max_retries retries, raise HarvestError. Rule 4 still applies.
    6. Any other non-200 status: raise HarvestError.

    Parse each body with parse_page() and yield the Page before fetching the next one,
    so the caller can store each page before the next request goes out.
    """
    raise NotImplementedError
