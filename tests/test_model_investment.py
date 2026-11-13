"""Investment: one asset."""

import pytest

from app.model.investment import Investment

POLICY = {"asset_categories": {"property": ["property", "condo"], "listed_equities": ["equit", "stock"],
                               "private_business": ["business", "stake"]}}


def _asset(asset_type="Residential property (condominium)", **changes):
    details = {"asset_type": asset_type, "country": "Singapore", "year_acquired": 2009,
               "price_paid": 1650000, "current_declared_value": 3100000,
               "payment_method": "loan", "income_produced": 0}
    details.update(changes)
    return Investment(**details)


def test_category_is_found_by_keyword():
    assert _asset().category(POLICY) == "property"
    assert _asset("Listed equities portfolio").category(POLICY) == "listed_equities"
    assert _asset("Gold bars").category(POLICY) == "other"


def test_an_asset_rejects_negative_or_non_number_amounts():
    with pytest.raises(ValueError):
        _asset(price_paid=-1)
    with pytest.raises(ValueError):
        _asset(current_declared_value="3.1m")
    asset = _asset()
    with pytest.raises(ValueError):
        asset.income_produced = -100


def test_amounts_may_be_left_empty_or_zero():
    asset = _asset(price_paid=None, income_produced=0)
    assert asset.price_paid is None
    assert asset.income_produced == 0


def test_an_asset_rejects_a_year_that_is_not_a_whole_year():
    with pytest.raises(ValueError):
        _asset(year_acquired="2009")
    asset = _asset()
    with pytest.raises(ValueError):
        asset.year_acquired = 99


def test_payment_method_must_be_text():
    with pytest.raises(ValueError):
        _asset(payment_method=3)
    assert _asset(payment_method=None).payment_method is None


def test_to_dict_keeps_the_saved_layout_and_any_extra_details():
    data = _asset(extra={"year_sold": 2020, "currency": "SGD"}).to_dict()
    assert data["current_declared_value"] == 3100000
    assert data["payment_method"] == "loan"
    assert data["year_sold"] == 2020 and data["currency"] == "SGD"
