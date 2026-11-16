"""FlagTicket: replaying flag_updated lines, and checking an update."""

import pytest

from app.model.audit_event import AuditEvent
from app.model.flag import Flag
from app.model.flag_ticket import FlagTicket

FLAG = Flag(flag_id="F-SHO-SOW-1-484", kind="shop", severity="high", client_ref="SOW-1",
            headline="Verdict worsened", sequences=(1, 2, 3), raised_at="2026-11-13T06:05:00Z")
NOTE = "Checked the documents."


def _update(to, actor="Admin A", frm="open", note=NOTE, waiting_on="", outcome="", flag_id=FLAG.flag_id,
            result="ok", sequence=10, at="2026-11-14T01:00:00Z"):
    return AuditEvent(sequence=sequence, at=at, actor=actor, action="flag_updated", result=result,
                      details={"flag_id": flag_id, "from": frm, "to": to, "waiting_on": waiting_on,
                               "outcome": outcome, "note": note})


def test_a_flag_with_no_updates_is_open_with_one_history_line_from_the_system():
    ticket = FlagTicket(FLAG, [])
    assert (ticket.status, ticket.status_name, ticket.assignee, ticket.waiting_on, ticket.outcome) == \
        ("open", "Open", "", "", "")
    assert ticket.flag is FLAG
    assert ticket.history == [{"by": "System", "at": "2026-11-13T06:05:00Z", "from": "", "to": "open",
                               "note": "Opened automatically by the rule."}]


def test_updates_move_the_status_and_the_first_one_out_of_open_sets_the_assignee():
    events = [_update("review", "Admin A", sequence=10), _update("followup", "Admin B", "review",
                                                                 waiting_on="IT support", sequence=11)]
    ticket = FlagTicket(FLAG, events)
    assert ticket.status == "followup" and ticket.assignee == "Admin A" and ticket.waiting_on == "IT support"
    assert [h["to"] for h in ticket.history] == ["open", "review", "followup"]
    last = ticket.history[-1]
    assert (last["by"], last["from"], last["note"], last["waiting_on"], last["sequence"]) == \
        ("Admin B", "review", NOTE, "IT support", 11)


def test_resolving_keeps_the_outcome_and_reopening_clears_it_but_keeps_the_assignee():
    events = [_update("review", sequence=10), _update("resolved", frm="review", outcome="fixed", sequence=11)]
    ticket = FlagTicket(FLAG, events)
    assert ticket.status == "resolved" and ticket.outcome == "fixed"
    reopened = FlagTicket(FLAG, events + [_update("open", "Admin B", "resolved", sequence=12)])
    assert reopened.status == "open" and reopened.outcome == "" and reopened.assignee == "Admin A"


def test_a_note_in_the_same_status_keeps_waiting_on():
    events = [_update("followup", waiting_on="Compliance", sequence=10),
              _update("followup", frm="followup", note="Chased them again.", sequence=11)]
    ticket = FlagTicket(FLAG, events)
    assert ticket.status == "followup" and ticket.waiting_on == "Compliance" and len(ticket.history) == 3


def test_leaving_following_up_clears_waiting_on():
    events = [_update("followup", waiting_on="Compliance", sequence=10), _update("review", frm="followup", sequence=11)]
    assert FlagTicket(FLAG, events).waiting_on == ""


def test_lines_for_other_flags_other_actions_and_failed_saves_are_ignored():
    other = _update("resolved", flag_id="F-SHO-SOW-1-999", outcome="legit")
    failed = _update("review", result="failed")
    not_an_update = AuditEvent(sequence=5, action="audit_verified")
    ticket = FlagTicket(FLAG, [other, failed, not_an_update])
    assert ticket.status == "open" and len(ticket.history) == 1 and ticket.skipped_count == 0


def test_a_line_with_an_unknown_status_is_skipped_and_counted():
    bad = _update("closed")
    ticket = FlagTicket(FLAG, [bad, _update("review", sequence=11)])
    assert ticket.status == "review" and ticket.skipped_count == 1


def test_the_history_is_a_copy():
    ticket = FlagTicket(FLAG, [])
    ticket.history[0]["note"] = "changed"
    assert ticket.history[0]["note"] == "Opened automatically by the rule."


def test_bad_inputs_are_refused():
    with pytest.raises(ValueError, match="needs a flag"):
        FlagTicket("F-1", [])
    with pytest.raises(ValueError, match="list of audit events"):
        FlagTicket(FLAG, ["x"])
    with pytest.raises(ValueError, match="list of audit events"):
        FlagTicket(FLAG, "events")


def test_the_constants_use_the_mockup_wording():
    assert FlagTicket.STATUSES == {"open": "Open", "review": "In review", "followup": "Following up",
                                   "resolved": "Resolved"}
    assert FlagTicket.OUTCOMES["legit"] == "No issue: the activity was legitimate"
    assert FlagTicket.WAITING_ON == ("Owner officer", "Officer who made the change", "IT support", "Compliance")
    assert (FlagTicket.NOTE_MIN, FlagTicket.NOTE_MAX) == (5, 500)


@pytest.mark.parametrize("note,expected", [
    ("abcd", "Please write a note of at least 5 characters saying what you found or did."),
    ("  abcd  ", "Please write a note of at least 5 characters saying what you found or did."),
    ("", "Please write a note of at least 5 characters saying what you found or did."),
    (None, "Please write a note of at least 5 characters saying what you found or did."),
    ("x" * 501, "Please keep the note to 500 characters or fewer."),
])
def test_the_note_must_be_5_to_500_characters_after_trimming(note, expected):
    assert FlagTicket(FLAG, []).check_update("review", note) == [expected]


def test_a_note_of_exactly_the_limits_is_fine():
    ticket = FlagTicket(FLAG, [])
    assert ticket.check_update("review", "abcde") == [] and ticket.check_update("review", " " + "x" * 500 + " ") == []


def test_an_unknown_status_is_refused():
    assert FlagTicket(FLAG, []).check_update("closed", NOTE) == ["Choose a status: Open, In review, Following up or Resolved."]


def test_following_up_needs_a_known_waiting_on_only_when_moving_there():
    ticket = FlagTicket(FLAG, [])
    assert ticket.check_update("followup", NOTE) == ["Choose who you are waiting on."]
    assert ticket.check_update("followup", NOTE, "The cleaner") == ["Choose who you are waiting on."]
    assert ticket.check_update("followup", NOTE, "IT support") == []
    already = FlagTicket(FLAG, [_update("followup", waiting_on="IT support")])
    assert already.check_update("followup", NOTE) == []


def test_resolving_needs_a_known_outcome_only_when_moving_there():
    ticket = FlagTicket(FLAG, [])
    assert ticket.check_update("resolved", NOTE) == ["Choose an outcome before resolving."]
    assert ticket.check_update("resolved", NOTE, outcome="fine") == ["Choose an outcome before resolving."]
    assert ticket.check_update("resolved", NOTE, outcome="escalated") == []
    done = FlagTicket(FLAG, [_update("resolved", outcome="fixed")])
    assert done.check_update("resolved", NOTE) == []
    assert done.check_update("open", NOTE) == []                  # a reopen needs nothing extra


def test_every_problem_is_reported_at_once():
    assert len(FlagTicket(FLAG, []).check_update("resolved", "no")) == 2


def test_update_details_gives_the_line_to_write():
    ticket = FlagTicket(FLAG, [])
    assert ticket.update_details("Admin A", "followup", "  Asked IT.  ", "IT support", "legit") == {
        "flag_id": FLAG.flag_id, "from": "open", "to": "followup", "waiting_on": "IT support", "outcome": "",
        "note": "Asked IT."}
    assert ticket.update_details("Admin A", "resolved", NOTE, "IT support", "fixed")["waiting_on"] == ""
    assert ticket.update_details("Admin A", "resolved", NOTE, outcome="fixed")["outcome"] == "fixed"


def test_update_details_for_a_note_keeps_the_status_and_drops_the_extras():
    ticket = FlagTicket(FLAG, [_update("followup", waiting_on="Compliance")])
    details = ticket.update_details("Admin A", "followup", "Chased.", "Compliance")
    assert details["from"] == "followup" and details["to"] == "followup" and details["waiting_on"] == ""


def test_update_details_refuses_a_bad_update_with_the_problems_and_an_empty_actor():
    ticket = FlagTicket(FLAG, [])
    with pytest.raises(ValueError, match="at least 5 characters.*Choose who you are waiting on"):
        ticket.update_details("Admin A", "followup", "no")
    with pytest.raises(ValueError, match="name of the person"):
        ticket.update_details(" ", "review", NOTE)


def test_the_details_make_a_line_that_replays_to_the_same_state():
    ticket = FlagTicket(FLAG, [])
    details = ticket.update_details("Admin A", "followup", NOTE, "Compliance")
    event = AuditEvent(sequence=10, actor="Admin A", action="flag_updated", details=details)
    assert FlagTicket(FLAG, [event]).waiting_on == "Compliance"
