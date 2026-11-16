"""ClaimedSource: one source of wealth the client named, in the AI's reading and the crime scan's row."""

import json

import pytest

from app.model.claimed_source import ClaimedSource

# One source as the AI reads it (the declaration schema's keys, in the schema's order)
READING = {"source_id": "S2", "source_type": "advisory_fees", "description": "Advisory work", "start_year": 2018,
           "end_year": 2021, "amount": 125000.5, "country": "Hong Kong", "linked_position_index": 1,
           "linked_asset_index": 0, "quote": "some advisory work", "counterparty": "Harbour Advisers Ltd",
           "occupation_mismatch": True}
# The same source as the crime scan's row (the layout saved under crime_scan.declaration)
ROW = {"source_id": "S2", "source_type": "advisory_fees", "description": "Advisory work", "amount_sgd": 125000.5,
       "start_year": 2018, "end_year": 2021, "jurisdiction": "HK", "counterparty": "Harbour Advisers Ltd",
       "evidence_sentence": "some advisory work", "occupation_mismatch": True,
       "amount_explained_by_forecast": True}


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


@pytest.mark.parametrize("field, value", [("start_year", "2018"), ("end_year", 2018.5), ("start_year", True),
                                          ("linked_position_index", -1), ("linked_asset_index", "0"),
                                          ("linked_position_index", False)])
def test_a_source_rejects_impossible_years_and_links(field, value):
    with pytest.raises(ValueError, match="whole number|position"):
        ClaimedSource.from_dict({**READING, field: value})


def test_a_whole_number_written_as_a_decimal_is_still_a_year():
    source = ClaimedSource.from_dict({**READING, "start_year": 2018.0, "linked_asset_index": 0.0})
    assert source.start_year == 2018.0 and source.linked_asset_index == 0.0


def test_a_reading_can_only_have_the_declaration_schema_keys():
    with pytest.raises(ValueError, match="only have the keys"):
        ClaimedSource(layout=("source_id", "colour"))


def test_from_dict_keeps_every_field_of_the_reading():
    source = ClaimedSource.from_dict(READING)
    assert (source.source_id, source.source_type, source.description) == ("S2", "advisory_fees", "Advisory work")
    assert (source.start_year, source.end_year, source.amount) == (2018, 2021, 125000.5)
    assert (source.country, source.quote, source.counterparty) == ("Hong Kong", "some advisory work",
                                                                   "Harbour Advisers Ltd")
    assert (source.linked_position_index, source.linked_asset_index) == (1, 0)
    assert source.occupation_mismatch is True and source.amount_explained is False
    assert source.counterparty_read()


def test_to_dict_gives_back_the_reading_exactly_key_order_too():
    source = ClaimedSource.from_dict(READING)
    assert json.dumps(source.to_dict()) == json.dumps(READING)
    assert list(source.to_dict()) == list(ClaimedSource.READING_KEYS)


def test_to_dict_keeps_the_order_the_ai_wrote_the_keys_in():
    reordered = dict(sorted(READING.items()))         # e.g. a reply with its keys in alphabetical order
    assert json.dumps(ClaimedSource.from_dict(reordered).to_dict()) == json.dumps(reordered)


def test_an_older_reading_without_counterparty_keeps_its_layout():
    old = {key: value for key, value in READING.items() if key not in ("counterparty", "occupation_mismatch")}
    source = ClaimedSource.from_dict(old)
    assert source.to_dict() == old and "counterparty" not in source.to_dict()
    assert not source.counterparty_read()
    assert source.counterparty is None and source.occupation_mismatch is False


def test_from_dict_reads_the_crime_scan_row():
    source = ClaimedSource.from_dict(ROW)
    assert (source.amount, source.country, source.quote) == (125000.5, "HK", "some advisory work")
    assert source.amount_explained is True and source.occupation_mismatch is True


def test_to_scan_dict_gives_back_the_saved_row_exactly_key_order_too():
    assert json.dumps(ClaimedSource.from_dict(ROW).to_scan_dict()) == json.dumps(ROW)


def test_the_scan_row_names_the_readings_facts_in_the_saved_layout():
    row = ClaimedSource.from_dict(READING).to_scan_dict()
    assert list(row) == ["source_id", "source_type", "description", "amount_sgd", "start_year", "end_year",
                         "jurisdiction", "counterparty", "evidence_sentence", "occupation_mismatch",
                         "amount_explained_by_forecast"]
    assert (row["amount_sgd"], row["jurisdiction"], row["evidence_sentence"]) == (125000.5, "Hong Kong",
                                                                                  "some advisory work")
    assert row["amount_explained_by_forecast"] is False


def test_a_null_text_field_in_a_dict_reads_as_empty_text():
    source = ClaimedSource.from_dict({"source_type": "salary", "description": None, "quote": None})
    assert source.description == ""
    assert source.quote == ""
    assert source.to_dict()["description"] == ""


def test_text_fields_reject_non_text():
    with pytest.raises(ValueError, match="description must be text"):
        ClaimedSource(description=None)
    with pytest.raises(ValueError, match="quote must be text"):
        ClaimedSource(quote=5)
    with pytest.raises(ValueError, match="type must be text"):
        ClaimedSource(source_type=["salary"])
    with pytest.raises(ValueError, match="country must be text"):
        ClaimedSource(country=3)
    with pytest.raises(ValueError, match="description must be text"):
        ClaimedSource.from_dict({"description": 12})
    assert ClaimedSource(country=None, counterparty=None, source_id=None).country is None
