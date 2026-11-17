"""OverviewPage: the numbers and the page of flags the Overview shows."""

from datetime import date, datetime

import pytest

from app.model.flag import Flag
from app.model.flag_ticket import FlagTicket
from app.model.overview_page import OverviewPage


def _ticket(number=1):
    return FlagTicket(Flag(Flag.make_id("hours", "SOW-1", number), "hours", "low", "SOW-1", "Late edit",
                           "", [number], "2026-11-13T06:05:00Z"))


def test_an_empty_page_has_every_count_at_zero():
    page = OverviewPage()
    assert (page.preset, page.tab, page.page, page.page_count) == ("7", "handle", 1, 1)
    assert (page.to_handle, page.open_flags, page.actions, page.failures, page.unreadable) == (0, 0, 0, 0, 0)
    assert page.intact and page.broken_at == 0
    assert (page.actions_change, page.failures_change) == (None, None)
    assert page.rows == [] and page.flags_by_type == [] and page.failures_by_day == []
    assert page.severity_counts == {"high": 0, "medium": 0, "low": 0}
    assert set(page.tab_counts) == set(OverviewPage.TABS)


def test_the_values_are_kept():
    days = [("2026-11-14", {"Save failed": 2}), ("2026-11-15", {"Save failed": 0})]
    types = [("hours", "After-hours activity", 2, 100)]
    page = OverviewPage("30", date(2026, 10, 17), date(2026, 11, 15), 5, 3, 2, 120, 79, 6, -50, 303, days, types,
                        {"high": 1, "medium": 1, "low": 0}, "review", {**dict.fromkeys(OverviewPage.TABS, 1)},
                        [_ticket(1), _ticket(2)], 2, 3, 4, {"hours": "low"})
    assert (page.preset, page.day_from, page.day_to) == ("30", date(2026, 10, 17), date(2026, 11, 15))
    assert (page.to_handle, page.not_started, page.in_progress) == (5, 3, 2)
    assert (page.actions, page.actions_change, page.failures, page.failures_change) == (120, 79, 6, -50)
    assert page.broken_at == 303 and not page.intact
    assert page.failures_by_day == days and page.flags_by_type == types
    assert (page.tab, page.page, page.page_count, page.unreadable) == ("review", 2, 3, 4)
    assert [row.flag.flag_id for row in page.rows] == ["F-HOU-SOW-1-1", "F-HOU-SOW-1-2"]
    assert page.type_severity == {"hours": "low"}


def test_what_comes_back_is_a_copy():
    page = OverviewPage(failures_by_day=[("2026-11-15", {"Save failed": 1})], rows=[_ticket()])
    page.rows.clear()
    page.tab_counts["all"] = 9
    page.severity_counts["high"] = 9
    page.failures_by_day[0][1]["Save failed"] = 9
    assert len(page.rows) == 1 and page.tab_counts["all"] == 0
    assert page.severity_counts["high"] == 0 and page.failures_by_day[0][1]["Save failed"] == 1


@pytest.mark.parametrize("kwargs", [
    {"preset": "1"}, {"preset": "custom"}, {"tab": "done"}, {"tab": ""},
    {"day_from": "2026-11-01"}, {"day_to": datetime(2026, 11, 1)},
    {"day_from": date(2026, 11, 2), "day_to": date(2026, 11, 1)},
    {"to_handle": -1, "not_started": -1}, {"actions": -1}, {"failures": True}, {"broken_at": -1},
    {"unreadable": "2"}, {"actions_change": 1.5}, {"failures_change": True},
    {"to_handle": 3, "not_started": 1, "in_progress": 1},
    {"page": 0}, {"page_count": 0}, {"page": 3, "page_count": 2},
    {"failures_by_day": "x"}, {"failures_by_day": [("2026-11-15",)]}, {"failures_by_day": [("15 Nov", {})]},
    {"failures_by_day": [("2026-13-45", {})]}, {"failures_by_day": [("2026-11-15", {"Save failed": -1})]},
    {"failures_by_day": [("2026-11-15", [])]},
    {"flags_by_type": "x"}, {"flags_by_type": [("hours", "After hours", 1)]},
    {"flags_by_type": [("bogus", "x", 1, 10)]}, {"flags_by_type": [("hours", "", 1, 10)]},
    {"flags_by_type": [("hours", "x", 0, 10)]}, {"flags_by_type": [("hours", "x", 1, 101)]},
    {"type_severity": "x"}, {"type_severity": {"hours": "low"}},
    {"flags_by_type": [("hours", "x", 1, 10)], "type_severity": {"hours": "urgent"}},
    {"flags_by_type": [("hours", "x", 1, 10)], "type_severity": {"hours": "low", "spike": "low"}},
    {"severity_counts": {"high": 1}}, {"severity_counts": {"high": 1, "medium": 0, "low": -1}},
    {"tab_counts": {"handle": 1}}, {"tab_counts": "x"},
    {"rows": ["x"]}, {"rows": "x"}, {"rows": [_ticket(n) for n in range(1, 8)]},
])
def test_an_impossible_value_is_refused(kwargs):
    with pytest.raises(ValueError):
        OverviewPage(**kwargs)


def test_a_full_page_of_six_is_allowed():
    assert len(OverviewPage(rows=[_ticket(n) for n in range(1, 7)]).rows) == OverviewPage.PAGE_SIZE


def test_the_size_of_the_log_and_the_entries_behind_each_row_are_kept_and_checked():
    from app.model.audit_event import AuditEvent
    entry = AuditEvent(sequence=3, action="assessment_run")
    page = OverviewPage(rows=[_ticket(3)], entries=9, evidence={"F-HOU-SOW-1-3": [entry]})
    assert page.entries == 9 and page.evidence("F-HOU-SOW-1-3") == [entry] and page.evidence("F-X") == []
    page.evidence("F-HOU-SOW-1-3").clear()
    assert len(page.evidence("F-HOU-SOW-1-3")) == 1                      # a copy
    for bad in ({"entries": -1}, {"entries": True}, {"evidence": {"F-HOU-SOW-1-3": [entry]}},
                {"rows": [_ticket(3)], "evidence": {"F-HOU-SOW-1-3": ["x"]}},
                {"rows": [_ticket(3)], "evidence": {"F-HOU-SOW-1-3": entry}}, {"evidence": "x"}):
        with pytest.raises(ValueError):
            OverviewPage(**bad)


def test_a_page_says_whether_the_earlier_range_is_covered_and_keeps_the_plain_differences():
    page = OverviewPage()
    assert page.has_previous is False and page.actions_diff == 0 and page.failures_diff == 0
    page = OverviewPage(has_previous=True, actions_diff=-3, failures_diff=2)
    assert page.has_previous and page.actions_diff == -3 and page.failures_diff == 2
    for kwargs in ({"has_previous": "yes"}, {"actions_diff": 1.5}, {"failures_diff": True}):
        with pytest.raises(ValueError):
            OverviewPage(**kwargs)
