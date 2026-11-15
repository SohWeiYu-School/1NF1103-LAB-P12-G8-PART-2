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
from tests import fake_ai
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


def test_combine_gives_one_verdict_object_with_checks_from_every_feature(parts):
    case, data = parts
    verdict = VerdictEngine(_features(), CONFIG).combine(case, data)
    assert isinstance(verdict, Verdict)
    assert verdict.outcome in Verdict.OUTCOMES
    assert {check.feature for check in verdict.checks()} == set(FEATURE_KEYS.values())
    details = verdict.details()
    assert details["verdict"] == verdict.outcome
    for key, name in FEATURE_KEYS.items():
        assert details[key] and all(check["feature"] == name for check in details[key])


def test_the_verdict_lists_every_check_once_in_feature_order(parts):
    case, data = parts
    verdict = VerdictEngine(_features(), CONFIG).combine(case, data)
    details = verdict.details()
    assert [check.to_dict() for check in verdict.checks()] == (
        details["benchmark"] + details["forecast"] + details["crime"] + details["document_findings"])


def test_combine_keeps_the_id_time_notes_and_what_did_not_run(parts):
    case, data = parts
    verdict = VerdictEngine(_features(), CONFIG).combine(case, {
        **data, "assessment_id": "a-1", "assessed_at": "2026-09-24T01:02:03+00:00",
        "notes": ["a warning from the run"], "not_run": ["The peer benchmark"]})
    assert (verdict.assessment_id, verdict.client_ref, verdict.assessed_at) == (
        "a-1", case["client_ref"], "2026-09-24T01:02:03+00:00")
    assert verdict.notes == ["a warning from the run"]
    assert verdict.not_run == ["The peer benchmark"]
    assert verdict.next_step == POLICY["routing"][verdict.outcome]
    assert verdict.next_review_date > case["current_date"]
    assert verdict.explanation["assessed_on"] == case["current_date"]
    assert verdict.explanation["verdict_label"] == VerdictEngine.VERDICT_LABELS[verdict.outcome]
    assert verdict.explanation["policy_version"] == POLICY["policy_version"]
    could_not_run = next(s for s in verdict.report["sections"] if s["title"] == "Could not run")
    assert [item["text"] for item in could_not_run["items"]] == ["The peer benchmark"]
    assert "Warnings from the run" in verdict.report["evidence_titles"]


def test_the_same_inputs_always_give_the_same_verdict(parts):
    case, data = parts
    first = VerdictEngine(_features(), CONFIG).combine(case, data)
    second = VerdictEngine(_features(), CONFIG).combine(case, data)
    assert first.details() == second.details()
    assert first.report == second.report


def test_a_feature_the_engine_was_not_given_adds_no_findings(parts):
    case, data = parts
    features = [feature for feature in _features() if feature.NAME != "crime"]
    verdict = VerdictEngine(features, CONFIG).combine(case, data).details()
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
    verdict = VerdictEngine(features, CONFIG).combine(case, data).details()
    assert [(check["check"], check["detail"]) for check in verdict["benchmark"]] == [
        ("TOTAL_WEALTH", "Made-up failure.")]


def test_with_nothing_run_each_feature_reports_skipped_and_nothing_crashes():
    verdict = VerdictEngine(_features(), CONFIG).combine(sample_case(), {}).details()
    statuses = {check["check"]: check["status"] for key in FEATURE_KEYS for check in verdict[key]}
    assert statuses["FORECAST"] == "skipped"
    assert statuses["CRIME_SCAN"] == "skipped"
    assert statuses["PEER_BENCHMARK"] == "skipped"


def test_the_report_lists_the_verdict_for_the_screen(parts):
    case, data = parts
    verdict = VerdictEngine(_features(), CONFIG).combine(case, data)
    report = verdict.report
    assert set(report) == {"header", "sections", "evidence", "evidence_titles", "legend"}
    assert report["legend"] == VerdictEngine.REPORT_LEGEND
    details = verdict.details()
    assert report["header"] == {key: details[key] for key in (
        "client_ref", "name", "assessed_on", "verdict", "verdict_label", "next_step", "next_review_date",
        "summary", "policy_version")}
    assert report["evidence"] == details["evidence"]
    assert report["evidence_titles"] == [part["title"] for part in details["evidence"]]
    why = report["sections"][0]
    assert why["title"] == "Why" and len(why["items"]) >= len(details["reasons"])
    clean = next(s for s in report["sections"] if s["title"] == "What came back clean")
    assert [item["text"] for item in clean["items"]] == (details["clean"] or ["Nothing came back fully clean."])



def test_a_verdict_where_nothing_ran_is_manual_review_not_passed():
    verdict = VerdictEngine(_features(), CONFIG).combine(sample_case(), {}).details()
    assert verdict["verdict"] == "MANUAL_REVIEW"
    assert any("nothing was checked" in reason["text"] for reason in verdict["reasons"])


def test_a_verdict_where_a_feature_ran_does_not_get_the_nothing_ran_reason():
    case = sample_case()
    verdict = VerdictEngine(_features(), CONFIG).combine(case, {"forecast": sample_forecast(case)}).details()
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
    return VerdictEngine(features, CONFIG).combine(sample_case(), {"benchmark_ai": {"expected_wealth": 1}}).details()


def test_the_verdict_holds_the_very_check_objects_the_features_made():
    checks = _made_up_checks()
    features = [_MadeUp(name, rows) for name, rows in checks.items()] + [Forecast(POLICY, CONFIG)]
    verdict = VerdictEngine(features, CONFIG).combine(sample_case(), {"benchmark_ai": {"expected_wealth": 1}})
    held = verdict.checks()
    for name in ("benchmark", "crime", "documents"):
        assert [check for check in held if check.feature == name] == checks[name]   # the same objects


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
    verdict = VerdictEngine(_features(), CONFIG).combine(case, {**data, "pay_adjustments": [adjusted]}).details()
    pay = verdict["forecast"][1]
    assert (pay["feature"], pay["check"], pay["status"], pay["group"]) == (
        "forecast", "PAY_FROM_DOCUMENTS", "info", "Pay taken from his documents")
    assert "scaled x1.5" in pay["detail"]


UNNAMED = {"sources": [{"source_id": "S1", "source_type": "advisory_fees", "counterparty": None,
                        "amount_sgd": None, "occupation_mismatch": False, "jurisdiction": "HK"}]}


def test_the_crime_scan_objects_feed_the_person_types_evidence_and_documents(parts):
    case, data = parts
    scan = CrimeScan(POLICY)
    reports = scan.verify_research(fake_ai.research())
    typologies = scan.verify_typology_sources(fake_ai.typologies()["sector_typologies"], reports)
    crime_result = scan.run(case, {"typologies": typologies, "declaration": UNNAMED})
    verdict = VerdictEngine(_features(), CONFIG).combine(case, {
        **data, "reports": reports, "typologies": typologies, "crime_result": crime_result})
    typology = typologies[0]

    t2 = next(row for row in verdict.explanation["types"] if row["typology_id"] == typology.typology_id)
    assert (t2["typology_name"], t2["match"], t2["source_ids"]) == (typology.name, "high", ["R1"])
    assert t2["quote"] == typology.source_quotes[0]
    assert t2["fired"] == ["counterparty_unnamed", "unvalued_source_present"]

    evidence = {part["title"]: part["lines"] for part in verdict.explanation["evidence"]}
    assert evidence["Research reports"] == ["[R1] FATF (2020) - Trade-Based Money Laundering"]
    assert evidence["Sector typologies"] == [
        f"{typology.name} ({CONFIG.category_name(typology.crime_category)})", f"    {typology.description}"]

    asked = {entry["document"]: entry["reason"] for entry in verdict.explanation["documents"]}
    assert verdict.outcome != "PASSED"
    for document in typology.typical_documents:              # Freight invoices, Bills of lading
        assert asked[document] == f"Matches the known pattern: {typology.name}"


def test_with_no_research_the_evidence_says_no_reports_were_found(parts):
    case, data = parts
    verdict = VerdictEngine(_features(), CONFIG).combine(case, {**data, "reports": None, "typologies": None})
    evidence = {part["title"]: part["lines"] for part in verdict.explanation["evidence"]}
    assert evidence["Research reports"] == ["No research reports were found."]
    assert evidence["Sector typologies"] == ["No verified typologies."]
