"""Declaration and ClaimedSource: what the client says his wealth came from."""

import pytest

from app.model.claimed_source import ClaimedSource
from app.model.declaration import Declaration


def test_gift_and_inheritance_are_told_apart_from_other_sources():
    assert ClaimedSource("gift", None, 1000, False).is_gift_or_inheritance()
    assert ClaimedSource("inheritance", "Late father", 1000, False).is_gift_or_inheritance()
    assert not ClaimedSource("salary", "Employer", 1000, False).is_gift_or_inheritance()


def test_a_source_with_no_counterparty_is_unnamed():
    assert not ClaimedSource("gift", None, 1000, False).has_named_counterparty()
    assert ClaimedSource("gift", "Uncle", 1000, False).has_named_counterparty()


def test_a_source_is_valued_when_it_has_an_amount():
    assert ClaimedSource("gift", None, 0, False).is_valued()
    assert not ClaimedSource("gift", None, None, False).is_valued()


def test_a_job_source_the_forecast_explains_needs_no_amount():
    assert ClaimedSource("salary", "Employer", None, False, amount_explained=True).is_valued()


def test_a_source_rejects_a_negative_or_non_number_amount():
    with pytest.raises(ValueError):
        ClaimedSource("gift", None, -5, False)
    with pytest.raises(ValueError):
        ClaimedSource("gift", None, "a lot", False)
    source = ClaimedSource("gift", None, 5, False)
    with pytest.raises(ValueError):
        source.amount = -1


def test_declaration_builds_its_own_sources_from_details():
    declaration = Declaration([
        {"source_type": "gift", "counterparty": None, "amount_sgd": 500000, "occupation_mismatch": False},
        {"source_type": "salary", "counterparty": "Employer", "amount": None, "occupation_mismatch": True},
    ])
    first, second = declaration.sources()
    assert (first.source_type, first.amount) == ("gift", 500000)
    assert second.occupation_mismatch is True
    assert declaration.unnamed_count() == 1


def test_an_empty_declaration_has_no_sources():
    assert Declaration().sources() == []
    assert Declaration().unnamed_count() == 0


def test_add_source_returns_the_new_source():
    declaration = Declaration()
    source = declaration.add_source({"source_type": "business_sale", "counterparty": "Buyer Ltd", "amount": 2})
    assert declaration.sources() == [source]


def test_the_source_list_cannot_be_changed_from_outside():
    declaration = Declaration([{"source_type": "gift"}])
    declaration.sources().clear()
    assert len(declaration.sources()) == 1
