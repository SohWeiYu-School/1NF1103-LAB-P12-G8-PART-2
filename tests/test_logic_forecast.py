"""Forecast: the forecast feature, from the made-up forecast in fake_ai."""

import pytest

from app.logic.risk_analysis import RiskAnalysis
from app.logic.forecast import Forecast
from app.model.check import Check
from tests.logic_fixtures import CONFIG, POLICY, sample_case, sample_forecast


@pytest.fixture(scope="module")
def ran():
    case = sample_case()
    forecast = sample_forecast(case)
    feature = Forecast(POLICY, CONFIG)
    assessment = feature.run(case, {"forecast": forecast})
    honest = feature.honest_numbers(case, forecast, assessment)
    return case, forecast, feature, assessment, honest


def test_forecast_is_a_feature():
    assert isinstance(Forecast(POLICY, CONFIG), RiskAnalysis)
    assert Forecast.NAME == "forecast"


def test_run_gives_one_outcome_with_its_routing_and_review_date(ran):
    case, _, _, assessment, _ = ran
    assert assessment["outcome"] in ("PASSED", "MANUAL_REVIEW", "RISKY", "SERIOUS_RISK")
    assert assessment["routing"] == POLICY["routing"][assessment["outcome"]]
    assert assessment["next_review_date"] > case["current_date"]
    assert assessment["policy_version"] == POLICY["policy_version"]


def test_the_same_forecast_always_gives_the_same_answer(ran):
    case, forecast, _, assessment, _ = ran
    assert Forecast(POLICY, CONFIG).run(case, {"forecast": forecast}) == assessment


def test_much_more_crime_money_does_not_change_the_honest_types_wealth():
    case = sample_case()
    low = Forecast(POLICY, CONFIG).run(case, {"forecast": sample_forecast(case, crime_money=100_000)})
    high = Forecast(POLICY, CONFIG).run(case, {"forecast": sample_forecast(case, crime_money=900_000)})
    wealth = lambda assessment, type_id: next(
        row for row in assessment["types"] if row["type_id"] == type_id)["wealth_now"]
    assert wealth(low, "T1") == wealth(high, "T1")
    assert wealth(high, "T2")["typical"] > wealth(low, "T2")["typical"]


def test_checks_are_check_objects_in_the_shared_shape(ran):
    case, _, feature, assessment, honest = ran
    checks = feature.checks({"case": case, "assessment": assessment, "honest": honest, "types": []})
    assert checks and all(isinstance(check, Check) for check in checks)
    assert all(check.feature == "forecast" for check in checks)
    assert "NET_WORTH_FIT" in [check.check for check in checks]


def test_forecast_checks_keep_their_groups_and_carry_no_extra_details(ran):
    case, _, feature, assessment, honest = ran
    types = [{"type_id": "T2", "name": "Trade mis-invoicing", "fits": True, "fit_score": 0.8, "route_years": ""}]
    checks = feature.checks({"case": case, "assessment": assessment, "honest": honest, "types": types})
    story = next(check for check in checks if check.check == "CRIME_STORY")
    assert (story.label, story.status, story.group) == ("T2 Trade mis-invoicing", "info", "Crime stories")
    assert story.detail == "Fits his money (fit 0.80)"
    assert next(check for check in checks if check.check == "NET_WORTH_FIT").group == "Honest story (T1)"
    assert all(list(check.to_dict()) == list(Check.FIELDS[:8]) for check in checks)


def test_a_forecast_that_stopped_gives_one_skipped_check():
    checks = Forecast(POLICY, CONFIG).checks({"case": sample_case(), "assessment": None, "honest": None,
                                              "failed_step": "the list of person types"})
    assert len(checks) == 1
    assert checks[0].status == "skipped"
    assert "the list of person types" in checks[0].detail


def test_honest_numbers_cover_every_year_of_his_career(ran):
    _, _, _, _, honest = ran
    assert honest["start"] == 1998 and honest["end"] == 2026
    assert set(range(1998, 2027)) <= set(honest["by_year"])


def test_the_economy_brief_holds_market_changes_but_nothing_about_the_client(ran):
    _, forecast, feature, _, _ = ran
    brief = feature.economy_brief(forecast["markets"])
    text = str(brief)
    assert "Container shipping" in text
    assert "16500000" not in text and "Daniel" not in text
    assert feature.economy_brief(None) is None
