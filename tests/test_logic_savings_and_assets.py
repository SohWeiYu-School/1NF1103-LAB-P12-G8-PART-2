"""CareerSavings and AssetPath, with small hand-checked numbers."""

import pytest

from app.logic.asset_path import AssetPath
from app.logic.career_savings import CareerSavings
from app.logic.market_model import MarketModel


def _range(low, typical, high):
    return {"low": low, "typical": typical, "high": high}


def _flat(value):
    return _range(value, value, value)


PAY_ROW = {"year": 2020, "base_pay": _range(80, 100, 120), "bonus": _flat(10), "equity_or_profit_share": _flat(0),
           "tax_rate_pct": _range(10, 20, 30), "living_costs": _range(30, 40, 50), "savings_return_pct": _flat(0)}
PAY = {"positions": [{"position_index": 0, "yearly": [PAY_ROW, {**PAY_ROW, "year": 2021}]}]}


def test_pay_total_adds_base_bonus_and_equity():
    assert CareerSavings().pay_total(PAY_ROW, "typical") == 110
    assert CareerSavings().pay_total(PAY_ROW, "low") == 90


def test_the_cautious_level_uses_low_pay_with_high_tax_and_costs():
    row = CareerSavings(PAY).rows(2020, 2020)[0]
    assert row["total_pay"] == {"cautious": 90, "typical": 110, "optimistic": 130}
    assert row["after_tax"]["cautious"] == pytest.approx(90 * 0.7)       # the high tax rate
    assert row["living_costs"]["cautious"] == 50                         # the high living costs
    assert row["saved"]["typical"] == pytest.approx(110 * 0.8 - 40)


def test_savings_build_up_year_after_year():
    first, second = CareerSavings(PAY).rows(2020, 2021)
    assert second["savings"]["typical"] == pytest.approx(2 * first["saved"]["typical"])


def test_savings_earn_a_return():
    pay = {"positions": [{"position_index": 0, "yearly": [
        {**PAY_ROW, "savings_return_pct": _flat(10)}, {**PAY_ROW, "year": 2021, "savings_return_pct": _flat(10)}]}]}
    first, second = CareerSavings(pay).rows(2020, 2021)
    saved = first["saved"]["typical"]
    assert second["savings"]["typical"] == pytest.approx(saved + saved * 0.10 + saved)


def test_a_year_with_no_pay_forecast_counts_as_no_pay():
    rows = CareerSavings(PAY).rows(2019, 2020)
    assert rows[0]["total_pay"] == {"cautious": 0.0, "typical": 0.0, "optimistic": 0.0}
    assert rows[0]["savings"]["typical"] == 0.0
    assert rows[1]["total_pay"]["typical"] == 110


def test_no_pay_at_all_gives_empty_years():
    assert [row["year"] for row in CareerSavings().rows(2020, 2021)] == [2020, 2021]


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
