"""TrailFilter: the Show and When choices above a client's History."""

from datetime import datetime, timezone

import pytest

from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.trail_filter import TrailFilter

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)


def _event(action="client_edited", at="2026-11-16T10:00:00Z"):
    return AuditEvent(at=at, actor="Shareen", action=action, client_ref="C-0007")


def test_the_defaults_show_everything_for_all_time():
    f = TrailFilter()
    assert (f.show, f.when, f.date_from, f.date_to, f.problems(), f.to_query()) == ("all", "all", "", "", [], {})
    assert f.matches(_event(at="2001-01-01T00:00:00Z"), NOW)


@pytest.mark.parametrize("kwargs, text", [
    ({"show": "everything"}, "show choice"), ({"when": "yesterday"}, "when choice"), ({"date_from": 5}, "text"),
    ({"when": "custom", "date_from": "2026/11/01"}, "year-month-day"),
    ({"when": "custom", "date_from": "2026-11-05", "date_to": "2026-11-04"}, "on or before"),
])
def test_building_it_directly_refuses_impossible_values(kwargs, text):
    with pytest.raises(ValueError, match=text):
        TrailFilter(**kwargs)


def test_show_chooses_the_groups():
    edit, assess = _event("client_edited"), _event("assessment_run")
    upload, sign = _event("document_uploaded"), _event("signed_in")
    assert [TrailFilter(show="edits").matches(e, NOW) for e in (edit, assess, upload, sign)] == [True, False, False, False]
    assert [TrailFilter(show="assessments").matches(e, NOW) for e in (edit, assess, upload, sign)] == [False, True, False, False]
    assert [TrailFilter(show="documents").matches(e, NOW) for e in (edit, assess, upload, sign)] == [False, False, True, False]


def test_when_chooses_singapore_days_back_from_today():
    f = TrailFilter(when="7")
    assert f.matches(_event(at="2026-11-10T00:00:00Z"), NOW) and not f.matches(_event(at="2026-11-09T15:59:00Z"), NOW)
    assert TrailFilter(when="custom", date_from="2026-11-10", date_to="2026-11-12").matches(_event(at="2026-11-11T00:00:00Z"), NOW)
    assert not TrailFilter(when="custom", date_from="2026-11-10", date_to="2026-11-12").matches(_event(), NOW)


def test_from_query_reads_every_value():
    f = TrailFilter.from_query({"show": "Edits", "when": "custom", "from": "2026-11-10", "to": "2026-11-12"}, NOW)
    assert (f.show, f.when, f.date_from, f.date_to, f.problems()) == ("edits", "custom", "2026-11-10", "2026-11-12", [])
    assert f.to_query() == {"show": "edits", "when": "custom", "from": "2026-11-10", "to": "2026-11-12"}


def test_bad_show_and_when_fall_back_with_plain_lines():
    f = TrailFilter.from_query({"show": "all-of-it", "when": "soon", "from": "x"}, NOW)
    assert (f.show, f.when) == ("all", "all")
    assert f.problems() == ["'show' must be one of all, edits, assessments, documents; showing all.",
                            "'when' must be one of all, 7, 30, 90, custom; showing all time."]


@pytest.mark.parametrize("args, problem", [
    ({"when": "custom"}, AuditFilter.PROBLEM_BOTH_DATES),
    ({"when": "custom", "from": "2026-11-10"}, AuditFilter.PROBLEM_BOTH_DATES),
    ({"when": "custom", "from": "2026-11-12", "to": "2026-11-10"}, AuditFilter.PROBLEM_DATE_ORDER),
    ({"when": "custom", "from": "2026-11-10", "to": "2026-12-10"}, AuditFilter.PROBLEM_FUTURE),
    ({"when": "custom", "from": "nov", "to": "2026-11-10"}, AuditFilter.PROBLEM_DATE_FORMAT),
])
def test_a_bad_custom_range_says_why_and_shows_all_dates_for_now(args, problem):
    f = TrailFilter.from_query(args, NOW)
    assert f.problems() == [problem] and f.when == "custom" and f.day_range(NOW) is None
    assert f.matches(_event(at="2001-01-01T00:00:00Z"), NOW)


def test_a_value_that_is_not_text_is_a_problem_not_a_crash():
    assert len(TrailFilter.from_query({"show": 5}, NOW).problems()) == 1


def test_from_query_refuses_what_is_not_a_mapping_and_matches_a_now_without_a_timezone():
    with pytest.raises(ValueError, match="mapping"):
        TrailFilter.from_query("show=all", NOW)
    with pytest.raises(ValueError, match="timezone"):
        TrailFilter(when="7").matches(_event(), datetime(2026, 11, 16))
