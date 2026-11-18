"""CareerSavings, with small hand-checked numbers."""

import pytest

from app.logic.career_savings import CareerSavings


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


@pytest.mark.parametrize("pay", ["pay", [1], {"positions": "none"}, {"positions": [1]},
                                 {"positions": [{"position_index": 0}]},
                                 {"positions": [{"position_index": 0, "yearly": None}]}])
def test_career_savings_rejects_a_pay_forecast_of_the_wrong_shape(pay):
    with pytest.raises(ValueError, match="pay forecast"):
        CareerSavings(pay)
