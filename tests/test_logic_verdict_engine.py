"""VerdictEngine: one verdict from the features it is handed."""

import pytest

from app.logic.benchmark import Benchmark
from app.logic.crime_scan import CrimeScan
from app.logic.document_evidence import DocumentEvidence
from app.logic.risk_analysis import RiskAnalysis
from app.logic.forecast import Forecast
from app.logic.verdict_engine import VerdictEngine
from app.model.check import Check
from app.model.verdict import Verdict
from tests.logic_fixtures import CONFIG, POLICY, sample_case, sample_forecast


FEATURE_KEYS = {"benchmark": "benchmark", "forecast": "forecast", "crime": "crime", "document_findings": "documents"}


def _features():
    return [CrimeScan(POLICY), DocumentEvidence(POLICY), Benchmark(POLICY, CONFIG), Forecast(POLICY, CONFIG)]


@pytest.fixture(scope="module")
def parts():
    case = sample_case()
    forecast = sample_forecast(case)
    assessment = Forecast(POLICY, CONFIG).run(case, {"forecast": forecast})
    return case, {"forecast": forecast, "forecast_assessment": assessment, "markets": forecast["markets"],
                  "declaration": forecast["declaration"]}


def test_the_engine_keeps_the_features_it_was_handed():
    features = _features()
    engine = VerdictEngine(features, CONFIG)
    assert engine.features() == features
    assert all(isinstance(feature, RiskAnalysis) for feature in engine.features())


def test_decide_gives_one_outcome_with_checks_from_every_feature(parts):
    case, data = parts
    verdict = VerdictEngine(_features(), CONFIG).decide(case, data)
    assert verdict["verdict"] in Verdict.OUTCOMES
    for key, name in FEATURE_KEYS.items():
        assert verdict[key] and all(check["feature"] == name for check in verdict[key])


def test_the_same_inputs_always_give_the_same_verdict(parts):
    case, data = parts
    first = VerdictEngine(_features(), CONFIG).decide(case, data)
    second = VerdictEngine(_features(), CONFIG).decide(case, data)
    assert first == second


def test_a_feature_the_engine_was_not_given_adds_no_findings(parts):
    case, data = parts
    features = [feature for feature in _features() if feature.NAME != "crime"]
    verdict = VerdictEngine(features, CONFIG).decide(case, data)
    assert verdict["crime"] == []
    assert verdict["forecast"]


class _AlwaysFails(RiskAnalysis):
    """A made-up benchmark, to show the engine treats any RiskAnalysis the same way."""

    NAME = "benchmark"

    def run(self, case: dict, ai_data: dict) -> dict:
        return {}

    def checks(self, context: dict) -> list[Check]:
        return [self._check("TOTAL_WEALTH", "Total wealth", "wealth", "failed", "Made-up failure.")]


def test_the_engine_uses_whatever_feature_it_is_handed(parts):
    case, data = parts
    features = [_AlwaysFails(POLICY) if feature.NAME == "benchmark" else feature for feature in _features()]
    verdict = VerdictEngine(features, CONFIG).decide(case, data)
    assert [(check["check"], check["detail"]) for check in verdict["benchmark"]] == [
        ("TOTAL_WEALTH", "Made-up failure.")]


def test_with_nothing_run_each_feature_reports_skipped_and_nothing_crashes():
    verdict = VerdictEngine(_features(), CONFIG).decide(sample_case(), {})
    statuses = {check["check"]: check["status"] for key in FEATURE_KEYS for check in verdict[key]}
    assert statuses["FORECAST"] == "skipped"
    assert statuses["CRIME_SCAN"] == "skipped"
    assert statuses["PEER_BENCHMARK"] == "skipped"


def test_the_report_lists_the_verdict_for_the_screen(parts):
    case, data = parts
    engine = VerdictEngine(_features(), CONFIG)
    report = engine.report(engine.decide(case, data))
    assert set(report) == {"header", "sections", "evidence", "evidence_titles", "legend"}
    assert report["legend"] == VerdictEngine.REPORT_LEGEND



def test_a_verdict_where_nothing_ran_is_manual_review_not_passed():
    verdict = VerdictEngine(_features(), CONFIG).decide(sample_case(), {})
    assert verdict["verdict"] == "MANUAL_REVIEW"
    assert any("nothing was checked" in reason["text"] for reason in verdict["reasons"])


def test_a_verdict_where_a_feature_ran_does_not_get_the_nothing_ran_reason():
    case = sample_case()
    verdict = VerdictEngine(_features(), CONFIG).decide(case, {"forecast": sample_forecast(case)})
    assert not any("nothing was checked" in reason["text"] for reason in verdict["reasons"])


class _MadeUp(RiskAnalysis):
    """A made-up feature that hands the engine the Check objects it was given."""

    def __init__(self, name: str, checks: list[Check]) -> None:
        super().__init__(POLICY)
        self.NAME = name
        self.__checks = checks

    def run(self, case: dict, ai_data: dict) -> dict:
        return {}

    def checks(self, context: dict) -> list[Check]:
        return list(self.__checks)


def _made_up_checks() -> dict:
    """Checks with every kind of field: sources and supports, and the extra details the rules read."""
    people = Check("benchmark", "COUNTERPARTIES", "Counterparties", "people", "failed", "2 not usual",
                   "Not explained: not linked.", extra={"independent": True, "optional": False})
    countries = Check("benchmark", "JURISDICTION", "Countries", "countries", "failed", "Panama",
                      extra={"independent": True, "optional": False})
    gap = Check("benchmark", "UNEXPLAINED_GAP", "Unexplained gap", "wealth", "failed", "S$9M",
                extra={"independent": False, "optional": False})
    pattern = Check("crime", "TYPOLOGY", "Trade-based laundering [R1]", "pattern", "weak", "Partial match",
                    group="Patterns", extra={"signs": ["counterparty_unnamed"], "match": "critical",
                                             "typology_id": "tbml"})
    income = Check("documents", "UNDECLARED_INCOME", "Income not declared", "sources", "weak", "Consulting fees.",
                   group="Documents", sources=["bank.pdf"], supports=[])
    return {"benchmark": [people, countries, gap], "crime": [pattern], "documents": [income]}


def _made_up_verdict(checks: dict) -> dict:
    features = [_MadeUp(name, rows) for name, rows in checks.items()] + [Forecast(POLICY, CONFIG)]
    return VerdictEngine(features, CONFIG).decide(sample_case(), {"benchmark_ai": {"expected_wealth": 1}})


def test_the_verdict_keeps_every_field_of_every_check():
    checks = _made_up_checks()
    verdict = _made_up_verdict(checks)
    for key, name in (("benchmark", "benchmark"), ("crime", "crime"), ("document_findings", "documents")):
        assert verdict[key] == [check.to_dict() for check in checks[name]]
        assert all(type(row) is dict for row in verdict[key])          # the saved layout, not objects
    assert verdict["document_findings"][0]["sources"] == ["bank.pdf"]
    assert verdict["document_findings"][0]["supports"] == []
    assert verdict["crime"][0]["signs"] == ["counterparty_unnamed"]


def test_the_rules_read_the_extra_details_on_the_check_objects():
    verdict = _made_up_verdict(_made_up_checks())
    texts = [reason["text"] for reason in verdict["reasons"]]
    # only the two independent benchmark failures count; the forecast-derived gap does not
    assert "Benchmark check(s) failed that the forecast can't explain: counterparties, countries." in texts
    # the crime check's match and typology id: a critical pattern no crime story was built from
    assert 'Known pattern "Trade-based laundering": Partial match.' in texts
    assert "His documents show things to check: income not declared." in texts


def test_agreement_groups_check_objects_by_theme_and_reads_the_warning_signs():
    verdict = _made_up_verdict(_made_up_checks())
    people = next(entry for entry in verdict["agreement"] if entry["theme"] == "people")
    assert people["features"] == ["benchmark", "crime"]
    assert people["lines"] == ["Benchmark: Counterparties - 2 not usual",
                               "Crime: Trade-based laundering [R1] - warning signs fired: money from unnamed people"]
    assert [entry["theme"] for entry in verdict["agreement"]][0] == "people"


def test_documents_to_request_come_from_the_failed_check_objects():
    verdict = _made_up_verdict(_made_up_checks())
    names = CONFIG.vocabulary["document_codes"]
    assert verdict["documents"] == [
        {"document": names["DOC_TAX_RETURNS"], "reason": "His documents show: income not declared"},
        {"document": names["DOC_CONSULTING_AGREEMENT"], "reason": "His documents show: income not declared"},
        {"document": names["DOC_BANK_STATEMENTS"], "reason": "Benchmark check failed: counterparties"},
        {"document": names["DOC_BENEFICIAL_OWNERSHIP"], "reason": "Benchmark check failed: countries"}]


def test_pay_taken_from_documents_is_added_as_a_forecast_check(parts):
    case, data = parts
    adjusted = {"ai_pay": 100_000, "documented_pay": 150_000, "year": 2025, "source_file": "tax.pdf",
                "job": "COO", "ratio": 1.5}
    verdict = VerdictEngine(_features(), CONFIG).decide(case, {**data, "pay_adjustments": [adjusted]})
    pay = verdict["forecast"][1]
    assert (pay["feature"], pay["check"], pay["status"], pay["group"]) == (
        "forecast", "PAY_FROM_DOCUMENTS", "info", "Pay taken from his documents")
    assert "scaled x1.5" in pay["detail"]
