"""AuditPage: the events of one page and the counts around them."""

import pytest

from app.model.audit_event import AuditEvent
from app.model.audit_page import AuditPage


def _event():
    return AuditEvent(actor="Shareen", action="signed_in")


def test_an_empty_page_has_every_count_at_zero():
    page = AuditPage()
    assert (page.events, page.total, page.unreadable, page.everything, page.officers, page.failed) == ([], 0, 0, 0, 0, 0)


def test_the_values_are_kept_and_events_come_back_as_a_copy():
    events = [_event(), _event()]
    page = AuditPage(events, 30, 2, 100, 3, 4)
    assert (page.total, page.unreadable, page.everything, page.officers, page.failed) == (30, 2, 100, 3, 4)
    page.events.append(_event())
    assert len(page.events) == 2


@pytest.mark.parametrize("kwargs", [{"events": ["x"]}, {"total": -1}])
def test_an_impossible_value_is_refused(kwargs):
    with pytest.raises(ValueError):
        AuditPage(**kwargs)


@pytest.mark.parametrize("kwargs", [
    {"events": [_event()], "total": 0, "everything": 5},        # more on the page than match
])
def test_counts_that_do_not_fit_together_are_refused(kwargs):
    with pytest.raises(ValueError, match="do not fit"):
        AuditPage(**kwargs)
