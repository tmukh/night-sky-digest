"""The morning digest: one LLM call per astro-ph subfield, every highlight cites arXiv IDs, and
a faithfulness check rejects citations of papers the LLM wasn't given."""

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Protocol

import httpx
import psycopg

from night_sky_digest.tracing import NoTracer, Tracer

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("DIGEST_MODEL", "qwen2.5:7b")
MAX_ATTEMPTS = 3  # first try plus two retries with feedback
ABSTRACT_BUDGET_CHARS = 24_000  # per subfield prompt; long sections get abstracts shortened

SUBFIELDS = {
    "CO": "Cosmology",
    "GA": "Galaxies",
    "HE": "High-energy astrophysics",
    "SR": "Solar and stellar",
    "EP": "Planets and the Solar System",
    "IM": "Instruments and methods",
}

# New-style (2410.01234) and old-style (astro-ph/0601001) IDs, with an optional version suffix.
ARXIV_ID = re.compile(r"(?<![\w.])(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?(?![\w])")

SYSTEM_PROMPT = """\
You write a short morning digest of new astrophysics papers for a curious, technically literate
reader. You get one day's new papers in one astro-ph subfield, each with its arXiv ID.
Pick the most interesting findings. For each, write one or two plain sentences: what was found and
why it matters. Put the arXiv IDs the highlight is based on in "arxiv_ids".
Rules:
- Use only information from the abstracts given. No outside facts.
- Cite only IDs from the list, copied exactly. Every highlight cites at least one.
- You may combine closely related papers in one highlight.
- Do not write arXiv IDs inside the summary text.
- Plain text only: no LaTeX, no Markdown, no math markup."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "arxiv_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["summary", "arxiv_ids"],
            },
        }
    },
    "required": ["highlights"],
}


@dataclass(frozen=True)
class SourcePaper:
    arxiv_id: str
    title: str
    abstract: str


@dataclass
class Highlight:
    summary: str
    arxiv_ids: list[str]


@dataclass
class Section:
    code: str
    title: str
    paper_count: int
    highlights: list[Highlight]


@dataclass
class DigestStats:
    papers: int = 0
    llm_calls: int = 0
    retries: int = 0
    highlights: int = 0
    dropped_highlights: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_seconds: float = 0.0
    problems: list[str] = field(default_factory=list)


@dataclass
class Digest:
    day: date
    model: str
    sections: list[Section]
    stats: DigestStats

    @property
    def markdown(self) -> str:
        lines = [f"# Night Sky Digest: {self.day.isoformat()}", ""]
        if not self.sections:
            lines.append("No new astro-ph papers for this day.")
        for s in self.sections:
            lines += [f"## {s.title} ({s.paper_count} new)", ""]
            for h in s.highlights:
                refs = ", ".join(f"[{a}](https://arxiv.org/abs/{a})" for a in h.arxiv_ids)
                lines.append(f"- {h.summary} ({refs})")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


# --- Faithfulness ---------------------------------------------------------------------------


def normalise_id(raw: str) -> str:
    """'arXiv:2410.01234v2' -> '2410.01234'."""
    m = ARXIV_ID.search(raw.strip())
    return m.group(1) if m else raw.strip()


def check_faithfulness(highlights: list[Highlight], allowed: set[str]) -> list[str]:
    """Problems with the citations, as sentences the LLM can act on. Empty list = faithful.

    Every highlight must cite at least one paper, every cited ID must be one the LLM was given,
    and IDs mentioned inside the summary text count as citations too.
    """
    problems = []
    for n, h in enumerate(highlights, start=1):
        if not h.arxiv_ids:
            problems.append(f"Highlight {n} cites no paper.")
        for arxiv_id in h.arxiv_ids:
            if arxiv_id not in allowed:
                problems.append(f"Highlight {n} cites {arxiv_id}, which is not in the list.")
        for m in ARXIV_ID.finditer(h.summary):
            if m.group(1) not in allowed:
                problems.append(f"Highlight {n} mentions {m.group(1)}, which is not in the list.")
    return problems


def faithful_only(highlights: list[Highlight], allowed: set[str]) -> list[Highlight]:
    return [h for h in highlights if not check_faithfulness([h], allowed)]


# --- LLM ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatResult:
    content: dict
    prompt_tokens: int
    completion_tokens: int
    seconds: float


class ChatModel(Protocol):
    model: str

    def chat(self, messages: list[dict], schema: dict) -> ChatResult: ...


class OllamaChat:
    def __init__(self, model: str = DEFAULT_MODEL, url: str | None = None) -> None:
        self.model = model
        self._url = (url or os.environ.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self._client = httpx.Client(timeout=600.0)

    def chat(self, messages: list[dict], schema: dict) -> ChatResult:
        start = time.perf_counter()
        r = self._client.post(
            f"{self._url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "format": schema,
                "think": False,
                "stream": False,
                "options": {"temperature": 0.2, "num_ctx": 16384},
            },
        )
        r.raise_for_status()
        body = r.json()
        return ChatResult(
            content=json.loads(body["message"]["content"]),
            prompt_tokens=body.get("prompt_eval_count", 0),
            completion_tokens=body.get("eval_count", 0),
            seconds=time.perf_counter() - start,
        )

    def close(self) -> None:
        self._client.close()


# --- Building a digest ----------------------------------------------------------------------


def papers_for_day(conn: psycopg.Connection, day: date) -> dict[str, list[SourcePaper]]:
    """Papers first announced on `day` whose primary category is astro-ph, by subfield.

    arXiv's `created` is the submission date of the *latest* version, so it also matches revisions
    of old papers. Instead: announced that day (datestamp) with an ID from that month or the month
    before. Brand-new papers get IDs from their announcement month; papers held in moderation
    across a month boundary get the previous one. Revisions keep their old ID and drop out.
    """
    fresh = (_yymm(day), _yymm(day.replace(day=1) - timedelta(days=1)))
    rows = conn.execute(
        """
        SELECT split_part(primary_category, '.', 2), arxiv_id, title, abstract
          FROM papers
         WHERE datestamp = %s AND NOT deleted AND primary_category LIKE 'astro-ph.%%'
           AND left(arxiv_id, 4) = ANY(%s)
         ORDER BY arxiv_id
        """,
        (day, list(fresh)),
    ).fetchall()
    by_code: dict[str, list[SourcePaper]] = {}
    for code, arxiv_id, title, abstract in rows:
        if code in SUBFIELDS:
            by_code.setdefault(code, []).append(
                SourcePaper(arxiv_id, plain(title), plain(abstract))
            )
    return by_code


def _yymm(d: date) -> str:
    return f"{d.year % 100:02d}{d.month:02d}"


_LATEX_SYMBOLS = {
    "Lambda": "Λ", "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "mu": "μ",
    "nu": "ν", "sigma": "σ", "Omega": "Ω", "odot": "☉", "sim": "~", "approx": "≈",
    "pm": "±", "times": "×", "lesssim": "≲", "gtrsim": "≳",
}  # fmt: skip


def plain(text: str) -> str:
    r"""Strip LaTeX from titles and abstracts so the model doesn't copy it. Backslashes are the
    real hazard: the model writes them into JSON, where "\t" or "\r" become control
    characters and eat letters ("\textit" came back as "extit")."""
    text = re.sub(r"\\([A-Za-z]+)", lambda m: _LATEX_SYMBOLS.get(m.group(1), ""), text)
    text = re.sub(r"[${}^_]", "", text)
    return " ".join(text.split())


def clean_summary(text: str) -> str:
    """Drop control characters and leftover markup from model output."""
    return " ".join(re.sub(r"[\x00-\x1f$]", " ", text).split())


def _paper_list(papers: list[SourcePaper]) -> str:
    total = sum(len(p.abstract) for p in papers)
    limit = None if total <= ABSTRACT_BUDGET_CHARS else ABSTRACT_BUDGET_CHARS // len(papers)
    parts = []
    for p in papers:
        abstract = p.abstract if limit is None else p.abstract[:limit].rsplit(" ", 1)[0] + " …"
        parts.append(f"[{p.arxiv_id}] {p.title}\n{abstract}")
    return "\n\n".join(parts)


def write_section(
    llm: ChatModel, tracer: Tracer, code: str, papers: list[SourcePaper], stats: DigestStats
) -> Section:
    allowed = {p.arxiv_id for p in papers}
    wanted = 1 if len(papers) <= 2 else min(4, 2 + len(papers) // 10)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Subfield: {SUBFIELDS[code]}. Write {wanted} highlight(s).\n\n"
            + _paper_list(papers),
        },
    ]
    highlights: list[Highlight] = []
    problems: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        # The LLM call runs inside the generation, so the trace records its real latency.
        with tracer.generation(name=f"section-{code}", model=llm.model, input=messages) as gen:
            result = llm.chat(messages, _SCHEMA)
            highlights = [
                Highlight(
                    summary=clean_summary(str(h.get("summary", ""))),
                    arxiv_ids=[normalise_id(a) for a in h.get("arxiv_ids", [])],
                )
                for h in result.content.get("highlights", [])
            ]
            problems = check_faithfulness(highlights, allowed)
            gen.update(
                output=result.content,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                metadata={"attempt": attempt, "papers": len(papers), "problems": problems},
                level="WARNING" if problems else "DEFAULT",
            )
        stats.llm_calls += 1
        stats.prompt_tokens += result.prompt_tokens
        stats.completion_tokens += result.completion_tokens
        stats.llm_seconds += result.seconds
        if not problems:
            break
        log.warning("%s attempt %d: %s", code, attempt, problems)
        if attempt < MAX_ATTEMPTS:
            stats.retries += 1
            messages += [
                {"role": "assistant", "content": json.dumps(result.content)},
                {
                    "role": "user",
                    "content": "Your answer has citation problems:\n- "
                    + "\n- ".join(problems)
                    + "\nAnswer again in the same JSON shape, citing only IDs from the list.",
                },
            ]
    if problems:
        kept = faithful_only(highlights, allowed)
        stats.dropped_highlights += len(highlights) - len(kept)
        stats.problems += [f"{code}: {p}" for p in problems]
        highlights = kept
    stats.highlights += len(highlights)
    return Section(code, SUBFIELDS[code], len(papers), highlights)


def build_digest(
    conn: psycopg.Connection, llm: ChatModel, day: date, tracer: Tracer | None = None
) -> Digest:
    tracer = tracer or NoTracer()
    stats = DigestStats()
    by_code = papers_for_day(conn, day)
    stats.papers = sum(len(p) for p in by_code.values())
    started = time.perf_counter()
    with tracer.trace(name="digest", input={"day": day.isoformat(), "papers": stats.papers}) as t:
        sections = [
            write_section(llm, tracer, code, by_code[code], stats)
            for code in SUBFIELDS
            if code in by_code
        ]
        digest = Digest(day, llm.model, sections, stats)
        total = stats.highlights + stats.dropped_highlights
        tracer.score("faithfulness", stats.highlights / total if total else 1.0)
        t.update(output=digest.markdown, metadata=asdict(stats))
    tracer.flush()
    log.info("digest %s: %s in %.0fs", day, stats, time.perf_counter() - started)
    return digest


def save_digest(conn: psycopg.Connection, digest: Digest) -> None:
    conn.execute(
        """
        INSERT INTO digests (digest_date, model, sections, markdown, stats)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (digest_date) DO UPDATE
           SET created_at = now(), model = EXCLUDED.model, sections = EXCLUDED.sections,
               markdown = EXCLUDED.markdown, stats = EXCLUDED.stats
        """,
        (
            digest.day,
            digest.model,
            json.dumps([asdict(s) for s in digest.sections]),
            digest.markdown,
            json.dumps(asdict(digest.stats)),
        ),
    )
    conn.commit()
