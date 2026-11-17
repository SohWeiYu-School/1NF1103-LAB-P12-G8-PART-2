"""AuditPage: the events of one page and the counts around them."""

import pytest

from app.model.audit_event import AuditEvent
from app.model.audit_page import AuditPage


def _event():
    return AuditEvent(actor="Shareen", action="signed_in")


def test_an_empty_page_has_every_count_at_zero():
    page = AuditPage()
    assert (page.events, page.total, page.unreadable, page.everything, page.officers, page.failed) == ([], 0, 0, 0, 0, 0)
    assert page.open_flags == 0


def test_the_values_are_kept_and_events_come_back_as_a_copy():
    events = [_event(), _event()]
    page = AuditPage(events, 30, 2, 100, 3, 4)
    assert (page.total, page.unreadable, page.everything, page.officers, page.failed) == (30, 2, 100, 3, 4)
    page.events.append(_event())
    assert len(page.events) == 2


@pytest.mark.parametrize("kwargs", [{"events": ["x"]}, {"total": -1}, {"open_flags": -1}, {"open_flags": True}, {"open_flags": "2"}])
def test_an_impossible_value_is_refused(kwargs):
    with pytest.raises(ValueError):
        AuditPage(**kwargs)


@pytest.mark.parametrize("kwargs", [
    {"events": [_event()], "total": 0, "everything": 5},        # more on the page than match
])
def test_counts_that_do_not_fit_together_are_refused(kwargs):
    with pytest.raises(ValueError, match="do not fit"):
        AuditPage(**kwargs)


def test_the_open_flag_count_is_kept_and_does_not_depend_on_the_filter_counts():
    assert AuditPage([], 0, 0, 0, 0, 0, 7).open_flags == 7


def test_the_flagged_entries_of_the_page_are_kept_and_must_belong_to_it():
    events = [AuditEvent(sequence=2, action="signed_in"), AuditEvent(sequence=3, action="signed_in")]
    assert AuditPage(events, 2, 0, 2, 0, 0, 1, [3]).flagged == frozenset({3})
    assert AuditPage().flagged == frozenset()
    for bad in ([9], [True], "3", [None]):
        with pytest.raises(ValueError, match="flagged"):
            AuditPage(events, 2, 0, 2, 0, 0, 1, bad)


def test_a_page_whose_flags_could_not_be_worked_out_has_no_open_flag_count():
    page = AuditPage([_event()], 1, 0, 1, 1, 0, None, (), False, 0)
    assert page.flags_ok is False and page.open_flags is None and page.flagged == frozenset()
    assert AuditPage().flags_ok is True and AuditPage().flags_skipped == 0
    assert AuditPage(flags_skipped=2).flags_skipped == 2


@pytest.mark.parametrize("kwargs", [{"flags_ok": False, "open_flags": 0}, {"flags_ok": False, "open_flags": None, "flagged": [1],
                                                                          "events": [AuditEvent(sequence=1, actor="A", action="signed_in")], "total": 1, "everything": 1},
                                    {"open_flags": None}, {"flags_ok": "no"}, {"flags_skipped": -1}])
def test_the_flags_state_must_fit_together(kwargs):
    with pytest.raises(ValueError):
        AuditPage(**kwargs)
