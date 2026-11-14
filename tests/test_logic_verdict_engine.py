"""VerdictEngine: one verdict from the features it is handed."""

import pytest

from app.logic.benchmark import Benchmark
from app.logic.crime_scan import CrimeScan
from app.logic.document_evidence import DocumentEvidence
from app.logic.feature import Feature
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
    assert all(isinstance(feature, Feature) for feature in engine.features())


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


class _AlwaysFails(Feature):
    """A made-up benchmark, to show the engine treats any Feature the same way."""

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
