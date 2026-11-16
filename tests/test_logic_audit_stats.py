"""AuditStats: counts in a range and the range before, failures by day, ticket counts, flags by type."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.logic.audit_stats import AuditStats
from app.model.audit_event import AuditEvent
from app.model.flag import Flag
from app.model.flag_ticket import FlagTicket

SGT = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=SGT)


def _event(day: date, action="client_edited", result="ok", hour=10, sequence=1) -> AuditEvent:
    moment = datetime(day.year, day.month, day.day, hour, 0, tzinfo=SGT).astimezone(timezone.utc)
    return AuditEvent(sequence=sequence, at=moment.strftime(AuditEvent.TIME_FORMAT), action=action, result=result)


def _events(*specs) -> list[AuditEvent]:
    """specs are (day, action, result); the sequence is the position."""
    return [_event(day, action, result, sequence=number) for number, (day, action, result) in enumerate(specs, 1)]


def _flag(kind="other", severity="medium", raised=date(2026, 11, 14), number=1) -> Flag:
    prefix = kind[:3].upper()
    day = "2026-11-14" if kind == "spike" else ""
    moment = datetime(raised.year, raised.month, raised.day, 9, 0, tzinfo=SGT)
    return Flag(f"F-{prefix}-{number}", kind, severity, "" if kind == "spike" else "SOW-1", "A flag", "",
                (number,), moment.isoformat(), "Owner", day=day)


def _ticket(flag: Flag, status: str) -> FlagTicket:
    if status == "open":
        return FlagTicket(flag, [])
    to = AuditEvent(sequence=50, actor="Admin", action="flag_updated",
                    details={"flag_id": flag.flag_id, "from": "open", "to": status, "note": "Looked at it.",
                             "waiting_on": "IT support" if status == "followup" else "",
                             "outcome": "legit" if status == "resolved" else ""})
    return FlagTicket(flag, [to])


D = date(2026, 11, 15)


def _stats(events=None, flags=None, tickets=None, first=date(2026, 11, 9), last=D):
    return AuditStats(events, flags, tickets, first, last, NOW)


# ---------- the range and the range before ----------

def test_actions_count_the_range_and_the_same_length_range_just_before():
    events = _events((date(2026, 11, 8), "signed_in", "ok"), (date(2026, 11, 2), "signed_in", "ok"),
                     (date(2026, 11, 1), "signed_in", "ok"),                       # before the earlier range
                     (date(2026, 11, 9), "signed_in", "ok"), (date(2026, 11, 15), "signed_in", "ok"),
                     (date(2026, 11, 16), "signed_in", "ok"))                      # after the range
    stats = _stats(events)
    assert (stats.length, stats.actions, stats.actions_before) == (7, 2, 2)
    assert (stats.day_from, stats.day_to) == (date(2026, 11, 9), D)


def test_the_range_includes_both_end_days_and_the_edges_of_the_earlier_range():
    events = _events((date(2026, 11, 1), "signed_in", "ok"), (date(2026, 11, 2), "signed_in", "ok"),
                     (date(2026, 11, 8), "signed_in", "ok"), (date(2026, 11, 9), "signed_in", "ok"))
    stats = _stats(events)
    assert stats.actions_before == 2 and stats.actions == 1


def test_events_are_placed_on_their_singapore_day():
    late = AuditEvent(sequence=1, at="2026-11-15T17:00:00Z", action="signed_in")        # 16 Nov 01:00 in Singapore
    assert _stats([late]).actions == 0
    assert AuditStats([late], [], {}, date(2026, 11, 16), date(2026, 11, 16), NOW).actions == 1


def test_failures_use_the_failure_kinds_and_the_two_ranges():
    events = _events((D, "assessment_failed", "ok"), (D, "client_edited", "failed"), (D, "client_edited", "ok"),
                     (date(2026, 11, 3), "data_unavailable", "ok"), (date(2026, 11, 4), "cloud_sync", "failed"),
                     (date(2026, 11, 5), "cloud_sync", "ok"))
    stats = _stats(events)
    assert (stats.failures, stats.failures_before) == (2, 2)


def test_a_single_day_range_compares_with_the_day_before():
    events = _events((D, "signed_in", "ok"), (D, "signed_in", "ok"), (D - timedelta(days=1), "signed_in", "ok"))
    stats = AuditStats(events, [], {}, D, D, NOW)
    assert (stats.length, stats.actions, stats.actions_before) == (1, 2, 1)


def test_without_a_range_it_is_the_singapore_day_of_now_and_without_now_a_fixed_day():
    assert (AuditStats(now=NOW).day_from, AuditStats(now=NOW).day_to) == (D, D)
    assert AuditStats().day_from == date(1970, 1, 1)


# ---------- change_percent ----------

def test_change_percent_is_the_signed_whole_percent_of_the_earlier_count():
    stats = _stats(_events((date(2026, 11, 1), "signed_in", "ok")))
    assert stats.has_previous
    assert stats.change_percent(179, 100) == 79 and stats.change_percent(8, 3) == 167
    assert stats.change_percent(50, 100) == -50 and stats.change_percent(5, 5) == 0
    assert stats.change_percent(1, 3) == -67 and stats.change_percent(0, 4) == -100


def test_change_percent_rounds_half_up_away_from_zero():
    stats = _stats(_events((date(2026, 11, 1), "signed_in", "ok")))
    assert stats.change_percent(1005, 1000) == 1 and stats.change_percent(995, 1000) == -1
    assert stats.change_percent(201, 8) == 2413


def test_change_percent_is_none_when_nothing_came_before():
    stats = _stats(_events((date(2026, 11, 1), "signed_in", "ok")))
    assert stats.change_percent(5, 0) is None and stats.change_percent(0, 0) is None


def test_change_percent_is_none_when_the_earlier_range_starts_before_the_first_event():
    stats = _stats(_events((date(2026, 11, 3), "signed_in", "ok")))                 # the earlier range starts 2 Nov
    assert not stats.has_previous and stats.change_percent(5, 2) is None
    assert not _stats([]).has_previous


def test_the_earlier_range_may_start_exactly_on_the_first_event_day():
    assert _stats(_events((date(2026, 11, 2), "signed_in", "ok"))).has_previous


@pytest.mark.parametrize("now_count,before_count", [(-1, 1), (1, -1), (1.5, 1), (True, 1), ("1", 1)])
def test_change_percent_refuses_counts_that_cannot_be_counts(now_count, before_count):
    with pytest.raises(ValueError, match="whole numbers"):
        _stats([]).change_percent(now_count, before_count)


# ---------- failures by day ----------

def test_failures_by_day_lists_every_day_in_order_with_zeros():
    events = _events((date(2026, 11, 10), "assessment_failed", "ok"), (date(2026, 11, 10), "assessment_failed", "ok"),
                     (date(2026, 11, 10), "data_unavailable", "ok"), (date(2026, 11, 12), "cloud_sync", "failed"),
                     (date(2026, 11, 12), "assessment_run", "failed"), (date(2026, 11, 8), "assessment_failed", "ok"),
                     (date(2026, 11, 11), "client_edited", "ok"))
    rows = _stats(events).failures_by_day()
    assert [day for day, _ in rows] == [date(2026, 11, 9) + timedelta(days=n) for n in range(7)]
    zero = {"AI step not run": 0, "Save failed": 0, "Read failed": 0, "Sync failed": 0}
    by_day = dict(rows)
    assert by_day[date(2026, 11, 9)] == zero and by_day[date(2026, 11, 11)] == zero
    assert by_day[date(2026, 11, 10)] == {**zero, "AI step not run": 2, "Read failed": 1}
    assert by_day[date(2026, 11, 12)] == {**zero, "Sync failed": 1, "Save failed": 1}
    assert sum(sum(counts.values()) for _, counts in rows) == _stats(events).failures == 5


def test_failures_by_day_hands_out_a_fresh_dict_each_time():
    stats = _stats([])
    stats.failures_by_day()[0][1]["Save failed"] = 9
    assert stats.failures_by_day()[0][1]["Save failed"] == 0


# ---------- flags to handle ----------

def test_to_handle_not_started_and_in_progress_come_from_the_tickets():
    flags = [_flag(number=n) for n in range(1, 6)]
    tickets = {flags[0].flag_id: _ticket(flags[0], "review"), flags[1].flag_id: _ticket(flags[1], "followup"),
               flags[2].flag_id: _ticket(flags[2], "resolved"), flags[3].flag_id: _ticket(flags[3], "open")}
    stats = _stats(flags=flags, tickets=tickets)                       # flags[4] has no ticket: Open
    assert (stats.to_handle, stats.not_started, stats.in_progress) == (4, 2, 2)


def test_the_flag_counts_ignore_the_date_range_and_no_flags_is_zero():
    old = _flag(raised=date(2026, 1, 1))
    assert _stats(flags=[old]).to_handle == 1
    stats = _stats()
    assert (stats.to_handle, stats.not_started, stats.in_progress, stats.open_flags_in_range) == (0, 0, 0, 0)


# ---------- flags by type ----------

def test_flags_by_type_counts_unresolved_flags_raised_in_the_range_with_percentages():
    flags = [_flag("other", "medium", number=1), _flag("other", "high", number=2), _flag("hours", "low", number=3),
             _flag("shop", "high", number=4), _flag("repeat", "medium", number=5),
             _flag("hours", "low", raised=date(2026, 11, 1), number=6),        # outside the range
             _flag("spike", "medium", number=7)]                               # resolved below
    tickets = {flags[6].flag_id: _ticket(flags[6], "resolved")}
    stats = _stats(flags=flags, tickets=tickets)
    assert stats.open_flags_in_range == 5
    assert stats.flags_by_type() == [("other", "Edited by non-owner", 2, 40), ("shop", "Verdict jump after edit", 1, 20),
                                     ("repeat", "Repeated assessments", 1, 20), ("hours", "After-hours activity", 1, 20)]
    assert stats.severity_counts() == {"high": 2, "medium": 2, "low": 1}
    assert stats.type_severity() == {"other": "medium", "hours": "low", "shop": "high", "repeat": "medium"}


def test_percentages_round_half_up_and_an_empty_range_gives_nothing():
    flags = [_flag("other", number=n) for n in range(1, 3)] + [_flag("hours", "low", number=3)]
    assert [row[3] for row in _stats(flags=flags).flags_by_type()] == [67, 33]
    stats = _stats(flags=[_flag(raised=date(2026, 10, 1))])
    assert stats.flags_by_type() == [] and stats.severity_counts() == {"high": 0, "medium": 0, "low": 0}


def test_a_flag_is_placed_on_its_singapore_day():
    late = Flag("F-OTH-1", "other", "medium", "SOW-1", "A flag", "", (1,), "2026-11-14T17:00:00Z", "Owner")   # 15 Nov in Singapore
    assert _stats(flags=[late], first=D, last=D).open_flags_in_range == 1
    assert _stats(flags=[late], first=date(2026, 11, 14), last=date(2026, 11, 14)).open_flags_in_range == 0


# ---------- inputs ----------

@pytest.mark.parametrize("kwargs,text", [
    ({"events": "x"}, "audit events"), ({"events": [1]}, "audit events"), ({"flags": [1]}, "list of flags"),
    ({"tickets": []}, "dict of flag id"), ({"tickets": {"F-1": 1}}, "dict of flag id"),
    ({"day_from": "2026-11-01"}, "day_from must be a date"), ({"day_to": datetime(2026, 11, 1)}, "day_to must be a date"),
    ({"day_from": date(2026, 11, 3), "day_to": date(2026, 11, 2)}, "end before"),
    ({"now": datetime(2026, 11, 1)}, "timezone"),
])
def test_wrong_inputs_are_refused(kwargs, text):
    with pytest.raises(ValueError, match=text):
        AuditStats(**kwargs)
