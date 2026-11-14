"""OnboardingAssessor: the onboarding rule, from the made-up forecast in fake_ai."""

import pytest

from app.logic.future_paths import FuturePaths
from app.logic.market_model import MarketModel
from app.logic.onboarding_assessor import OnboardingAssessor
from tests.logic_fixtures import CONFIG, POLICY, sample_case, sample_forecast


def _evaluate(case, scale=1.0, **options):
    forecast = sample_forecast(case, **options)
    paths = FuturePaths(MarketModel(forecast), forecast, POLICY)
    assessor = OnboardingAssessor(paths, POLICY, CONFIG)
    savings = paths.career_savings().rows(1998, 2026)
    assets = paths.asset_path().build(case, 2026)
    return assessor.evaluate(case, forecast, savings, assets, scale)


def _assessor():
    return OnboardingAssessor(FuturePaths(MarketModel()), POLICY, CONFIG)


def _fit(fits=True, at_typical=True):
    return {"fits": fits, "fits_at_typical": at_typical}


def test_evaluate_gives_an_outcome_and_a_fit_for_every_type():
    result = _evaluate(sample_case())
    assert result["outcome"] in ("PASSED", "MANUAL_REVIEW", "RISKY", "SERIOUS_RISK")
    assert set(result["fits"]) == {"T1", "T2", "T3"}
    assert all(0 <= fit["fit_score"] <= 1 for fit in result["fits"].values())


def test_a_much_higher_declared_net_worth_stops_fitting_the_honest_type():
    case = sample_case()
    honest = _evaluate(case)["fits"]["T1"]["wealth_now"]["optimistic"]
    case["claims"]["declared_net_worth"] = honest * 5
    assert _evaluate(case)["fits"]["T1"]["net_worth_fits"] is False


def test_scaling_the_forecasts_up_makes_every_type_richer():
    case = sample_case()
    normal = _evaluate(case)["fits"]["T1"]["wealth_now"]["typical"]
    assert _evaluate(case, scale=1.1)["fits"]["T1"]["wealth_now"]["typical"] == pytest.approx(normal * 1.1, rel=1e-6)


def test_a_named_country_with_nothing_behind_it_fails_the_country_check():
    case = sample_case()
    case["claims"]["wealth_countries"] = ["Singapore", "Panama"]
    jurisdiction = _evaluate(case)["jurisdiction"]
    assert jurisdiction["failed"] is True
    assert jurisdiction["unexplained_countries"] == ["panama"]


def test_a_source_with_no_amount_and_nothing_behind_it_is_unquantified():
    sources = {source["source_id"]: source for source in _evaluate(sample_case())["sources"]}
    assert sources["S1"]["failed"] is False       # salary tied to his current job
    assert sources["S2"]["failed"] is True        # "some advisory work": no amount, no job, no asset


def test_only_a_crime_type_explaining_him_is_serious_risk():
    fits = {"T1": _fit(fits=False), "T2": _fit(fits=True)}
    assert _assessor()._decide_onboarding(fits, False, []) == "SERIOUS_RISK"


def test_no_type_explaining_him_is_risky():
    fits = {"T1": _fit(fits=False), "T2": _fit(fits=False)}
    assert _assessor()._decide_onboarding(fits, False, []) == "RISKY"


def test_honest_only_at_the_optimistic_edge_or_an_unaffordable_purchase_is_risky():
    assert _assessor()._decide_onboarding({"T1": _fit(at_typical=False)}, False, []) == "RISKY"
    assert _assessor()._decide_onboarding({"T1": _fit()}, True, []) == "RISKY"


def test_other_failed_checks_mean_manual_review_and_a_clean_case_passes():
    assert _assessor()._decide_onboarding({"T1": _fit()}, False, ["JURISDICTION"]) == "MANUAL_REVIEW"
    assert _assessor()._decide_onboarding({"T1": _fit()}, False, []) == "PASSED"


def test_an_answer_that_changes_when_the_forecasts_shift_goes_to_manual_review():
    assessor = _assessor()
    assert assessor.stable_outcome("PASSED", {"-10%": "PASSED", "+10%": "RISKY"}) == ("MANUAL_REVIEW", True)
    assert assessor.stable_outcome("PASSED", {"-10%": "PASSED", "+10%": "PASSED"}) == ("PASSED", False)


def test_a_borderline_case_is_never_downgraded():
    assert _assessor().stable_outcome("SERIOUS_RISK", {"-10%": "RISKY", "+10%": "SERIOUS_RISK"}) == ("SERIOUS_RISK", True)
