"""CaseReader: a saved record read into one forecasting case, or a list of what is missing."""

import pytest

from app.logic.case_reader import CaseReader
from tests.logic_fixtures import sample_case


@pytest.mark.parametrize("text, number", [
    ("1,650,000", 1650000.0), ("S$1.65m", 1650000.0), ("410k", 410000.0), (30, 30.0), ("2 million", 2000000.0),
    ("45%", 45.0), ("sgd 500", 500.0)])
def test_read_amount_understands_the_ways_people_write_money(text, number):
    assert CaseReader.read_amount(text) == pytest.approx(number)


@pytest.mark.parametrize("text", ["a lot", "", None, True])
def test_read_amount_gives_none_for_what_it_cannot_read(text):
    assert CaseReader.read_amount(text) is None


def test_read_year_only_accepts_a_real_year():
    reader = CaseReader()
    assert reader.read_year("2017") == 2017
    assert reader.read_year("17") is None
    assert reader.read_year("present") is None


def test_a_complete_record_becomes_a_case():
    case, problems = CaseReader("2026-10-14").forecasting_case(sample_case())
    assert problems == []
    assert case["client_ref"] == sample_case()["client_ref"]
    assert case["current_date"] == "2026-10-14"
    assert case["career_history"][-1]["end_year"] is None


def test_money_typed_as_text_is_read_as_numbers():
    record = sample_case()
    record["claims"]["declared_net_worth"] = "S$16.5m"
    record["investments"][0]["price_paid"] = "1,650,000"
    case, problems = CaseReader("2026-10-14").forecasting_case(record)
    assert problems == []
    assert case["claims"]["declared_net_worth"] == 16500000
    assert case["investments"][0]["price_paid"] == 1650000


def test_a_record_with_gaps_lists_what_is_missing_instead_of_guessing():
    record = sample_case()
    record["claims"]["declared_net_worth"] = None
    record["investments"][0]["year_acquired"] = "sometime"
    case, problems = CaseReader("2026-10-14").forecasting_case(record)
    assert case is None
    assert len(problems) >= 2


def test_the_same_record_always_gives_the_same_case():
    reader = CaseReader("2026-10-14")
    assert reader.forecasting_case(sample_case()) == reader.forecasting_case(sample_case())


def test_crime_scan_input_holds_only_what_the_crime_scan_may_see():
    data = CaseReader().crime_scan_input(sample_case())
    assert set(data) == {"client_ref", "occupation", "industry", "age", "career_start_year", "country",
                         "country_of_residence", "declaration_text"}
    assert "declared_net_worth" not in data


def test_benchmark_input_gives_the_asset_split_in_whole_percents():
    case = sample_case()
    data, missing = CaseReader().benchmark_input(case, CaseReader().crime_scan_input(case))
    assert missing == []
    assert (data["property"], data["listed_equities"], data["private_business"], data["cash"]) == (28, 11, 41, 20)
    assert data["declared_net_worth"] == 16500000


def test_read_year_accepts_a_number_or_text_as_the_records_hold_both():
    """Saved records and form answers hold years as text or as numbers, so read_year takes either."""
    reader = CaseReader()
    assert reader.read_year("2017") == 2017
    assert reader.read_year(2017) == 2017
    assert reader.read_year(None) is None
