from datetime import date
from pathlib import Path

import pytest

from night_sky_digest.ingest.oai import Deleted, OAIError, Paper, parse_page

FIXTURES = Path(__file__).parent / "fixtures" / "oai"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_first_page_has_records_and_token() -> None:
    page = parse_page(load("list_records_first.xml"))
    assert [r.arxiv_id for r in page.records] == ["2406.10062", "2411.16879", "2509.02895"]
    assert page.resumption_token is not None
    assert page.resumption_token.startswith("verb%3DListRecords")


def test_paper_fields() -> None:
    paper = parse_page(load("list_records_first.xml")).records[0]
    assert isinstance(paper, Paper)
    assert paper.title.startswith("Phase transitions, shadows, and microstructure")
    assert "Reissner-Nordström" in paper.title
    assert "\n" not in paper.abstract and "  " not in paper.abstract
    assert paper.authors == ["Jose M. Ladino", "Carlos E. Romero-Figueroa", "Hernando Quevedo"]
    assert paper.created == date(2024, 7, 2)
    assert paper.updated == date(2026, 10, 8)
    assert paper.datestamp == date(2026, 10, 8)


def test_cross_listed_paper_keeps_its_own_primary_category() -> None:
    # In the astro-ph set, but primary category is gr-qc.
    paper = parse_page(load("list_records_first.xml")).records[0]
    assert isinstance(paper, Paper)
    assert paper.primary_category == "gr-qc"
    assert "astro-ph.HE" in paper.categories


def test_last_page_empty_token_and_deleted_record() -> None:
    page = parse_page(load("list_records_last.xml"))
    assert page.resumption_token is None
    assert page.records[-1] == Deleted(arxiv_id="2510.00001", datestamp=date(2026, 10, 8))


def test_missing_token_element_means_last_page() -> None:
    assert parse_page(load("list_records_no_token.xml")).resumption_token is None


def test_no_records_match_is_an_empty_last_page() -> None:
    page = parse_page(load("no_records_match.xml"))
    assert page.records == [] and page.resumption_token is None


def test_bad_resumption_token_raises() -> None:
    with pytest.raises(OAIError) as exc:
        parse_page(load("bad_resumption_token.xml"))
    assert exc.value.code == "badResumptionToken"
