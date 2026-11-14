"""Benchmark: the benchmark feature."""

from app.logic.benchmark import Benchmark
from app.logic.risk_analysis import RiskAnalysis
from app.model.check import Check
from tests import fake_ai
from tests.logic_fixtures import CONFIG, POLICY, sample_case

BENCH_INPUT = {"occupation": "COO", "industry": "Shipping", "age": 51, "career_start_year": 1998,
               "country": "Singapore", "declared_net_worth": 16_500_000, "listed_equities": 11, "cash": 20,
               "property": 28, "private_business": 41, "biggest_wealth_jump": None, "wealth_jump_years": 0.0,
               "declared_counterparties": ["Meridian Harbour Bank", "Lucky Star Trading"],
               "declared_countries": ["Singapore", "Panama"]}


def _feature():
    return Benchmark(POLICY, CONFIG)


def test_benchmark_is_a_feature():
    assert isinstance(_feature(), RiskAnalysis)
    assert Benchmark.NAME == "benchmark"


def test_wealth_far_above_peers_fails_the_total_wealth_rule():
    result = _feature().run({}, {"benchmark_input": BENCH_INPUT, "benchmark_ai": fake_ai.benchmark()})
    rules = {finding["rule_id"]: finding for finding in result["findings"]}
    assert rules["TOTAL_WEALTH"]["failed"] is True          # 16.5m against peers' 2.4m
    assert "Lucky Star Trading" in rules["COUNTERPARTIES"]["detail"]
    assert "Meridian Harbour Bank" not in rules["COUNTERPARTIES"]["detail"]
    assert "Panama" in rules["JURISDICTION"]["detail"]


def test_wealth_in_line_with_peers_passes_the_total_wealth_rule():
    ai = fake_ai.benchmark(expected_wealth=15_000_000)
    result = _feature().run({}, {"benchmark_input": BENCH_INPUT, "benchmark_ai": ai})
    rules = {finding["rule_id"]: finding for finding in result["findings"]}
    assert rules["TOTAL_WEALTH"]["failed"] is False


def test_no_ai_benchmark_gives_no_results_and_a_skipped_check():
    feature = _feature()
    assert feature.run({}, {"benchmark_input": BENCH_INPUT, "benchmark_ai": None}) == {}
    checks = feature.checks({"case": sample_case(), "ai_data": None})
    assert all(isinstance(check, Check) for check in checks)
    assert "skipped" in [check.status for check in checks]


def test_checks_are_stamped_benchmark_and_cover_total_wealth():
    feature = _feature()
    findings = feature.run({}, {"benchmark_input": BENCH_INPUT, "benchmark_ai": fake_ai.benchmark()})["findings"]
    checks = feature.checks({"case": sample_case(), "bench_input": BENCH_INPUT, "ai_data": fake_ai.benchmark(),
                             "findings": findings})
    assert all(check.feature == "benchmark" for check in checks)
    total = next(check for check in checks if check.check == "TOTAL_WEALTH")
    assert total.status == "failed"            # with no forecast, nothing explains the gap


def test_pep_status_follows_the_policy():
    assert _feature().is_pep({"claims": {"pep_status": "Domestic PEP"}}) is True
    assert _feature().is_pep({"claims": {"pep_status": "None"}}) is False
