"""Declaration: what the client says his wealth came from, as a list of ClaimedSources."""

import json

import pytest

from app.model.claimed_source import ClaimedSource
from app.model.declaration import Declaration

READING = {"claimed_sources": [
    {"source_id": "S1", "source_type": "employment", "description": "Salary as COO", "start_year": 1998,
     "end_year": None, "amount": None, "country": "Singapore", "linked_position_index": 3,
     "linked_asset_index": None, "quote": "salary", "counterparty": "Straits Harbour Logistics Pte Ltd",
     "occupation_mismatch": False},
    {"source_id": "S2", "source_type": "advisory_fees", "description": "Advisory work", "start_year": 2018,
     "end_year": None, "amount": None, "country": "Hong Kong", "linked_position_index": None,
     "linked_asset_index": None, "quote": "some advisory work", "counterparty": None, "occupation_mismatch": False},
]}


def test_declaration_builds_its_own_sources_from_details():
    declaration = Declaration([
        {"source_type": "gift", "counterparty": None, "amount_sgd": 500000, "occupation_mismatch": False},
        {"source_type": "salary", "counterparty": "Employer", "amount": None, "occupation_mismatch": True},
    ])
    first, second = declaration.sources()
    assert isinstance(first, ClaimedSource)
    assert (first.source_type, first.amount) == ("gift", 500000)
    assert second.occupation_mismatch is True
    assert declaration.unnamed_count() == 1


def test_an_empty_declaration_has_no_sources():
    assert Declaration().sources() == []
    assert Declaration().unnamed_count() == 0
    assert Declaration().to_dict() == {"claimed_sources": []}
    assert Declaration().to_scan_dict() == {"sources": []}


def test_add_source_returns_the_new_source():
    declaration = Declaration()
    source = declaration.add_source({"source_type": "business_sale", "counterparty": "Buyer Ltd", "amount": 2})
    assert declaration.sources() == [source]


def test_the_source_list_cannot_be_changed_from_outside():
    declaration = Declaration([{"source_type": "gift"}])
    declaration.sources().clear()
    assert len(declaration.sources()) == 1


def test_from_dict_reads_the_ai_reading_and_to_dict_gives_it_back_exactly():
    declaration = Declaration.from_dict(READING)
    assert [source.source_id for source in declaration.sources()] == ["S1", "S2"]
    assert json.dumps(declaration.to_dict()) == json.dumps(READING)


def test_from_dict_reads_the_saved_crime_scan_rows_and_to_scan_dict_gives_them_back_exactly():
    rows = Declaration.from_dict(READING).to_scan_dict()
    assert json.dumps(Declaration.from_dict(rows).to_scan_dict()) == json.dumps(rows)
    assert [row["jurisdiction"] for row in rows["sources"]] == ["Singapore", "Hong Kong"]


@pytest.mark.parametrize("data", [None, [], {"claimed_sources": "none"}, {"sources": ["S1"]}])
def test_from_dict_rejects_something_that_is_not_a_declaration(data):
    with pytest.raises(ValueError, match="declaration"):
        Declaration.from_dict(data)


def test_a_source_with_an_impossible_value_is_not_added():
    with pytest.raises(ValueError, match="negative"):
        Declaration.from_dict({"claimed_sources": [{**READING["claimed_sources"][0], "amount": -1}]})
