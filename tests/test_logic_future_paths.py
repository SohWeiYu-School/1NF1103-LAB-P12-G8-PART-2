"""FuturePaths: the wealth of each person type, from the made-up forecast in fake_ai."""

import pytest

from app.logic.future_paths import FuturePaths
from app.logic.market_model import MarketModel
from tests.logic_fixtures import POLICY, sample_case, sample_forecast


@pytest.fixture(scope="module")
def setup():
    case = sample_case()
    forecast = sample_forecast(case)
    paths = FuturePaths(MarketModel(forecast), forecast, POLICY)
    savings = paths.career_savings().rows(1998, 2026)
    assets = paths.asset_path().build(case, 2026)
    return case, forecast, paths, savings, assets


def test_it_creates_its_own_savings_and_asset_path(setup):
    _, _, paths, savings, assets = setup
    assert savings[-1]["year"] == 2026
    assert len(assets) == len(sample_case()["investments"])


def test_honest_wealth_is_savings_plus_asset_gains_and_income(setup):
    case, _, paths, savings, assets = setup
    wealth = paths.honest_wealth(case, savings, assets, 2026)
    expected = savings[-1]["savings"]["typical"]
    for asset, path in zip(case["investments"], assets):
        expected += path["values"][2026]["typical"] - asset["price_paid"]
        expected += paths.asset_path().income_up_to(path, 2026)["typical"]
    assert wealth["typical"] == pytest.approx(expected, rel=1e-6)


def test_an_asset_not_yet_bought_adds_nothing(setup):
    case, _, paths, savings, assets = setup
    first_purchase = min(asset["year_acquired"] for asset in case["investments"])
    before = paths.honest_wealth(case, savings, assets, first_purchase - 1)
    row = next(row for row in savings if row["year"] == first_purchase - 1)
    assert before == row["savings"]


def test_a_crime_type_is_richer_than_the_honest_type_by_its_extra_money(setup):
    case, forecast, paths, savings, assets = setup
    now = paths.type_wealth_now(case, savings, assets)
    extra = paths.extra_money_up_to(forecast["types"]["behaviour"]["T2"], 2026)
    assert now["T1"] == paths.honest_wealth(case, savings, assets, 2026)
    assert now["T2"]["typical"] == pytest.approx(now["T1"]["typical"] + extra["typical"])
    assert extra["typical"] > 0


def test_forward_paths_cover_this_year_and_every_forecast_year(setup):
    case, _, paths, savings, _ = setup
    forward = paths.forward_paths(case, savings, "steady")
    assert sorted(forward["T1"]) == [2026, 2027, 2028, 2029, 2030]
    assert set(forward) == {"T1", "T2", "T3"}


def test_expected_paths_lie_between_the_scenarios(setup):
    case, _, paths, savings, _ = setup
    expected = paths.expected_paths(case, savings)["T1"][2030]["typical"]
    by_scenario = [paths.forward_paths(case, savings, scenario)["T1"][2030]["typical"]
                   for scenario in MarketModel.SCENARIOS]
    assert min(by_scenario) - 1 <= expected <= max(by_scenario) + 1


def test_event_impacts_give_one_row_per_event_and_type(setup):
    case, forecast, paths, savings, _ = setup
    rows = paths.event_impacts(case, savings)
    assert len(rows) == len(forecast["events"]["events"]) * 3
    assert all(row["weighted_impact"] == round(row["impact"] * row["chance"]) for row in rows)


def test_divergence_years_names_when_a_type_can_be_told_apart():
    paths = FuturePaths(MarketModel())
    band = lambda low, high: {"cautious": low, "typical": (low + high) / 2, "optimistic": high}
    wealth = {"T1": {2026: band(10, 20), 2027: band(10, 20), 2028: band(10, 20)},
              "T2": {2026: band(15, 25), 2027: band(18, 30), 2028: band(21, 40)},
              "T3": {2026: band(12, 18), 2027: band(12, 18), 2028: band(12, 18)}}
    assert paths.divergence_years(wealth) == [{"type_id": "T2", "distinguishable_from": 2028},
                                              {"type_id": "T3", "distinguishable_from": None}]


def test_monitoring_ranges_come_from_the_honest_types_signals(setup):
    _, forecast, paths, _, _ = setup
    tolerance = POLICY["tolerance"]["signal_amount"]
    ranges = paths.monitoring_ranges(2027)
    signal = forecast["types"]["behaviour"]["T1"]["signals"][0]
    assert ranges[signal["signal_code"]]["amount_max"] == round(signal["amount_per_year"]["high"] * (1 + tolerance))
