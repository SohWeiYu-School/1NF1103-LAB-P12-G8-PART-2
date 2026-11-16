"""CaseTimeline: it rejects starting values no case can have."""

import pytest

from app.logic.case_timeline import CaseTimeline


@pytest.mark.parametrize("years", [0, -5, 2.5, "4", None, True])
def test_the_forecast_years_must_be_a_whole_number_of_one_or_more(years):
    with pytest.raises(ValueError, match="forecast years must be a whole number of 1 or more"):
        CaseTimeline({}, years)


@pytest.mark.parametrize("record", ["case", [1, 2], 5])
def test_the_record_must_be_a_dict_or_none(record):
    with pytest.raises(ValueError, match="record must be a dict"):
        CaseTimeline(record)


def test_valid_starting_values_still_work():
    assert len(CaseTimeline({"current_date": "2026-01-01"}, 3).future_years()) == 3
