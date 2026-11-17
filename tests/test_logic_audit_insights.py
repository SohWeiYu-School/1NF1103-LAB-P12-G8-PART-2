"""AuditInsights: each of the six rules, with a case just below its limit, and stable ids."""

from datetime import datetime, timedelta, timezone

import pytest

from app.logic.audit_insights import AuditInsights
from app.model.audit_event import AuditEvent
from app.model.audit_policy import AuditPolicy

SGT = timezone(timedelta(hours=8))
BASE = datetime(2026, 11, 2, 10, 0, tzinfo=SGT)           # a Monday, 10:00 in Singapore
INCOME = {"field": "claims.expected_aum", "before": 100000, "after": 250000}
EMPLOYER = {"field": "career.employer_name", "before": "A", "after": "B"}


class Log:
    """Builds a sequenced list of events; at() gives a Singapore time as the log's UTC text."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def add(self, action, when, actor="Owner", client="SOW-1", result="ok", **details) -> AuditEvent:
        text = when.astimezone(timezone.utc).strftime(AuditEvent.TIME_FORMAT)
        event = AuditEvent(sequence=len(self.events) + 1, at=text, actor=actor, action=action, client_ref=client,
                           result=result, details=details)
        self.events.append(event)
        return event

    def create(self, when=BASE, actor="Owner", client="SOW-1"):
        return self.add("client_created", when, actor, client)

    def edit(self, when, changes, actor="Owner", client="SOW-1", result="ok"):
        return self.add("client_edited", when, actor, client, result, changes=changes)

    def assess(self, when, outcome, actor="Owner", client="SOW-1", result="ok"):
        return self.add("assessment_run", when, actor, client, result, outcome=outcome, assessment_id=f"A-{len(self.events)}")


def _flags(log: Log, **options):
    return AuditInsights(log.events, options.pop("policy", None), **options).flags()


def _of(flags, kind):
    return [flag for flag in flags if flag.kind == kind]


# ---------- failure_kind ----------

@pytest.mark.parametrize("action,result,expected", [
    ("assessment_failed", "ok", "AI step not run"), ("assessment_failed", "failed", "AI step not run"),
    ("data_unavailable", "ok", "Read failed"), ("cloud_sync", "failed", "Sync failed"),
    ("client_created", "failed", "Save failed"), ("client_edited", "failed", "Save failed"),
    ("assessment_run", "failed", "Save failed"),
    ("cloud_sync", "ok", ""), ("client_edited", "ok", ""), ("signed_in", "failed", ""), ("document_uploaded", "failed", ""),
])
def test_failure_kind_names_the_kind_of_failure_or_nothing(action, result, expected):
    assert AuditInsights.failure_kind(AuditEvent(action=action, result=result)) == expected


# ---------- construction ----------

def test_no_events_means_no_flags():
    assert AuditInsights().flags() == []
    assert AuditInsights([], AuditPolicy()).flags() == []


@pytest.mark.parametrize("kwargs", [{"events": "x"}, {"events": [1]}, {"policy": {}}, {"broken_at": -1},
                                    {"broken_at": True}, {"now": datetime(2026, 1, 1)}, {"now": "today"}])
def test_the_wrong_kind_of_input_is_refused(kwargs):
    with pytest.raises(ValueError):
        AuditInsights(**kwargs)


def test_events_given_out_of_order_are_put_in_sequence_order():
    log = Log()
    log.create()
    log.edit(BASE + timedelta(hours=1), [INCOME], actor="Other")
    assert len(AuditInsights(list(reversed(log.events))).flags()) == 1


# ---------- other: edited by non-owner ----------

def test_an_edit_by_someone_who_did_not_create_the_client_is_medium_and_names_the_owner():
    log = Log()
    log.create(actor="Owner")
    edit = log.edit(BASE + timedelta(hours=1), [EMPLOYER], actor="Other")
    (flag,) = _flags(log)
    assert (flag.kind, flag.severity, flag.owner, flag.sequences) == ("other", "medium", "Owner", (edit.sequence,))
    assert flag.headline == "Edited by Other, not the client's owner (Owner)"
    assert flag.flag_id == "F-OTH-SOW-1-2" and flag.client_ref == "SOW-1" and flag.changes == (EMPLOYER,)
    assert flag.raised_at == edit.at


def test_an_edit_of_a_watched_field_by_a_non_owner_is_high_and_keeps_every_change():
    log = Log()
    log.create()
    log.edit(BASE + timedelta(hours=1), [EMPLOYER, INCOME], actor="Other")
    (flag,) = _flags(log)
    assert flag.severity == "high" and flag.changes == (EMPLOYER, INCOME)


def test_edits_by_the_owner_raise_nothing_and_neither_do_edits_when_the_owner_is_not_in_the_log():
    log = Log()
    log.create(actor="Owner")
    log.edit(BASE + timedelta(hours=1), [INCOME], actor="Owner")
    assert _flags(log) == []
    unknown = Log()
    unknown.edit(BASE, [INCOME], actor="Other")
    assert _flags(unknown) == []


def test_a_failed_client_creation_does_not_make_someone_the_owner_and_a_failed_edit_raises_nothing():
    log = Log()
    log.add("client_created", BASE, "Trainee", result="failed")
    log.create(BASE + timedelta(minutes=5), actor="Owner")
    log.edit(BASE + timedelta(hours=1), [INCOME], actor="Trainee", result="failed")
    log.edit(BASE + timedelta(hours=2), [EMPLOYER], actor="Owner")
    assert _flags(log) == []


# ---------- shop: verdict jump after edit ----------

def _shop_log(before="RISKY", after="PASSED", edit_gap=timedelta(minutes=30), span=timedelta(days=2),
              changes=None) -> Log:
    log = Log()
    log.create()
    log.assess(BASE, before)
    log.edit(BASE + edit_gap, [INCOME] if changes is None else changes)
    log.assess(BASE + span, after)
    return log


def test_a_watched_edit_then_a_two_level_jump_is_a_high_flag_with_the_three_entries():
    log = _shop_log(edit_gap=timedelta(hours=1), span=timedelta(hours=1, minutes=30))
    (flag,) = _flags(log)
    assert (flag.kind, flag.severity, flag.sequences, flag.flag_id) == ("shop", "high", (2, 3, 4), "F-SHO-SOW-1-4")
    assert flag.headline == "Verdict improved by 2 levels after declared figures were edited"
    assert flag.meaning == ("The result went from Risky to Passed 30 minutes after expected aum went "
                            "100,000 → 250,000. Raising declared figures until a case passes is the pattern "
                            "regulators look for.")
    assert flag.changes == (INCOME,) and flag.owner == "Owner" and flag.raised_at == log.events[3].at


def test_a_worsening_verdict_says_worsened_and_a_long_gap_is_counted_in_hours():
    log = _shop_log(before="PASSED", after="SERIOUS_RISK", edit_gap=timedelta(minutes=10), span=timedelta(hours=3, minutes=10))
    (flag,) = _flags(log)
    assert flag.headline == "Verdict worsened by 3 levels after declared figures were edited"
    assert "Passed to Serious risk 3 hours after" in flag.meaning


def test_a_jump_of_one_level_is_just_below_the_limit_and_raises_nothing():
    assert _of(_flags(_shop_log(before="RISKY", after="MANUAL_REVIEW")), "shop") == []


def test_the_jump_limit_follows_the_policy():
    log = _shop_log(before="RISKY", after="MANUAL_REVIEW")
    assert len(_of(_flags(log, policy=AuditPolicy(jump_levels=1)), "shop")) == 1


def test_an_edit_that_changes_no_watched_field_does_not_count_as_a_shop():
    assert _of(_flags(_shop_log(changes=[EMPLOYER])), "shop") == []


def test_a_jump_with_no_edit_between_the_assessments_is_not_a_shop():
    log = Log()
    log.create()
    log.assess(BASE, "RISKY")
    log.assess(BASE + timedelta(days=1), "PASSED")
    assert _of(_flags(log), "shop") == []


def test_an_edit_before_the_first_assessment_is_not_a_shop():
    log = Log()
    log.create()
    log.edit(BASE, [INCOME])
    log.assess(BASE + timedelta(hours=1), "RISKY")
    log.assess(BASE + timedelta(hours=2), "PASSED")
    assert _of(_flags(log), "shop") == []


def test_the_window_is_counted_from_the_assessment_before_the_edit_up_to_the_limit():
    just_inside = _shop_log(span=timedelta(days=30))
    just_outside = _shop_log(span=timedelta(days=30, minutes=1))
    assert len(_of(_flags(just_inside), "shop")) == 1
    assert _of(_flags(just_outside), "shop") == []
    assert len(_of(_flags(just_outside, policy=AuditPolicy(window_days=31)), "shop")) == 1


def test_a_failed_edit_or_a_failed_assessment_is_ignored_by_the_shop_rule():
    log = Log()
    log.create()
    log.assess(BASE, "RISKY")
    log.edit(BASE + timedelta(minutes=30), [INCOME], result="failed")
    log.assess(BASE + timedelta(days=1), "PASSED")
    assert _of(_flags(log), "shop") == []
    log2 = _shop_log()
    log2.assess(BASE + timedelta(days=3), "SERIOUS_RISK", result="failed")
    assert len(_of(_flags(log2), "shop")) == 1


def test_a_second_assessment_resets_the_pending_edit():
    log = Log()
    log.create()
    log.assess(BASE, "PASSED")
    log.edit(BASE + timedelta(minutes=10), [INCOME])
    log.assess(BASE + timedelta(minutes=20), "PASSED")            # no jump: the edit is used up
    log.assess(BASE + timedelta(minutes=30), "SERIOUS_RISK")      # a jump, but no edit before it
    assert _of(_flags(log), "shop") == []


def test_an_assessment_with_an_unknown_outcome_is_not_compared():
    log = _shop_log(after="WEIRD")
    assert _of(_flags(log), "shop") == []


# ---------- repeat: repeated assessments ----------

def _runs(count, step=timedelta(days=1), outcomes=("RISKY",)) -> Log:
    log = Log()
    log.create()
    for number in range(count):
        log.assess(BASE + step * number, outcomes[number % len(outcomes)])
    return log


def test_four_assessments_in_the_window_raise_one_medium_flag_with_the_first_run_in_the_id():
    log = _runs(4)
    (flag,) = _of(_flags(log), "repeat")
    assert (flag.severity, flag.sequences, flag.flag_id) == ("medium", (2, 3, 4, 5), "F-REP-SOW-1-2")
    assert flag.headline == "Assessed 4 times in 3 days"
    assert flag.meaning == ("Results: Risky, Risky, Risky, Risky. Nothing changed between runs, so re-running is "
                            "not moving the case forward. Repeated runs can also be a way of hoping for a "
                            "better answer.")


def test_a_change_of_result_between_runs_is_said_so():
    (flag,) = _of(_flags(_runs(4, outcomes=("RISKY", "PASSED"))), "repeat")
    assert "The result changed between runs." in flag.meaning


def test_exactly_three_assessments_is_just_below_the_limit():
    assert _of(_flags(_runs(3)), "repeat") == []


def test_the_limit_follows_the_policy():
    assert len(_of(_flags(_runs(3), policy=AuditPolicy(repeat_assessments=2)), "repeat")) == 1


def test_four_assessments_spread_wider_than_the_window_raise_nothing():
    assert _of(_flags(_runs(4, step=timedelta(days=11))), "repeat") == []          # 33 days end to end
    assert len(_of(_flags(_runs(4, step=timedelta(days=10))), "repeat")) == 1       # exactly 30 days


def test_one_burst_gives_one_flag_and_a_later_burst_gets_its_own():
    log = _runs(5)
    for number in range(4):
        log.assess(BASE + timedelta(days=100 + number), "RISKY")
    flags = _of(_flags(log), "repeat")
    assert len(flags) == 2 and flags[0].flag_id != flags[1].flag_id
    assert sorted(len(flag.sequences) for flag in flags) == [4, 5]


def test_a_day_is_not_plural_when_it_is_one_and_a_burst_within_a_day_says_1_day():
    log = Log()
    log.create()
    for number in range(4):
        log.assess(BASE + timedelta(minutes=number), "RISKY")
    (flag,) = _of(_flags(log), "repeat")
    assert flag.headline == "Assessed 4 times in 1 day"


def test_runs_of_different_clients_are_counted_apart_and_failed_runs_do_not_count():
    log = Log()
    log.create()
    log.create(client="SOW-2")
    for number in range(2):
        log.assess(BASE + timedelta(days=number), "RISKY")
        log.assess(BASE + timedelta(days=number), "RISKY", client="SOW-2")
    log.assess(BASE + timedelta(days=3), "RISKY", result="failed")
    assert _of(_flags(log), "repeat") == []


def test_a_growing_burst_keeps_the_same_flag_id():
    ids = {_of(_flags(_runs(count)), "repeat")[0].flag_id for count in (4, 5, 8)}
    assert ids == {"F-REP-SOW-1-2"}


def test_runs_every_10_days_make_one_flag_per_burst_not_one_per_run():
    flags = _of(_flags(_runs(9, step=timedelta(days=10))), "repeat")
    # bursts start at day 0, 40 and 80: runs 0-3 (30 days), 4-7, and run 8 alone
    assert [(flag.flag_id, len(flag.sequences)) for flag in flags] == [("F-REP-SOW-1-6", 4), ("F-REP-SOW-1-2", 4)]


# ---------- hours: after-hours activity ----------

def _at(hour, minute=0):
    return datetime(2026, 11, 3, hour, minute, tzinfo=SGT)


def test_an_edit_before_the_working_day_is_a_low_flag_in_singapore_time():
    log = Log()
    log.create(_at(10))
    log.edit(_at(7, 59), [EMPLOYER])
    (flag,) = _of(_flags(log), "hours")
    assert (flag.severity, flag.sequences, flag.flag_id, flag.owner) == ("low", (2,), "F-HOU-SOW-1-2", "Owner")
    assert flag.headline == "Edited client at 07:59, outside working hours"
    assert flag.meaning == ("Owner worked on SOW-1 at 07:59 on 3 Nov. Working hours are 08:00 to 20:00. "
                            "Out-of-hours changes are less likely to be seen by a colleague.")


def test_an_assessment_at_the_end_of_the_day_is_flagged_and_the_working_hours_edges_are_inside():
    log = Log()
    log.create(_at(10))
    log.assess(_at(8, 0), "PASSED")
    log.assess(_at(19, 59), "PASSED")
    assert _of(_flags(log), "hours") == []
    log.assess(_at(20, 0), "PASSED")
    (flag,) = _of(_flags(log), "hours")
    assert flag.headline == "Assessed at 20:00, outside working hours"


def test_the_day_is_judged_in_singapore_time_not_utc():
    log = Log()
    log.create(_at(10))
    log.edit(datetime(2026, 11, 3, 0, 30, tzinfo=timezone.utc), [EMPLOYER])       # 08:30 in Singapore
    assert _of(_flags(log), "hours") == []
    log.edit(datetime(2026, 11, 3, 12, 30, tzinfo=timezone.utc), [EMPLOYER])      # 20:30 in Singapore
    assert len(_of(_flags(log), "hours")) == 1


def test_only_edits_and_assessments_count_for_hours_and_a_failed_one_is_ignored():
    log = Log()
    log.add("client_created", _at(3))
    log.add("document_uploaded", _at(3))
    log.edit(_at(3), [EMPLOYER], result="failed")
    assert _of(_flags(log), "hours") == []


def test_the_working_hours_follow_the_policy():
    log = Log()
    log.create(_at(10))
    log.edit(_at(21), [EMPLOYER])
    assert _of(_flags(log, policy=AuditPolicy(work_end="22:00")), "hours") == []


def test_an_event_with_no_client_can_still_be_after_hours():
    log = Log()
    log.add("client_edited", _at(2), client="", changes=[])
    (flag,) = _of(_flags(log), "hours")
    assert flag.client_ref == "" and flag.flag_id == "F-HOU-1" and "worked on a client" in flag.meaning


# ---------- spike: failure spike ----------

def _failures(log: Log, day_offset: int, count: int, action="assessment_failed", base=BASE) -> list[AuditEvent]:
    day = base + timedelta(days=day_offset)
    return [log.add(action, day.replace(hour=10, minute=number), client="SOW-9") for number in range(count)]


def test_three_failures_on_a_quiet_day_raise_a_medium_spike_flag():
    log = Log()
    failures = _failures(log, 0, 3)
    (flag,) = _of(_flags(log), "spike")
    assert (flag.severity, flag.client_ref, flag.day, flag.usual) == ("medium", "", "2026-11-02", 0)
    assert flag.sequences == (1, 2, 3) and flag.flag_id == "F-SPI-1" and flag.raised_at == failures[-1].at
    assert flag.headline == "3 failures on 2 Nov (usually 0)"
    assert flag.meaning == ("3 assessments stopped because the AI service did not answer. Cases assessed that "
                            "day may be missing steps.")


def test_two_failures_is_just_below_the_minimum_and_raises_nothing():
    log = Log()
    _failures(log, 0, 2)
    assert _of(_flags(log), "spike") == []
    assert len(_of(_flags(log, policy=AuditPolicy(spike_min=2)), "spike")) == 1


def test_just_below_the_multiplier_raises_nothing_on_that_day():
    log = Log()
    for offset in range(-14, 0):
        _failures(log, offset, 2)                  # usual 2 a day; none of those days is 3x its own baseline
    _failures(log, 0, 5)                           # 5 < 3 x 2
    assert all(flag.day != "2026-11-02" for flag in _of(_flags(log), "spike"))
    _failures(log, 0, 1)                           # now 6 = 3 x 2
    (flag,) = [flag for flag in _of(_flags(log), "spike") if flag.day == "2026-11-02"]
    assert flag.usual == 2 and flag.headline == "6 failures on 2 Nov (usually 2)"


def test_the_usual_number_is_the_median_so_one_bad_day_before_does_not_hide_a_spike():
    log = Log()
    _failures(log, -3, 20)                          # one terrible day inside the 14 days before
    _failures(log, 0, 3)
    flags = {flag.day: flag for flag in _of(_flags(log), "spike")}
    assert "2026-11-02" in flags and flags["2026-11-02"].usual == 0


def test_an_even_number_of_days_averages_the_two_middle_values():
    log = Log()
    _failures(log, -1, 1)
    _failures(log, 0, 3)
    flags = {flag.day: flag for flag in _of(_flags(log), "spike")}
    assert "2026-11-02" in flags and flags["2026-11-02"].usual == 0
    low = AuditPolicy(spike_baseline_days=2)
    log2 = Log()
    _failures(log2, -1, 1)
    _failures(log2, -2, 2)
    _failures(log2, 0, 3)
    day = [flag for flag in _of(_flags(log2, policy=low), "spike") if flag.day == "2026-11-02"]
    assert day == []                                # median of (1, 2) is 1.5; 3 < 4.5


def test_every_kind_of_failure_counts_and_the_meaning_says_what_failed():
    log = Log()
    log.add("assessment_failed", BASE, client="SOW-1")
    log.add("data_unavailable", BASE, client="", what="client records")
    log.add("data_unavailable", BASE, client="")
    log.add("cloud_sync", BASE, client="", result="failed")
    log.add("client_edited", BASE, client="SOW-1", result="failed", changes=[])
    (flag,) = _of(_flags(log), "spike")
    assert flag.headline == "5 failures on 2 Nov (usually 0)"
    assert flag.meaning == ("1 assessment stopped because the AI service did not answer, and the database could "
                            "not be read 2 times, and 1 save failed, and 1 cloud sync failed. Cases assessed "
                            "that day may be missing steps.")


def test_a_spike_with_no_ai_failures_does_not_talk_about_assessments():
    log = Log()
    for _ in range(3):
        log.add("data_unavailable", BASE, client="")
    (flag,) = _of(_flags(log), "spike")
    assert flag.meaning == "The database could not be read 3 times. Work done that day may not have been saved or read."


def test_failures_are_counted_by_singapore_day():
    log = Log()
    for hour in (15, 16, 17):                          # 23:00, 00:00 and 01:00 in Singapore
        log.add("assessment_failed", datetime(2026, 11, 2, hour, 0, tzinfo=timezone.utc), client="")
    assert _of(_flags(log), "spike") == []


def test_the_spike_id_stays_the_same_when_more_failures_arrive_the_same_day():
    log = Log()
    _failures(log, 0, 3)
    first = _of(_flags(log), "spike")[0].flag_id
    log.add("assessment_failed", BASE.replace(hour=15), client="")
    assert _of(_flags(log), "spike")[0].flag_id == first


# ---------- integrity ----------

def test_a_broken_chain_raises_one_high_flag_with_no_client_and_the_broken_entry():
    log = Log()
    log.create()
    log.edit(BASE + timedelta(hours=1), [EMPLOYER])
    (flag,) = _flags(log, broken_at=2)
    assert (flag.kind, flag.severity, flag.client_ref, flag.sequences, flag.broken_at) == ("integrity", "high", "", (), 2)
    assert flag.flag_id == "F-INT-2" and flag.headline == "Audit log changed outside the app at entry #2"
    assert flag.meaning.startswith("Entry #2 no longer matches the fingerprint stored in entry #3.")
    assert flag.raised_at == log.events[1].at


def test_an_intact_chain_raises_no_integrity_flag_and_a_missing_entry_falls_back_to_the_last_event():
    log = Log()
    log.create()
    assert _flags(log, broken_at=0) == []
    (flag,) = _flags(log, broken_at=9)
    assert flag.raised_at == log.events[-1].at
    (empty,) = AuditInsights([], None, 5, BASE).flags()
    assert empty.raised_at == BASE.astimezone(timezone.utc).strftime(AuditEvent.TIME_FORMAT)


def test_the_other_rules_still_run_when_the_chain_is_broken():
    log = Log()
    log.create()
    log.edit(BASE + timedelta(hours=1), [INCOME], actor="Other")
    assert {flag.kind for flag in _flags(log, broken_at=1)} == {"other", "integrity"}


# ---------- ordering and stability ----------

def test_flags_come_back_newest_first():
    log = Log()
    log.create()
    log.edit(BASE + timedelta(hours=1), [EMPLOYER], actor="Other")
    log.edit(BASE + timedelta(hours=3), [EMPLOYER], actor="Other")
    assert [flag.sequences for flag in _flags(log)] == [(3,), (2,)]


def test_the_same_events_give_the_same_flags_in_the_same_order():
    log = _shop_log()
    log.edit(BASE + timedelta(days=3), [INCOME], actor="Other")
    for number in range(4):
        log.assess(BASE + timedelta(days=4 + number), "RISKY")
    first = [flag.flag_id for flag in _flags(log)]
    assert first == [flag.flag_id for flag in _flags(log)] == [flag.flag_id for flag in _flags(log, now=BASE)]
    assert len(first) == len(set(first)) and len(first) >= 3


def test_ids_do_not_change_when_unrelated_events_are_added_later():
    log = _shop_log()
    before = {flag.flag_id for flag in _flags(log)}
    log.add("signed_in", BASE + timedelta(days=5), client="")
    assert before <= {flag.flag_id for flag in _flags(log)}


def test_an_edit_inside_a_watched_dict_counts_and_is_named_under_its_parent():
    log = Log()
    log.create()
    log.assess(BASE, "SERIOUS_RISK")
    log.edit(BASE + timedelta(hours=1), [{"field": "claims.asset_composition.cash", "before": 10, "after": 90},
                                         {"field": "claims.asset_composition.property", "before": 90, "after": 10}])
    log.assess(BASE + timedelta(hours=2), "PASSED")
    (flag,) = _of(_flags(log), "shop")
    assert len(flag.changes) == 2
    assert "asset composition (cash) went 10 → 90" in flag.meaning
    assert "asset composition (property) went 90 → 10" in flag.meaning


def test_an_assessment_that_stopped_while_saving_is_a_save_failure_not_an_ai_failure():
    saving = AuditEvent(action="assessment_failed", result="failed", details={"step": AuditEvent.SAVE_STEP})
    other = AuditEvent(action="assessment_failed", result="failed", details={"step": "Crime scan"})
    assert AuditInsights.failure_kind(saving) == "Save failed"
    assert AuditInsights.failure_kind(other) == "AI step not run"


def test_an_assessment_that_finished_with_a_step_not_run_counts_as_an_ai_failure():
    assert AuditInsights.failure_kind(AuditEvent(action="assessment_run", result="ok",
                                                 details={"not_run": ["Crime scan"]})) == "AI step not run"
    assert AuditInsights.failure_kind(AuditEvent(action="assessment_run", result="ok", details={"not_run": []})) == ""
    assert AuditInsights.failure_kind(AuditEvent(action="assessment_run", result="ok", details={})) == ""


def test_the_spike_meaning_says_each_kind_truthfully():
    log = Log()
    log.add("assessment_failed", BASE, result="failed", step=AuditEvent.SAVE_STEP)
    log.add("assessment_run", BASE + timedelta(minutes=1), outcome="RISKY", not_run=["Crime scan"])
    log.add("assessment_failed", BASE + timedelta(minutes=2), result="failed", step="Crime scan")
    (flag,) = _of(_flags(log), "spike")
    assert flag.meaning == ("1 assessment stopped because the AI service did not answer, and 1 assessment finished "
                            "with a step that did not run, and 1 save failed. Cases assessed that day may be "
                            "missing steps.")
