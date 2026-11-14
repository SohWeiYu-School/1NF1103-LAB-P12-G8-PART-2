"""Formatter and CaseTimeline: money text, review dates and the years of a case."""

import pytest

from app.logic.case_timeline import CaseTimeline
from app.logic.formatter import Formatter

CASE = {"current_date": "2026-09-24",
        "career": {"occupation": "COO", "career_start_year": 1998},
        "career_history": [{"start_year": 1998, "end_year": 2016, "occupation": "Planner"},
                           {"start_year": 2017, "end_year": None, "occupation": "COO"}]}


@pytest.mark.parametrize("value, text", [(12345.6, "S$12,346"), (0, "S$0"), (-2500, "-S$2,500"),
                                         (None, "n/a"), ("12", "n/a"), (True, "n/a")])
def test_sgd_writes_money_and_copes_with_non_numbers(value, text):
    assert Formatter.sgd(value) == text


@pytest.mark.parametrize("start, months, end", [
    ("2026-09-24", 3, "2026-12-24"), ("2026-09-24", 6, "2027-03-24"), ("2026-11-30", 3, "2027-02-28"),
    ("2024-01-31", 1, "2024-02-29"), ("2026-12-15", 12, "2027-12-15")])
def test_add_months_clips_the_day_to_the_month(start, months, end):
    assert Formatter.add_months(start, months) == end


def test_formatter_needs_no_object():
    assert Formatter().sgd(5) == Formatter.sgd(5)


def test_timeline_reads_the_years_of_a_case():
    timeline = CaseTimeline(CASE)
    assert timeline.current_year() == 2026
    assert timeline.career_years() == (1998, 2026)
    assert timeline.future_years() == [2027, 2028, 2029, 2030]


def test_the_current_job_runs_to_this_year():
    timeline = CaseTimeline(CASE)
    first, current = timeline.positions()
    assert timeline.position_end(first) == 2016
    assert timeline.position_end(current) == 2026


def test_with_no_history_the_current_job_is_the_only_position():
    timeline = CaseTimeline({"current_date": "2026-09-24", "career": {"occupation": "COO", "career_start_year": 2005}})
    assert timeline.positions() == [{"occupation": "COO", "career_start_year": 2005,
                                     "start_year": 2005, "end_year": None}]
    assert timeline.career_years() == (2005, 2026)


def test_the_number_of_forecast_years_can_be_changed():
    assert CaseTimeline(CASE, forecast_years=2).future_years() == [2027, 2028]
