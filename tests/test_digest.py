from datetime import date

import psycopg
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from night_sky_digest.api import app, get_pool
from night_sky_digest.digest import (
    ChatResult,
    DigestStats,
    Highlight,
    SourcePaper,
    build_digest,
    check_faithfulness,
    normalise_id,
    papers_for_day,
    plain,
    save_digest,
    write_section,
)
from night_sky_digest.ingest.oai import Paper
from night_sky_digest.ingest.store import store_page
from night_sky_digest.tracing import NoTracer

DAY = date(2026, 10, 8)
ALLOWED = {"2610.00001", "2610.00002"}


class ScriptedChat:
    """Returns the scripted JSON answers in order and remembers the messages it got."""

    model = "scripted"

    def __init__(self, answers: list[dict]) -> None:
        self.answers = list(answers)
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict], schema: dict) -> ChatResult:
        self.calls.append(list(messages))
        return ChatResult(self.answers.pop(0), prompt_tokens=100, completion_tokens=20, seconds=1)


def answer(*highlights: tuple[str, list[str]]) -> dict:
    return {"highlights": [{"summary": s, "arxiv_ids": ids} for s, ids in highlights]}


# --- faithfulness ---------------------------------------------------------------------------


def test_faithful_highlights_pass() -> None:
    hs = [Highlight("Two papers agree.", ["2610.00001", "2610.00002"])]
    assert check_faithfulness(hs, ALLOWED) == []


def test_unknown_citation_is_flagged() -> None:
    problems = check_faithfulness([Highlight("Claim.", ["2610.99999"])], ALLOWED)
    assert problems == ["Highlight 1 cites 2610.99999, which is not in the list."]


def test_highlight_without_citation_is_flagged() -> None:
    assert check_faithfulness([Highlight("Uncited claim.", [])], ALLOWED) == [
        "Highlight 1 cites no paper."
    ]


def test_ids_inside_the_summary_count_as_citations() -> None:
    hs = [Highlight("As shown in 2509.12345, this works.", ["2610.00001"])]
    assert check_faithfulness(hs, ALLOWED) == [
        "Highlight 1 mentions 2509.12345, which is not in the list."
    ]


def test_normalise_id_strips_prefix_and_version() -> None:
    assert normalise_id("arXiv:2610.00001v3") == "2610.00001"
    assert normalise_id(" astro-ph/0601001v1 ") == "astro-ph/0601001"


# --- retries ----------------------------------------------------------------------------------

PAPERS = [SourcePaper("2610.00001", "A", "Abstract A."), SourcePaper("2610.00002", "B", "Abs B.")]


def test_bad_citation_triggers_a_retry_with_feedback() -> None:
    llm = ScriptedChat([answer(("Made up.", ["2610.99999"])), answer(("Real.", ["2610.00001"]))])
    stats = DigestStats()
    section = write_section(llm, NoTracer(), "HE", PAPERS, stats)
    assert [h.arxiv_ids for h in section.highlights] == [["2610.00001"]]
    assert stats.retries == 1 and stats.llm_calls == 2 and stats.dropped_highlights == 0
    assert "2610.99999" in llm.calls[1][-1]["content"]  # the feedback names the bad ID


def test_still_unfaithful_after_retries_drops_only_bad_highlights() -> None:
    bad = answer(("Fine.", ["2610.00002"]), ("Invented.", ["1234.56789"]))
    llm = ScriptedChat([bad, bad, bad])
    stats = DigestStats()
    section = write_section(llm, NoTracer(), "HE", PAPERS, stats)
    assert [h.summary for h in section.highlights] == ["Fine."]
    assert stats.llm_calls == 3 and stats.dropped_highlights == 1 and stats.problems


# --- end to end -------------------------------------------------------------------------------


def paper(arxiv_id: str, category: str, created: date = DAY) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title=f"Title {arxiv_id}",
        abstract="An abstract.",
        authors=["A. Astronomer"],
        categories=[category],
        created=created,
        updated=None,
        datestamp=created,
        license=None,
        doi=None,
        comments=None,
    )


def test_build_save_and_serve_digest(conn: psycopg.Connection, db_url: str) -> None:
    store_page(
        conn,
        [
            paper("2610.00001", "astro-ph.HE"),
            paper("2610.00002", "astro-ph.GA"),
            paper("2610.00003", "gr-qc"),  # cross-list, not astro-ph primary: excluded
            paper("2610.00004", "astro-ph.HE", created=date(2026, 10, 7)),  # other day
        ],
    )
    conn.commit()
    # Sections are written in SUBFIELDS order: GA before HE.
    llm = ScriptedChat(
        [answer(("Galaxy news.", ["2610.00002"])), answer(("HE news.", ["2610.00001"]))]
    )
    digest = build_digest(conn, llm, DAY)
    assert [s.code for s in digest.sections] == ["GA", "HE"]
    assert digest.stats.papers == 2
    assert "[2610.00001](https://arxiv.org/abs/2610.00001)" in digest.markdown
    save_digest(conn, digest)
    save_digest(conn, digest)  # re-running a day replaces it

    with ConnectionPool(db_url, min_size=1, max_size=1) as pool:
        app.dependency_overrides[get_pool] = lambda: pool
        try:
            client = TestClient(app)
            latest = client.get("/digest/latest")
            md = client.get(f"/digest/{DAY.isoformat()}.md")
            missing = client.get("/digest/2020-01-01")
        finally:
            app.dependency_overrides.clear()
    assert latest.status_code == 200 and latest.json()["date"] == DAY.isoformat()
    assert md.status_code == 200 and md.text.startswith("# Night Sky Digest: 2026-10-08")
    assert missing.status_code == 404


def test_new_papers_exclude_revisions_and_keep_held_papers(conn: psycopg.Connection) -> None:
    store_page(
        conn,
        [
            paper("2610.00001", "astro-ph.HE"),
            paper("2609.09999", "astro-ph.HE"),  # held in moderation, announced in October: new
            paper("2412.03461", "astro-ph.HE"),  # revision of a 2024 paper: not new
        ],
    )
    conn.commit()
    ids = [p.arxiv_id for p in papers_for_day(conn, DAY)["HE"]]
    assert ids == ["2609.09999", "2610.00001"]


def test_plain_strips_latex() -> None:
    assert plain(r"$\Lambda$CDM with $M_{\rm BH}$ at $z \sim 7$") == "ΛCDM with M BH at z ~ 7"
