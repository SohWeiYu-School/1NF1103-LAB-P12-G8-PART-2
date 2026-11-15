"""ResearchReport: one published report the research AI found."""

import pytest

from app.model.research_report import ResearchReport

REPLY_REPORT = {"organisation": "FATF", "title": "Trade-Based Money Laundering", "year": 2020,
                "url": "https://www.fatf-gafi.org/tbml", "excerpts": ["Over-invoicing is used."],
                "summary": ["Over-invoicing", "Third-party payments"], "report_id": "R1"}


def test_report_domain_comes_from_its_url():
    report = ResearchReport("R1", "https://www.FATF-gafi.org/publications/x.html", [])
    assert report.domain() == "www.fatf-gafi.org"
    assert ResearchReport("R2", "", []).domain() == ""


def test_a_quote_is_found_despite_case_spacing_and_curly_marks():
    report = ResearchReport("R1", "https://mas.gov.sg/x", ["Shell   companies are “often” used – widely."])
    assert report.contains_quote('shell companies are "often" used - widely')
    assert not report.contains_quote("shell companies are rarely used")


def test_a_report_with_no_excerpts_contains_no_quote():
    assert not ResearchReport("R1", "https://mas.gov.sg/x").contains_quote("anything")


def test_a_report_reads_every_field_of_the_research_reply():
    report = ResearchReport.from_dict(REPLY_REPORT, "2026-10-01T00:00:00+00:00")
    assert (report.report_id, report.url, report.organisation, report.title, report.year) == (
        "R1", "https://www.fatf-gafi.org/tbml", "FATF", "Trade-Based Money Laundering", 2020)
    assert report.excerpts == ["Over-invoicing is used."]
    assert report.summary == ["Over-invoicing", "Third-party payments"]
    assert report.retrieved_at == "2026-10-01T00:00:00+00:00"
    assert report.retrieved_year() == 2026


def test_to_dict_gives_back_the_reply_layout_in_the_same_order():
    saved = ResearchReport.from_dict(REPLY_REPORT, "2026-10-01").to_dict()
    assert saved == REPLY_REPORT
    assert list(saved) == ["organisation", "title", "year", "url", "excerpts", "summary", "report_id"]
    assert "retrieved_at" not in saved                     # the time belongs to the research, not the report


def test_a_year_that_is_not_a_number_is_kept_as_unknown():
    assert ResearchReport.from_dict({**REPLY_REPORT, "year": "2020?"}).year is None
    assert ResearchReport.from_dict({"report_id": "R1"}).year is None
    assert ResearchReport.from_dict({**REPLY_REPORT, "year": 0}).year == 0     # the crime scan warns about it


def test_research_with_no_readable_time_has_year_zero():
    assert ResearchReport("R1").retrieved_year() == 0
    assert ResearchReport("R1", retrieved_at="soon").retrieved_year() == 0


def test_the_report_cannot_be_changed_from_outside():
    report = ResearchReport.from_dict(REPLY_REPORT)
    report.excerpts.append("made up")
    report.to_dict()["excerpts"].append("made up")
    assert report.excerpts == ["Over-invoicing is used."]


@pytest.mark.parametrize("bad", [{"report_id": 1}, {"url": ["https://x"]}, {"excerpts": "one excerpt"},
                                 {"organisation": 5}, {"summary": {"a": 1}}])
def test_impossible_values_are_rejected_with_a_clear_message(bad):
    with pytest.raises(ValueError, match="research report"):
        ResearchReport.from_dict({**REPLY_REPORT, **bad})


def test_a_report_that_is_not_an_object_is_rejected():
    with pytest.raises(ValueError, match="JSON object"):
        ResearchReport.from_dict(["R1"])
