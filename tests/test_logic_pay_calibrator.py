"""PayCalibrator: documented pay replaces the AI's estimate, within the policy's limits."""

import copy

import pytest

from app.logic.career_savings import CareerSavings
from app.logic.pay_calibrator import PayCalibrator
from tests.logic_fixtures import POLICY, sample_case, sample_forecast

CASE = sample_case()
FORECAST = sample_forecast(CASE)
CURRENT = len(CASE["career_history"]) - 1


def _calibrate(documented, forecast=FORECAST):
    return PayCalibrator(CareerSavings(), POLICY).calibrate(CASE, forecast, documented)


def _typical_pay(forecast, year):
    position = next(p for p in forecast["earnings"]["positions"] if p["position_index"] == CURRENT)
    row = next(row for row in position["yearly"] if row["year"] == year)
    return CareerSavings().pay_total(row, "typical")


def test_with_no_documented_pay_the_forecast_is_unchanged():
    forecast, adjusted = _calibrate([])
    assert forecast is FORECAST and adjusted == []


def test_documented_pay_moves_the_estimate_to_the_documented_figure():
    documented = _typical_pay(FORECAST, 2025) * 1.5
    forecast, adjusted = _calibrate([{"year": 2025, "amount": documented, "source_file": "tax_2025.pdf"}])
    assert _typical_pay(forecast, 2025) == pytest.approx(documented)
    assert adjusted[0]["position_index"] == CURRENT
    assert adjusted[0]["ratio"] == 1.5
    assert adjusted[0]["source_file"] == "tax_2025.pdf"


def _layout(forecast):
    """The forecast with its Declaration written out, so two forecasts can be compared."""
    return {**forecast, "declaration": forecast["declaration"].to_dict()}


def test_the_original_forecast_is_not_changed():
    before = copy.deepcopy(FORECAST)
    _calibrate([{"year": 2025, "amount": _typical_pay(FORECAST, 2025) * 1.5}])
    assert _layout(FORECAST) == _layout(before)


def test_the_current_jobs_future_pay_is_scaled_too():
    forecast, _ = _calibrate([{"year": 2025, "amount": _typical_pay(FORECAST, 2025) * 1.5}])
    before = FORECAST["earnings"]["future_pay"]["yearly"][0]["steady"]["base_pay"]["typical"]
    after = forecast["earnings"]["future_pay"]["yearly"][0]["steady"]["base_pay"]["typical"]
    assert after == pytest.approx(before * 1.5)


def test_a_document_cannot_move_an_estimate_past_the_policy_limit():
    limit = POLICY["verdict"]["pay_calibration"]["max_ratio"]
    forecast, adjusted = _calibrate([{"year": 2025, "amount": _typical_pay(FORECAST, 2025) * limit * 10}])
    assert adjusted[0]["ratio"] == round(limit, 2)


def test_a_tiny_difference_is_left_alone():
    forecast, adjusted = _calibrate([{"year": 2025, "amount": _typical_pay(FORECAST, 2025) * 1.001}])
    assert adjusted == []


def test_applying_the_same_documents_twice_changes_nothing_more():
    documented = [{"year": 2025, "amount": _typical_pay(FORECAST, 2025) * 1.5}]
    once, _ = _calibrate(documented)
    _, again = _calibrate(documented, once)
    assert again == []
