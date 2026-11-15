"""Benchmark: the benchmark feature."""

from app.logic.benchmark import Benchmark
from app.logic.risk_analysis import RiskAnalysis
from app.model.check import Check
from app.model.declaration import Declaration
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


def _benchmark_checks(**claims):
    feature = _feature()
    findings = feature.run({}, {"benchmark_input": BENCH_INPUT, "benchmark_ai": fake_ai.benchmark()})["findings"]
    case = sample_case()
    case["claims"].update(claims)
    return {check.check: check for check in feature.checks(
        {"case": case, "bench_input": BENCH_INPUT, "ai_data": fake_ai.benchmark(), "findings": findings})}


def test_pep_status_follows_the_policy():
    assert _benchmark_checks(pep_status="Domestic PEP")["PEP_STATUS"].failed()
    assert not _benchmark_checks(pep_status="None")["PEP_STATUS"].failed()


def test_a_blank_pep_answer_is_a_check_that_could_not_run_not_a_pass():
    for blank in ("", "  ", None):
        check = _benchmark_checks(pep_status=blank)["PEP_STATUS"]
        assert check.status == "skipped" and "Not answered" in check.detail
        assert not check.failed() and check.status != "passed"


def test_every_benchmark_check_says_whether_it_is_independent_evidence():
    checks = _benchmark_checks()
    assert checks["TOTAL_WEALTH"].extra("independent") is True        # from peers
    assert checks["UNEXPLAINED_GAP"].extra("independent") is False    # the forecast's story seen again
    assert checks["PEP_STATUS"].extra("independent") is False
    assert list(checks["TOTAL_WEALTH"].to_dict())[-2:] == ["independent", "optional"]


def test_money_he_cannot_fund_by_his_own_figures_is_independent():
    assert _benchmark_checks(expected_aum=50_000_000)["AUM_FUNDING"].failed()
    assert _benchmark_checks(expected_aum=50_000_000)["AUM_FUNDING"].extra("independent") is True
    assert _benchmark_checks(expected_aum=5_000_000)["AUM_FUNDING"].extra("independent") is False


def test_a_missing_wealth_jump_is_an_optional_skipped_check():
    checks = _benchmark_checks()
    jump = checks["JUMP_VS_ECONOMY"]
    assert (jump.status, jump.extra("optional")) == ("skipped", True)
    assert checks["TOTAL_WEALTH"].extra("optional") is False


# ----- counterparties not usual for his career, cross-checked with his declaration ----------

MANY_PEOPLE = {**BENCH_INPUT, "declared_counterparties": ["Lucky Star Trading", "Golden Dragon Holdings",
                                                          "Meridian Harbour Bank"]}


def _source(counterparty, job=None, asset=None, description="x"):
    return {"source_id": "S1", "source_type": "business_income", "description": description, "start_year": 2010,
            "end_year": None, "amount": 1000, "country": "Singapore", "linked_position_index": job,
            "linked_asset_index": asset, "quote": "x", "counterparty": counterparty, "occupation_mismatch": False}


def _counterparty_check(declaration):
    feature = _feature()
    findings = feature.run({}, {"benchmark_input": MANY_PEOPLE, "benchmark_ai": fake_ai.benchmark()})["findings"]
    checks = feature.checks({"case": sample_case(), "bench_input": MANY_PEOPLE, "ai_data": fake_ai.benchmark(),
                             "findings": findings, "declaration": declaration})
    return next(check for check in checks if check.check == "COUNTERPARTIES")


def test_counterparties_named_by_sources_linked_to_his_jobs_or_assets_are_explained():
    declaration = Declaration.from_dict({"claimed_sources": [_source("Lucky Star Trading Pte Ltd", job=0),
                                                             _source("Golden Dragon Holdings", asset=1)]})
    assert _counterparty_check(declaration).status == "explained"


def test_a_counterparty_named_only_by_an_unlinked_source_is_not_explained():
    declaration = Declaration.from_dict({"claimed_sources": [_source("Lucky Star Trading", job=0),
                                                             _source("Golden Dragon Holdings")]})
    assert _counterparty_check(declaration).status == "failed"


def test_only_the_sources_counterparty_names_someone_not_its_description():
    declaration = Declaration.from_dict({"claimed_sources": [
        _source("Lucky Star Trading", job=0), _source(None, asset=1, description="Golden Dragon Holdings")]})
    assert _counterparty_check(declaration).status == "failed"


def test_with_no_declaration_reading_the_counterparties_are_not_checked():
    check = _counterparty_check(None)
    assert check.status == "failed" and check.explanation
