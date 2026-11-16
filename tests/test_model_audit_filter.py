"""AuditFilter: each field valid and invalid, Singapore days with a fixed now, search, paging, query and chips."""

from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.datastructures import MultiDict

from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)          # 20:00 on 16 Nov in Singapore


def _event(at="2026-11-16T10:00:00Z", actor="Shareen", action="client_edited", ref="C-0007", result="ok", details=None):
    return AuditEvent(at=at, actor=actor, action=action, client_ref=ref, result=result, details=details)


def test_the_defaults_are_the_last_7_days_every_group_newest_first_and_page_1_with_no_problems():
    f = AuditFilter()
    assert (f.preset, f.date_from, f.date_to, f.groups, f.result) == ("7", "", "", tuple(AuditEvent.GROUPS), "all")
    assert (f.actor, f.client_ref, f.query, f.sort, f.page) == ("", "", "", "desc", 1)
    assert f.all_groups() is True and f.problems() == [] and f.to_query() == {} and f.chips() == []
    assert AuditFilter.PAGE_SIZE == 25


@pytest.mark.parametrize("kwargs, text", [
    ({"preset": "5"}, "preset must be one of"),
    ({"date_from": "15/11/2026", "preset": "custom"}, "start date must look like"),
    ({"date_to": "2026-13-01", "preset": "custom"}, "end date must look like"),
    ({"preset": "custom", "date_from": "2026-11-10", "date_to": "2026-11-09"}, "on or before"),
    ({"groups": []}, "At least one group"), ({"groups": ["Nope"]}, "group must be one of"),
    ({"result": "maybe"}, "result must be"), ({"result": ""}, "result must be"), ({"sort": "up"}, "sort must be"),
    ({"actor": "x" * 81}, "actor"),
    ({"client_ref": "x" * 41}, "client reference"), ({"query": "x" * 81}, "search text"),
    ({"query": "a\x07b"}, "search text"),
    ({"page": 0}, "page must be"),
])
def test_building_it_directly_refuses_impossible_values(kwargs, text):
    with pytest.raises(ValueError, match=text):
        AuditFilter(**kwargs)


def test_dates_are_kept_only_for_a_custom_range_and_a_missing_one_means_all_dates():
    assert AuditFilter("7", "2026-11-01", "2026-11-02").date_from == ""
    f = AuditFilter("custom", "2026-11-01", "")
    assert f.date_from == "2026-11-01" and f.day_range(NOW) is None


def test_groups_are_kept_in_the_order_the_event_lists_them_without_repeats():
    assert AuditFilter(groups=["System", "Client", "Client"]).groups == ("Client", "System")


def test_from_query_reads_every_field_and_trims_text():
    f = AuditFilter.from_query(MultiDict([("preset", "30"), ("actor", " Shareen "), ("group", "Client"), ("group", "system"),
                                         ("client_ref", " c-0007"), ("result", "FAILED"), ("q", "  net   worth "),
                                         ("sort", "asc"), ("page", "3")]), NOW)
    assert (f.preset, f.actor, f.groups, f.client_ref, f.result, f.query, f.sort, f.page) == (
        "30", "Shareen", ("Client", "System"), "c-0007", "failed", "net worth", "asc", 3)
    assert f.problems() == []


def test_from_query_with_nothing_or_blanks_gives_the_defaults():
    assert AuditFilter.from_query({}, NOW).to_query() == {}
    assert AuditFilter.from_query({"preset": "  ", "group": "", "q": " "}, NOW).to_query() == {}


def test_from_query_accepts_a_plain_dict_with_a_list_of_groups():
    assert AuditFilter.from_query({"group": ["Client", "Documents"]}, NOW).groups == ("Client", "Documents")


@pytest.mark.parametrize("value", ["5", "1" * 5000])
def test_a_bad_preset_falls_back_to_7_days_and_says_what_is_allowed(value):
    f = AuditFilter.from_query({"preset": value}, NOW)
    assert f.preset == "7"
    assert f.problems() == ["'preset' must be one of 1, 7, 30, 90, custom; showing the last 7 days."]


def test_a_bad_group_is_ignored_and_the_good_ones_are_kept():
    f = AuditFilter.from_query(MultiDict([("group", "Client"), ("group", "Everything")]), NOW)
    assert f.groups == ("Client",)
    assert f.problems() == ["'group' must be one of Sign-in, Client, Documents, Assessment, System; ignoring that value."]
    assert AuditFilter.from_query({"group": "Everything"}, NOW).all_groups() is True


@pytest.mark.parametrize("name, value, text", [
    ("result", "maybe", "'result' must be all, ok or failed; showing all."),
    ("sort", "up", "'sort' must be desc (newest first) or asc (oldest first); showing newest first."),
    ("page", "0", "'page' must be a whole number, 1 or more; showing page 1."),
    ("page", "٢", "'page' must be a whole number, 1 or more; showing page 1."),
    ("q", "x" * 81, "'q' must be printable text of at most 80 characters; not searching."),
    ("actor", "x" * 81, "'actor' must be printable text of at most 80 characters; showing every officer."),
    ("client_ref", "x" * 41, "'client_ref' must be printable text of at most 40 characters; showing every client."),
])
def test_each_bad_value_falls_back_with_its_own_plain_line(name, value, text):
    f = AuditFilter.from_query({name: value}, NOW)
    assert f.problems() == [text] and f.to_query() == {}


def test_custom_dates_are_read_and_a_good_range_has_no_problem():
    f = AuditFilter.from_query({"preset": "custom", "from": "2026-11-10", "to": "2026-11-12"}, NOW)
    assert (f.preset, f.date_from, f.date_to, f.problems()) == ("custom", "2026-11-10", "2026-11-12", [])
    assert [d.isoformat() for d in f.day_range(NOW)] == ["2026-11-10", "2026-11-12"]


@pytest.mark.parametrize("args, problem", [
    ({"preset": "custom", "from": "2026-11-10"}, AuditFilter.PROBLEM_BOTH_DATES),
    ({"preset": "custom", "to": "2026-11-10"}, AuditFilter.PROBLEM_BOTH_DATES),
    ({"preset": "custom", "from": "2026-11-12", "to": "2026-11-10"}, AuditFilter.PROBLEM_DATE_ORDER),
    ({"preset": "custom", "from": "2026-11-10", "to": "2026-11-17"}, AuditFilter.PROBLEM_FUTURE),
    ({"preset": "custom", "from": "10 Nov", "to": "2026-11-10"}, AuditFilter.PROBLEM_DATE_FORMAT),
    ({"preset": "custom", "from": "2026-02-30", "to": "2026-03-01"}, AuditFilter.PROBLEM_DATE_FORMAT),
])
def test_a_bad_custom_range_says_why_and_shows_all_dates_for_now(args, problem):
    f = AuditFilter.from_query(args, NOW)
    assert f.problems() == [problem] and f.preset == "custom" and f.day_range(NOW) is None
    assert f.matches(_event("2020-01-01T00:00:00Z"), NOW)           # no date filter is applied


def test_the_mockups_two_date_messages_are_exact():
    # Custom just picked, no dates yet: all dates, and no warning (the user did nothing wrong)
    picked = AuditFilter.from_query({"preset": "custom"}, NOW)
    assert picked.problems() == [] and picked.range_text(NOW) == "All dates"
    assert AuditFilter.PROBLEM_BOTH_DATES == "Pick both a start and an end date. Showing all dates for now."
    assert AuditFilter.PROBLEM_DATE_ORDER == "The start date must be on or before the end date. Showing all dates for now."


def test_dates_given_with_a_preset_that_is_not_custom_are_ignored_without_a_problem():
    f = AuditFilter.from_query({"preset": "30", "from": "garbage", "to": "2026-11-10"}, NOW)
    assert f.problems() == [] and f.date_from == "" and f.to_query() == {"preset": "30"}


def test_the_date_today_in_singapore_is_not_in_the_future_even_when_it_is_tomorrow_in_utc():
    late = datetime(2026, 11, 16, 17, 0, 0, tzinfo=timezone.utc)      # 01:00 on 17 Nov in Singapore
    f = AuditFilter.from_query({"preset": "custom", "from": "2026-11-17", "to": "2026-11-17"}, late)
    assert f.problems() == []


def test_problems_returns_a_copy():
    f = AuditFilter.from_query({"page": "x"}, NOW)
    f.problems().append("more")
    assert len(f.problems()) == 1


def test_the_preset_days_are_singapore_days_counted_back_from_today():
    # NOW is 20:00 on 16 Nov in Singapore.
    assert [d.isoformat() for d in AuditFilter("1").day_range(NOW)] == ["2026-11-16", "2026-11-16"]
    assert [d.isoformat() for d in AuditFilter("7").day_range(NOW)] == ["2026-11-10", "2026-11-16"]
    assert [d.isoformat() for d in AuditFilter("90").day_range(NOW)] == ["2026-08-19", "2026-11-16"]


def test_an_event_is_on_the_singapore_day_not_the_utc_day():
    just_after_midnight_in_singapore = "2026-11-15T16:30:00Z"            # 00:30 on 16 Nov in Singapore
    assert AuditFilter("1").matches(_event(just_after_midnight_in_singapore), NOW)
    assert not AuditFilter("1").matches(_event("2026-11-15T15:59:59Z"), NOW)     # 23:59:59 on 15 Nov in Singapore


def test_matches_uses_the_days_up_to_the_given_now():
    f = AuditFilter("7")
    assert f.matches(_event("2026-11-10T00:00:00Z"), NOW)
    assert not f.matches(_event("2026-11-09T15:59:00Z"), NOW)
    assert not f.matches(_event("2026-11-10T00:00:00Z"), NOW + timedelta(days=3))


def test_matches_a_custom_range_by_singapore_days_inclusive():
    f = AuditFilter("custom", "2026-11-10", "2026-11-12")
    assert f.matches(_event("2026-11-09T16:00:00Z"), NOW) and f.matches(_event("2026-11-12T15:59:59Z"), NOW)
    assert not f.matches(_event("2026-11-12T16:00:00Z"), NOW) and not f.matches(_event("2026-11-09T15:59:59Z"), NOW)


def test_matches_refuses_a_now_with_no_timezone():
    with pytest.raises(ValueError, match="timezone"):
        AuditFilter().matches(_event(), datetime(2026, 11, 16))


def test_matches_accepts_any_timezone():
    singapore = datetime(2026, 11, 16, 20, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    assert AuditFilter("1").matches(_event(), singapore)


def test_matches_group_result_actor_and_client_ignoring_case():
    event = _event(actor="Shareen", ref="C-0007", result="failed")
    assert AuditFilter(groups=["Client"]).matches(event, NOW) and not AuditFilter(groups=["System"]).matches(event, NOW)
    assert AuditFilter(result="failed").matches(event, NOW) and not AuditFilter(result="ok").matches(event, NOW)
    assert AuditFilter(actor="SHAREEN").matches(event, NOW) and not AuditFilter(actor="Adrian").matches(event, NOW)
    assert AuditFilter(client_ref="c-0007").matches(event, NOW) and not AuditFilter(client_ref="C-0008").matches(event, NOW)


def test_matches_needs_every_filter_to_pass():
    event = _event()
    assert AuditFilter("7", actor="Shareen", groups=["Client"], result="ok", client_ref="C-0007").matches(event, NOW)
    assert not AuditFilter("7", actor="Shareen", groups=["Client"], result="failed").matches(event, NOW)


def test_the_search_looks_in_actor_client_label_summary_file_and_changed_field_names_ignoring_case():
    edit = _event(details={"changes": [{"field": "claims.declared_net_worth", "before": 1, "after": 2}]})
    upload = _event(action="document_uploaded", details={"file_id": "data/documents/Bank_Statement.pdf"})
    for text, event, expected in [
        ("shar", edit, True), ("c-0007", edit, True), ("client edited", edit, True), ("edited client", edit, True),
        ("NET_WORTH", edit, True), ("declared", edit, True), ("adrian", edit, False),
        ("bank_statement", upload, True), ("uploaded", upload, True), ("net_worth", upload, False)]:
        assert AuditFilter(query=text).matches(event, NOW) is expected, text


def test_the_search_ignores_extra_spaces_and_a_malformed_changes_list():
    odd = _event(details={"changes": ["text", {"field": 5}, {"field": "name"}]})
    assert AuditFilter(query="  name ").matches(odd, NOW) and AuditFilter(query="zzz").matches(odd, NOW) is False


def test_page_count_is_at_least_one():
    f = AuditFilter()
    assert [f.page_count(n) for n in (-3, 0, 1, 25, 26, 51)] == [1, 1, 1, 1, 2, 3]


def test_page_of_slices_twenty_five_at_a_time_and_clamps_a_page_past_the_end():
    events = [_event(at=f"2026-11-16T10:{n // 60:02d}:{n % 60:02d}Z") for n in range(30)]
    assert len(AuditFilter(page=1).page_of(events)) == 25 and AuditFilter(page=2).page_of(events) == events[25:]
    assert AuditFilter(page=9).page_of(events) == events[25:] and AuditFilter(page=9).page_for(30) == 2
    assert AuditFilter().page_of([]) == []


def test_to_query_holds_only_values_that_are_not_the_default():
    f = AuditFilter("custom", "2026-11-10", "2026-11-12", ["Client", "System"], "failed", "Shareen", "C-0007",
                    "net worth", "asc", 2)
    assert f.to_query() == {"preset": "custom", "from": "2026-11-10", "to": "2026-11-12", "group": ["Client", "System"],
                            "actor": "Shareen", "client_ref": "C-0007", "q": "net worth", "result": "failed",
                            "sort": "asc", "page": "2"}


def test_a_query_survives_a_round_trip_through_from_query():
    f = AuditFilter("30", "", "", ["Documents"], "ok", "Adrian", "C-1", "file", "asc", 4)
    again = AuditFilter.from_query(MultiDict([(k, x) for k, v in f.to_query().items()
                                              for x in (v if isinstance(v, list) else [v])]), NOW)
    assert again.to_query() == f.to_query() and again.problems() == []


def test_chips_name_each_active_filter_in_plain_words_and_say_which_address_value_removes_it():
    f = AuditFilter("custom", "2026-11-10", "2026-11-12", ["Client", "System"], "failed", "Shareen", "c-0007", "net")
    assert f.chips() == [("actor", "Officer: Shareen"), ("group", "Actions: Client, System"),
                         ("client_ref", "Client: C-0007"), ("result", "Failed only"), ("q", "Search: “net”")]
    assert AuditFilter(result="ok").chips() == [("result", "OK only")]


def test_the_range_and_headline_texts():
    assert AuditFilter("1").period_text(NOW) == "Today" and AuditFilter("1").range_text(NOW) == "16 November 2026"
    assert AuditFilter("7").period_text(NOW) == "In the last 7 days"
    assert AuditFilter("7").range_text(NOW) == "10 November 2026 – 16 November 2026"
    custom = AuditFilter("custom", "2026-11-10", "2026-11-12")
    assert custom.period_text(NOW) == "10 Nov to 12 Nov" and custom.range_text(NOW) == "10 November 2026 – 12 November 2026"
    unset = AuditFilter("custom")
    assert unset.period_text(NOW) == "On all dates" and unset.range_text(NOW) == "All dates"


def test_parse_day_is_strict():
    assert AuditFilter.parse_day("2026-11-15").isoformat() == "2026-11-15"
    for bad in ("2026-1-5", "15-11-2026", "2026-02-30", "", None, "２０２６-11-15"):
        assert AuditFilter.parse_day(bad) is None
