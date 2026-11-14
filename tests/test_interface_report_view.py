"""ReportView: the layout of what the officer reads."""

from app.interface.console_ui import ConsoleUI
from app.interface.report_view import ReportView
from app.logic.benchmark import Benchmark
from app.logic.crime_scan import CrimeScan
from app.logic.document_evidence import DocumentEvidence
from app.logic.forecast import Forecast
from app.logic.verdict_engine import VerdictEngine
from tests.logic_fixtures import CONFIG, POLICY, sample_case, sample_forecast


def _view():
    return ReportView(ConsoleUI())


def _report():
    case = sample_case()
    forecast = sample_forecast(case)
    feature = Forecast(POLICY, CONFIG)
    assessment = feature.run(case, {"forecast": forecast})
    engine = VerdictEngine([CrimeScan(POLICY), DocumentEvidence(POLICY), Benchmark(POLICY, CONFIG), feature], CONFIG)
    verdict = engine.decide(case, {"forecast": forecast, "forecast_assessment": assessment,
                                   "markets": forecast["markets"], "declaration": forecast["declaration"]})
    return verdict, engine.report(verdict)


def test_the_verdict_report_names_the_client_and_the_verdict():
    verdict, report = _report()
    text = _view().format_verdict_report(report)
    assert verdict["client_ref"] in text
    assert verdict["verdict_label"] in text


def test_the_evidence_is_laid_out_under_its_titles():
    _, report = _report()
    text = _view().format_evidence(report)
    assert all(title in text for title in report["evidence_titles"][:1])


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
    _view().display_client_record({"client_ref": "SOW-1", "name": "Daniel Tan", "nationality": "Malaysian",
                                   "career": {"occupation": "COO"}, "career_history": [], "investments": [],
                                   "claims": {}, "sow_declaration": "Salary savings."})
    out = capsys.readouterr().out
    assert "Daniel Tan" in out and "SOW-1" in out
