"""AuditFilter: each field valid and invalid, matching with a fixed now, paging, query and chips."""

from datetime import datetime, timezone

import pytest

from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)


def _event(at="2026-11-16T10:00:00Z", actor="Shareen", action="client_edited", ref="C-0007", result="ok"):
    return AuditEvent(at=at, actor=actor, action=action, client_ref=ref, result=result)


def test_the_defaults_are_the_last_7_days_and_page_1_with_no_problems():
    f = AuditFilter()
    assert (f.days, f.actor, f.group, f.client_ref, f.result, f.page) == (7, "", "", "", "", 1)
    assert f.problems() == [] and f.to_query() == {} and f.chips() == []


@pytest.mark.parametrize("kwargs, text", [
    ({"days": 5}, "days must be one of"), ({"days": True}, "days must be one of"),
    ({"actor": "x" * 81}, "actor"), ({"actor": 5}, "actor must be text"),
    ({"client_ref": "x" * 41}, "client reference"), ({"group": "Nope"}, "group must be"),
    ({"result": "maybe"}, "result must be"), ({"page": 0}, "page must be"), ({"page": "2"}, "page must be"),
])
def test_building_it_directly_refuses_impossible_values(kwargs, text):
    with pytest.raises(ValueError, match=text):
        AuditFilter(**kwargs)


def test_from_query_reads_every_field_and_trims_text():
    f = AuditFilter.from_query({"days": "30", "actor": " Shareen ", "group": "Client",
                                "client_ref": " c-0007", "result": "failed", "page": "3"})
    assert (f.days, f.actor, f.group, f.client_ref, f.result, f.page) == (30, "Shareen", "Client", "c-0007", "failed", 3)
    assert f.problems() == []


def test_from_query_with_nothing_gives_the_defaults():
    assert AuditFilter.from_query({}).to_query() == {} and AuditFilter.from_query({"days": "  "}).days == 7


def test_days_all_means_all_time():
    assert AuditFilter.from_query({"days": "ALL"}).days == 0


@pytest.mark.parametrize("value", ["5", "0", "-1", "week", "7.5", "١", "1" * 5000])
def test_a_bad_days_falls_back_to_7_and_says_what_is_allowed(value):
    f = AuditFilter.from_query({"days": value})
    assert f.days == 7
    assert f.problems() == ["'days' must be one of 1, 7, 30, 90 or all; showing the last 7 days."]


def test_a_group_is_matched_ignoring_case_and_a_bad_one_is_dropped():
    assert AuditFilter.from_query({"group": "documents"}).group == "Documents"
    f = AuditFilter.from_query({"group": "Everything"})
    assert f.group == "" and "'group' must be one of Sign-in, Client, Documents, Assessment, System" in f.problems()[0]


def test_a_bad_result_is_dropped_and_a_good_one_is_lower_cased():
    assert AuditFilter.from_query({"result": "OK"}).result == "ok"
    f = AuditFilter.from_query({"result": "maybe"})
    assert f.result == "" and f.problems() == ["'result' must be ok or failed; showing both."]


@pytest.mark.parametrize("value", ["0", "-2", "two", "1.5", "²", "9" * 5000])
def test_a_bad_page_falls_back_to_1(value):
    f = AuditFilter.from_query({"page": value})
    assert f.page == 1 and "'page' must be a whole number, 1 or more; showing page 1." in f.problems()


def test_a_too_long_actor_or_client_ref_is_dropped_with_a_reason():
    f = AuditFilter.from_query({"actor": "x" * 81, "client_ref": "y" * 41})
    assert f.actor == "" and f.client_ref == ""
    assert len(f.problems()) == 2 and "'actor'" in f.problems()[0] and "'client_ref'" in f.problems()[1]


def test_text_with_control_characters_is_dropped():
    f = AuditFilter.from_query({"actor": "a\x00b", "client_ref": "a\x07b"})
    assert f.actor == "" and f.client_ref == "" and len(f.problems()) == 2


def test_a_value_that_is_not_text_is_a_problem_not_a_crash():
    f = AuditFilter.from_query({"days": 7, "page": ["2"]})
    assert f.days == 7 and f.page == 1 and len(f.problems()) == 2


def test_several_bad_values_each_get_their_own_line_and_the_good_ones_are_kept():
    f = AuditFilter.from_query({"days": "x", "result": "bad", "actor": "Adrian"})
    assert f.actor == "Adrian" and len(f.problems()) == 2


def test_from_query_refuses_something_that_is_not_a_mapping():
    with pytest.raises(ValueError, match="mapping"):
        AuditFilter.from_query(None)


def test_problems_returns_a_copy():
    f = AuditFilter.from_query({"days": "x"})
    f.problems().clear()
    assert len(f.problems()) == 1


def test_matches_uses_the_period_ending_at_the_given_now():
    f = AuditFilter(days=1)
    assert f.matches(_event(at="2026-11-15T12:00:01Z"), NOW)
    assert not f.matches(_event(at="2026-11-15T11:59:59Z"), NOW)
    assert AuditFilter(days=0).matches(_event(at="2001-01-01T00:00:00Z"), NOW)      # all time
    assert AuditFilter().matches(_event(at="2026-11-09T12:00:00Z"), NOW)
    assert not AuditFilter().matches(_event(at="2026-11-09T11:59:59Z"), NOW)


@pytest.mark.parametrize("days", [0, 1, 7])
def test_matches_refuses_a_now_with_no_timezone(days):
    with pytest.raises(ValueError, match="now must carry a timezone"):
        AuditFilter(days=days).matches(_event(at="2026-11-16T10:00:00Z"), datetime(2026, 11, 16, 12, 0, 0))


def test_matches_refuses_a_now_that_is_not_a_datetime():
    with pytest.raises(ValueError, match="timezone"):
        AuditFilter().matches(_event(), "2026-11-16")


def test_matches_accepts_any_timezone():
    from datetime import timedelta
    singapore = timezone(timedelta(hours=8))
    assert AuditFilter(days=1).matches(_event(at="2026-11-16T10:00:00Z"), datetime(2026, 11, 16, 20, 0, tzinfo=singapore))


def test_matches_actor_and_client_ref_ignore_case_but_must_match_exactly():
    f = AuditFilter(actor="shareen", client_ref="c-0007")
    assert f.matches(_event(), NOW)
    assert not f.matches(_event(actor="Shareen Tan"), NOW)
    assert not f.matches(_event(ref="C-00071"), NOW)


def test_matches_group_and_result():
    assert AuditFilter(group="Client").matches(_event(), NOW)
    assert not AuditFilter(group="System").matches(_event(), NOW)
    assert AuditFilter(result="failed").matches(_event(result="failed"), NOW)
    assert not AuditFilter(result="failed").matches(_event(), NOW)


def test_matches_needs_every_filter_to_pass():
    f = AuditFilter(actor="Shareen", group="Client", result="ok")
    assert f.matches(_event(), NOW) and not f.matches(_event(actor="Adrian"), NOW)


def test_page_count_is_at_least_one():
    f = AuditFilter()
    assert [f.page_count(n) for n in (-3, 0, 1, 50, 51, 100, 101)] == [1, 1, 1, 1, 2, 2, 3]


def test_page_of_slices_fifty_at_a_time_and_clamps_a_page_past_the_end():
    events = [_event(ref=f"C-{n}") for n in range(120)]
    assert [e.client_ref for e in AuditFilter(page=1).page_of(events)] == [f"C-{n}" for n in range(50)]
    assert [e.client_ref for e in AuditFilter(page=3).page_of(events)] == [f"C-{n}" for n in range(100, 120)]
    assert AuditFilter(page=99).page_of(events) == AuditFilter(page=3).page_of(events)
    assert AuditFilter().page_of([]) == []


def test_to_query_holds_only_values_that_are_not_the_default():
    f = AuditFilter(days=0, actor="Shareen", group="Client", client_ref="C-1", result="ok", page=2)
    assert f.to_query() == {"days": "all", "actor": "Shareen", "group": "Client", "client_ref": "C-1",
                            "result": "ok", "page": "2"}
    assert AuditFilter(days=30).to_query() == {"days": "30"}


def test_a_query_survives_a_round_trip_through_from_query():
    f = AuditFilter(days=90, actor="Wei Yu", result="failed", page=4)
    again = AuditFilter.from_query(f.to_query())
    assert again.to_query() == f.to_query() and again.problems() == []


def test_chips_name_each_active_filter_in_plain_words():
    f = AuditFilter(days=0, actor="Shareen", group="Client", client_ref="C-1", result="failed", page=3)
    assert f.chips() == [("Period", "All time"), ("Officer", "Shareen"), ("Group", "Client"),
                         ("Client", "C-1"), ("Result", "Failed")]
    assert AuditFilter(days=1).chips() == [("Period", "Last 24 hours")]
    assert AuditFilter(days=90, result="ok").chips() == [("Period", "Last 90 days"), ("Result", "OK")]


def test_page_for_is_the_chosen_page_clamped_to_the_last():
    assert AuditFilter(page=2).page_for(120) == 2
    assert AuditFilter(page=99).page_for(120) == 3
    assert AuditFilter(page=5).page_for(0) == 1 and AuditFilter().page_for(10) == 1


def test_page_of_shows_the_page_that_page_for_names():
    events = [_event(ref=f"C-{n}") for n in range(120)]
    for page in (1, 2, 3, 9):
        f = AuditFilter(page=page)
        start = (f.page_for(len(events)) - 1) * AuditFilter.PAGE_SIZE
        assert f.page_of(events) == events[start:start + AuditFilter.PAGE_SIZE]
