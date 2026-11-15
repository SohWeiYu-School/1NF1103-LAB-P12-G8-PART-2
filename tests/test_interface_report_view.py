"""ReportView: the layout of what the officer reads."""

import pytest

from app.interface.console_ui import ConsoleUI
from app.interface.report_view import ReportView
from app.logic.benchmark import Benchmark
from app.logic.crime_scan import CrimeScan
from app.logic.document_evidence import DocumentEvidence
from app.logic.forecast import Forecast
from app.logic.verdict_engine import VerdictEngine
from app.model.client_record import ClientRecord
from tests import fake_ai
from tests.logic_fixtures import CONFIG, POLICY, sample_case, sample_forecast


def _view():
    return ReportView(ConsoleUI())


def _report():
    case = sample_case()
    forecast = sample_forecast(case)
    feature = Forecast(POLICY, CONFIG)
    assessment = feature.run(case, {"forecast": forecast})
    engine = VerdictEngine([CrimeScan(POLICY), DocumentEvidence(POLICY), Benchmark(POLICY, CONFIG), feature], CONFIG)
    return engine.combine(case, {"forecast": forecast, "forecast_assessment": assessment,
                                 "markets": forecast["markets"], "declaration": forecast["declaration"]})


def test_the_verdict_report_names_the_client_and_the_verdict():
    verdict = _report()
    text = _view().format_verdict_report(verdict)
    assert verdict.client_ref in text
    assert verdict.explanation["verdict_label"] in text
    assert verdict.next_step in text and verdict.next_review_date in text
    for part in verdict.report["sections"]:
        if part["items"] and part["title"] != "Crime - known patterns for his industry":
            assert part["title"].upper() in text


def test_the_report_is_read_from_the_verdict_object():
    verdict = _report()
    verdict.report = {**verdict.report, "header": {**verdict.report["header"], "summary": "Summary from the report."}}
    assert "Summary from the report." in _view().format_verdict_report(verdict)


def test_the_evidence_is_laid_out_under_its_titles():
    verdict = _report()
    text = _view().format_evidence(verdict)
    assert verdict.client_ref in text
    assert all(title in text for title in verdict.report["evidence_titles"])


def test_showing_a_verdict_prints_the_report_then_asks_for_the_evidence(capsys, monkeypatch):
    verdict = _report()
    asked = []
    monkeypatch.setattr("builtins.input", lambda question="": asked.append(question) or "y")
    _view().show_verdict_report(verdict)
    out = capsys.readouterr().out
    assert "COMBINED ASSESSMENT" in out and "FULL EVIDENCE  " in out
    assert out.index("FULL EVIDENCE  ") > out.index("COMBINED ASSESSMENT")
    assert any("Show the full evidence?" in question for question in asked)


def test_the_evidence_is_not_offered_when_not_asked_for(capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda question="": (_ for _ in ()).throw(AssertionError(question)))
    _view().show_verdict_report(_report(), ask_for_evidence=False)
    assert "FULL EVIDENCE  " not in capsys.readouterr().out


def test_an_empty_assessment_list_says_so():
    assert _view().format_assessment_list([]) == "No saved assessments match."


def test_the_assessment_list_shows_one_line_per_assessment():
    records = [{"client_ref": "SOW-1", "kind": "combined", "verdict": {"assessed_on": "2026-09-24", "verdict": "RISKY"}},
               {"client_ref": "SOW-2", "kind": "onboarding", "assessment": {"assessed_on": "2026-09-25", "outcome": "PASSED"}}]
    lines = _view().format_assessment_list(records).splitlines()
    assert len(lines) == 3
    assert "SOW-1" in lines[1] and ReportView.OUTCOME_LABELS["RISKY"] in lines[1]
    assert "2026-09-25" in lines[2]


def test_showing_a_client_record_prints_through_the_console(capsys):
    record = ClientRecord.from_dict({"client_ref": "SOW-1", "name": "Daniel Tan", "nationality": "Malaysian",
                                     "career": {"occupation": "COO"}, "career_history": [], "investments": [],
                                     "claims": {}, "sow_declaration": "Salary savings."})
    assert _view().display_client_record(record) is None
    out = capsys.readouterr().out
    assert "Daniel Tan" in out and "SOW-1" in out and "Salary savings." in out


def test_a_client_record_lists_its_claim_problems_to_fix(capsys):
    record = ClientRecord.from_dict({"client_ref": "SOW-1", "name": "Daniel Tan", "nationality": "Malaysian",
                                     "career": {"occupation": "COO"}, "career_history": [], "investments": [],
                                     "claims": {"pep_status": ""}, "sow_declaration": "Salary savings."})
    _view().display_client_record(record)
    out = capsys.readouterr().out
    assert "TO FIX" in out
    assert "The PEP question is not answered" in out and "Declared net worth is missing: enter an amount greater than 0." in out


def test_a_complete_client_record_shows_nothing_to_fix(capsys):
    _view().display_client_record(ClientRecord.from_dict(sample_case()))
    assert "TO FIX" not in capsys.readouterr().out


def test_a_client_record_shows_every_job_asset_and_document(capsys):
    _view().display_client_record(ClientRecord.from_dict({**sample_case(), "supporting_documents": [
        {"file_name": "payslip.pdf", "file_id": "f1"}]}))
    out = capsys.readouterr().out
    assert "--- Job 2 ---" in out and "--- Investment 1 ---" in out
    assert "present (current job)" in out
    assert "1. payslip.pdf" in out and "File ID: f1" in out


UNNAMED = {"sources": [{"source_id": "S1", "source_type": "advisory_fees", "counterparty": None,
                        "amount_sgd": None, "occupation_mismatch": False, "jurisdiction": "HK"}]}


def _crime_scan():
    """The crime scan's own objects for the sample: the verified Typologies and the crime result."""
    scan = CrimeScan(POLICY)
    typologies = scan.verify_typology_sources(fake_ai.typologies()["sector_typologies"],
                                              scan.verify_research(fake_ai.research()))
    return typologies, scan.run(sample_case(), {"typologies": typologies, "declaration": UNNAMED})


def test_the_crime_section_is_laid_out_from_the_typology_objects():
    typologies, crime_result = _crime_scan()
    text = _view().format_verdict_report(_report(), crime_result=crime_result, typologies=typologies)
    typology = typologies[0]
    assert "CRIME - KNOWN PATTERNS FOR HIS INDUSTRY" in text
    assert "1 typologies  \u00b7  1 matched  \u00b7  0 no match" in text
    assert f"[HIGH MATCH]  {typology.name}" in text
    assert "    Core:        \u2713 Money from unnamed counterparty" in text
    assert "    Supporting:  \u2713 Source with no declared amount" in text
    assert typology.description.split(".")[0] in text                       # read from the Typology
    assert f'"{typology.source_quotes[0]["quote"]}"  [R1]' in text


def test_an_unchecked_typology_is_marked_in_the_crime_section():
    typologies, crime_result = _crime_scan()
    unchecked = CrimeScan(POLICY).read_typologies(fake_ai.typologies()["sector_typologies"])
    crime_result = CrimeScan(POLICY).run(sample_case(), {"typologies": unchecked, "declaration": UNNAMED})
    text = _view().format_verdict_report(_report(), crime_result=crime_result, typologies=unchecked)
    assert f"[HIGH MATCH]  {unchecked[0].name}  (not checked against research)" in text
    checked = _view().format_verdict_report(_report(), crime_result=_crime_scan()[1], typologies=typologies)
    assert "not checked against research" not in checked
    # the mark comes from the match's own typology, so it shows even without the typology list
    without_list = _view().format_verdict_report(_report(), crime_result=crime_result, typologies=[])
    assert "(not checked against research)" in without_list


def test_a_match_whose_typology_is_not_listed_shows_no_description_or_quote():
    typologies, crime_result = _crime_scan()
    text = _view().format_verdict_report(_report(), crime_result=crime_result, typologies=[])
    assert f"[HIGH MATCH]  {typologies[0].name}" in text
    assert typologies[0].description.split(".")[0] not in text
    assert typologies[0].source_quotes[0]["quote"] not in text


def test_the_report_is_laid_out_at_the_width_it_is_given():
    """96 characters unless another width is handed in; the crime section follows the same width."""
    typologies, crime_result = _crime_scan()
    for width in (96, 60):
        view = ReportView(ConsoleUI(), width) if width != 96 else _view()
        text = view.format_verdict_report(_report(), crime_result=crime_result, typologies=typologies)
        text += "\n" + view.format_evidence(_report())
        assert "═" * width + "\n" in text and "═" * (width + 1) not in text
        assert "  " + "─" * (width - 2) in text


@pytest.mark.parametrize("width", [0, 19, 60.5, True, "96"])
def test_an_impossible_report_width_is_refused(width):
    with pytest.raises(ValueError, match="the report width must be a whole number of at least 20"):
        ReportView(ConsoleUI(), width)


def test_show_client_list_says_so_when_no_clients_are_saved(capsys):
    _view().show_client_list([])
    assert "No clients saved yet." in capsys.readouterr().out


def test_show_client_list_has_a_row_for_every_client(capsys):
    _view().show_client_list([
        {"client_ref": "CL-1", "name": "Ada Tan", "career": {"industry": "Banking"}},
        {"client_ref": "CL-2", "client_profile": {"full_name": "Ben Lim", "industry": "Shipping"}}])
    shown = capsys.readouterr().out
    assert "CL-1" in shown and "Ada Tan" in shown and "Banking" in shown
    assert "CL-2" in shown and "Ben Lim" in shown and "Shipping" in shown
