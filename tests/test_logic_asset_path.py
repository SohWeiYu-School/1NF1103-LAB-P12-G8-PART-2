"""AssetPath, with small hand-checked numbers."""

import pytest

from app.logic.asset_path import AssetPath
from app.logic.market_model import MarketModel


def _range(low, typical, high):
    return {"low": low, "typical": typical, "high": high}


def _flat(value):
    return _range(value, value, value)


FORECAST = {"markets": {"series": {"PROP_SG": {
    "history": [{"year": 2021, "change_pct": 10.0}, {"year": 2022, "change_pct": -50.0}], "outlook": []}},
    "scenario_chances": []}}
MODEL = {"asset_index": 0, "exposures": [{"market_id": "PROP_SG", "sensitivity": _flat(1.0)}],
         "own_growth_pct": _flat(0), "income_yield_by_year": [{"year": 2021, "yield_pct": _flat(5)}],
         "future_income_yield_pct": {"steady": _flat(2), "boom": _flat(3), "downturn": _flat(1)}}
RECORD = {"current_date": "2022-06-01", "career_history": [{"start_year": 2015, "end_year": None}],
          "investments": [{"asset_type": "Condo", "year_acquired": 2020, "price_paid": 1000.0}]}


def _paths(shocks=None):
    return AssetPath(MarketModel(FORECAST), [MODEL]).build(RECORD, 2022, "steady", shocks)


def test_an_asset_starts_at_its_purchase_price():
    assert _paths()[0]["values"][2020]["typical"] == 1000.0


def test_an_asset_moves_with_its_market():
    values = _paths()[0]["values"]
    assert values[2021]["typical"] == pytest.approx(1100.0)       # +10%
    assert values[2022]["typical"] == pytest.approx(550.0)        # then -50%


def test_income_is_the_yield_on_that_years_value():
    income = _paths()[0]["income"]
    assert income[2021]["typical"] == pytest.approx(1100.0 * 0.05)   # the yield recalled for 2021
    assert income[2022]["typical"] == pytest.approx(550.0 * 0.02)    # no recalled yield: the forecast one


def test_an_event_shock_changes_the_value():
    shocked = _paths({("PROP_SG", 2021): _flat(-10.0)})[0]["values"]
    assert shocked[2021]["typical"] == pytest.approx(1000.0)      # +10% and -10% cancel


def test_a_value_never_goes_below_zero():
    shocked = _paths({("PROP_SG", 2022): _flat(-100.0)})[0]["values"]
    assert shocked[2022]["typical"] == 0.0


def test_income_up_to_adds_the_years_so_far():
    asset_path = AssetPath(MarketModel(FORECAST), [MODEL])
    path = asset_path.build(RECORD, 2022)[0]
    total = asset_path.income_up_to(path, 2021)
    assert total["typical"] == pytest.approx(path["income"][2020]["typical"] + path["income"][2021]["typical"])


def test_an_asset_with_no_model_gets_no_path():
    assert AssetPath(MarketModel(FORECAST), []).build(RECORD, 2022) == []


def test_asset_path_rejects_a_market_model_or_asset_models_of_the_wrong_type():
    with pytest.raises(ValueError, match="market model must be a MarketModel"):
        AssetPath({"markets": {}})
    with pytest.raises(ValueError, match="asset models must be a list"):
        AssetPath(MarketModel(), {"asset_index": 0})
    with pytest.raises(ValueError, match="asset_index"):
        AssetPath(MarketModel(), [{"exposures": []}])
    with pytest.raises(ValueError, match="asset_index"):
        AssetPath(MarketModel(), ["model"])
