"""OnboardingAssessor: the onboarding rule, from the made-up forecast in fake_ai."""

import pytest

from app.logic.future_paths import FuturePaths
from app.logic.market_model import MarketModel
from app.logic.onboarding_assessor import OnboardingAssessor
from app.model.declaration import Declaration
from tests.logic_fixtures import CONFIG, POLICY, sample_case, sample_forecast


def _evaluate(case, scale=1.0, declaration=None, **options):
    forecast = sample_forecast(case, **options)
    if declaration is not None:
        forecast["declaration"] = declaration
    paths = FuturePaths(MarketModel(forecast), forecast, POLICY)
    assessor = OnboardingAssessor(paths, POLICY, CONFIG)
    savings = paths.career_savings().rows(1998, 2026)
    assets = paths.asset_path().build(case, 2026)
    return assessor.evaluate(case, forecast, savings, assets, scale)


def _assessor():
    return OnboardingAssessor(FuturePaths(MarketModel()), POLICY, CONFIG)


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


def _source(source_id, country, amount=None, job=None, asset=None, kind="advisory_fees"):
    return {"source_id": source_id, "source_type": kind, "description": f"about {source_id}", "start_year": 2010,
            "end_year": 2012, "amount": amount, "country": country, "linked_position_index": job,
            "linked_asset_index": asset, "quote": f"quote {source_id}", "counterparty": None,
            "occupation_mismatch": False}


def test_a_declared_source_puts_its_country_behind_a_named_country():
    case = sample_case()
    case["claims"]["wealth_countries"] = ["Singapore", "Panama"]
    declaration = Declaration.from_dict({"claimed_sources": [_source("S1", "Panama", amount=1000)]})
    jurisdiction = _evaluate(case, declaration=declaration)["jurisdiction"]
    assert "panama" not in jurisdiction["unexplained_countries"]


def test_each_declared_source_is_checked_from_the_declaration():
    declaration = Declaration.from_dict({"claimed_sources": [
        _source("S1", "Hong Kong"), _source("S2", "Singapore", amount=5000), _source("S3", "Singapore", asset=0),
        _source("S4", "Singapore", job=1), _source("S5", "Singapore", kind="employment")]})
    sources = _evaluate(sample_case(), declaration=declaration)["sources"]
    assert [source["failed"] for source in sources] == [True, False, False, False, False]
    assert sources[0] == {"rule_id": "UNQUANTIFIED_SOURCE", "source_id": "S1", "source_type": "advisory_fees",
                          "failed": True, "quote": "quote S1",
                          "detail": "S1 about S1 (2010-2012, Hong Kong): no amount and no job or asset behind it"}


def _outcome(declared, clean=False):
    """The onboarding outcome for the sample case declaring this net worth. clean = no unexplained
    assets, countries or sources, so no other check can fail."""
    case = sample_case()
    case["claims"]["declared_net_worth"] = declared
    if not clean:
        return _evaluate(case)["outcome"]
    case["investments"] = []
    case["claims"]["wealth_countries"] = ["Singapore"]
    return _evaluate(case, declaration=Declaration.from_dict({"claimed_sources": []}))["outcome"]


def test_only_a_crime_type_explaining_him_is_serious_risk():
    assert _outcome(20_000_000) == "SERIOUS_RISK"       # only T2 (a crime type) fits


def test_no_type_explaining_him_is_risky():
    assert _outcome(100_000_000) == "RISKY"


def test_honest_only_at_the_optimistic_edge_or_an_unaffordable_purchase_is_risky():
    assert _outcome(16_500_000) == "RISKY"              # T1 fits, but not at the typical wealth
    assert _outcome(10_000_000, clean=True) == "RISKY"


def test_other_failed_checks_mean_manual_review_and_a_clean_case_passes():
    assert _outcome(1_000_000) == "MANUAL_REVIEW"
    assert _outcome(2_000_000, clean=True) == "PASSED"


def test_an_answer_that_changes_when_the_forecasts_shift_goes_to_manual_review():
    assessor = _assessor()
    assert assessor.stable_outcome("PASSED", {"-10%": "PASSED", "+10%": "RISKY"}) == ("MANUAL_REVIEW", True)
    assert assessor.stable_outcome("PASSED", {"-10%": "PASSED", "+10%": "PASSED"}) == ("PASSED", False)


def test_a_borderline_case_is_never_downgraded():
    assert _assessor().stable_outcome("SERIOUS_RISK", {"-10%": "RISKY", "+10%": "SERIOUS_RISK"}) == ("SERIOUS_RISK", True)
