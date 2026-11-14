"""Job: one position in the career history."""

import pytest

from app.model.job import Job


def _job(start=2017, end=None, **extra):
    return Job(start, end, "Chief Operating Officer", "C-suite", "Shipping", "Straits Harbour",
               "1,000-5,000 employees", "Singapore", **extra)


def test_a_job_with_no_end_year_is_the_current_job():
    assert _job().is_current()
    assert not _job(2009, 2013).is_current()


def test_end_or_gives_this_year_for_the_current_job():
    assert _job().end_or(2026) == 2026
    assert _job(2009, 2013).end_or(2026) == 2013


def test_a_job_rejects_a_year_that_is_not_a_whole_year():
    with pytest.raises(ValueError):
        _job(start="2017")
    with pytest.raises(ValueError):
        _job(start=17)
    job = _job()
    with pytest.raises(ValueError):
        job.end_year = 20.5


def test_a_job_that_ends_before_it_starts_reports_a_problem():
    assert _job(2013, 2009).problems() == ["ends (2009) before it starts (2013)"]
    assert _job(2009, 2013).problems() == []


def test_years_can_be_corrected_through_the_setters():
    job = _job(2013, 2009)
    job.end_year = 2015
    assert job.problems() == []
    assert (job.start_year, job.end_year) == (2013, 2015)


def test_to_dict_keeps_the_saved_layout_and_any_extra_details():
    data = _job(2009, 2013, extra={"notes": "secondment"}).to_dict()
    assert data["start_year"] == 2009 and data["end_year"] == 2013
    assert data["occupation"] == "Chief Operating Officer"
    assert data["country"] == "Singapore"
    assert data["notes"] == "secondment"
