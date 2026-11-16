"""MarketModel: past changes from the history, future changes from the scenario forecast."""

import pytest

from app.logic.market_model import MarketModel


def _range(low, typical, high):
    return {"low": low, "typical": typical, "high": high}


FORECAST = {"markets": {
    "series": {"PROP_SG": {
        "history": [{"year": 2024, "change_pct": 3.0}, {"year": 2025, "change_pct": None}],
        "outlook": [{"year": 2027, "steady": _range(1, 2, 3), "boom": _range(3, 5, 7),
                     "downturn": _range(-4, -2, 0)}]}},
    "scenario_chances": [{"year": 2027, "steady": 60, "boom": 30, "downturn": 30}]}}


def test_a_past_year_uses_the_recalled_history():
    assert MarketModel(FORECAST).change("PROP_SG", 2024, "boom", "high") == 3.0


def test_a_year_the_ai_could_not_find_counts_as_no_change():
    assert MarketModel(FORECAST).change("PROP_SG", 2025, "steady") == 0.0


def test_a_future_year_uses_the_scenario_and_level():
    model = MarketModel(FORECAST)
    assert model.change("PROP_SG", 2027, "steady") == 2.0
    assert model.change("PROP_SG", 2027, "downturn", "low") == -4.0
    assert model.change("PROP_SG", 2027, "boom", "high") == 7.0


def test_an_unknown_market_or_year_is_no_change():
    model = MarketModel(FORECAST)
    assert model.change("FX_AUD", 2027, "steady") == 0.0
    assert model.change("PROP_SG", 2040, "steady") == 0.0


def test_an_event_shock_is_added_on_top():
    shocks = {("PROP_SG", 2027): _range(-20, -10, -5)}
    assert MarketModel(FORECAST).change("PROP_SG", 2027, "steady", "typical", shocks) == -8.0


def test_scenario_chances_add_up_to_exactly_one():
    chances = MarketModel(FORECAST).scenario_chances()[2027]
    assert chances == {"steady": 0.5, "boom": 0.25, "downturn": 0.25}
    assert sum(chances.values()) == pytest.approx(1.0)


def test_history_and_outlook_are_keyed_by_market_and_year():
    model = MarketModel(FORECAST)
    assert model.history() == {"PROP_SG": {2024: 3.0, 2025: None}}
    assert model.outlook()["PROP_SG"][2027]["boom"] == _range(3, 5, 7)


def test_a_model_with_no_forecast_knows_no_markets():
    model = MarketModel()
    assert model.history() == {} and model.scenario_chances() == {}
    assert model.change("PROP_SG", 2027, "steady") == 0.0


@pytest.mark.parametrize("forecast, message", [
    ("markets", "forecast must be a dict"),
    ({"markets": [1]}, "markets must be a dict"),
    ({"markets": {"series": [1]}}, "market series must be a dict"),
    ({"markets": {"series": {"M1": "flat"}}}, "market M1 must be a dict with a list called history"),
    ({"markets": {"series": {"M1": {"history": [{"year": 2024}], "outlook": []}}}}, "history row of market M1"),
    ({"markets": {"series": {"M1": {"history": [], "outlook": [{"year": 2027}]}}}}, "outlook row of market M1"),
    ({"markets": {"scenario_chances": {"year": 2027}}}, "scenario_chances must be a list"),
    ({"markets": {"scenario_chances": [{"year": 2027, "steady": 1}]}}, "scenario chance must be a dict"),
])
def test_a_forecast_of_the_wrong_shape_is_a_value_error_that_says_which_part(forecast, message):
    with pytest.raises(ValueError, match=message):
        MarketModel(forecast)


def test_no_forecast_or_no_markets_is_an_empty_model():
    assert MarketModel().history() == {} and MarketModel({}).outlook() == {}
