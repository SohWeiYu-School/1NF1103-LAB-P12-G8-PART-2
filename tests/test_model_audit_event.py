"""AuditEvent: validation, the hash and seal rules, summary lines, group and label for every action."""

import re

import pytest

from app.model.audit_event import AuditEvent
from tests.conftest import TEST_AUDIT_KEY as KEY

AT = "2026-11-15T06:02:11Z"


def _event(**changes) -> AuditEvent:
    fields = {"event_id": "id-1", "at": AT, "actor": "Shareen", "action": "client_edited", "client_ref": "C-0007",
              "details": {"changes": [{"field": "a", "before": 1, "after": 2}]}}
    fields.update(changes)
    return AuditEvent(**fields)


def test_an_event_with_all_defaults_builds_and_is_unset():
    event = AuditEvent()
    assert event.action == "" and event.actor == "terminal" and event.result == "ok"
    assert event.sequence == 0 and event.hash == "" and event.details == {}
    assert event.group == "" and event.label == "" and not event.is_sealed()
    assert re.match(r"^[0-9a-f-]{36}$", event.event_id)                 # an id was made
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", event.at)  # and the time


def test_an_unset_event_cannot_be_saved_hashed_or_sealed():
    event = AuditEvent()
    for call in (event.to_dict, lambda: event.compute_hash(KEY), lambda: event.seal(1, AuditEvent.GENESIS, KEY)):
        with pytest.raises(ValueError, match="no action"):
            call()


def test_an_empty_action_is_refused_when_anything_else_is_set():
    with pytest.raises(ValueError, match="action must be one of"):
        AuditEvent(actor="Shareen")


@pytest.mark.parametrize("changes, text", [
    ({"action": "deleted"}, "action must be one of"),
    ({"action": None}, "must be text"),
    ({"actor": ""}, "actor"),
    ({"actor": "x" * 81}, "actor"),
    ({"actor": "line\nbreak"}, "actor"),
    ({"result": "maybe"}, "result must be one of ok, failed"),
    ({"client_ref": "x" * 41}, "client reference"),
    ({"client_ref": "a\tb"}, "client reference"),
    ({"details": []}, "details must be an object"),
    ({"details": {"x": {1, 2}}}, "plain JSON"),
    ({"details": {"x": float("nan")}}, "plain JSON"),
    ({"at": "2026-11-15 06:02:11"}, "time must look like"),
    ({"at": "2026-13-45T06:02:11Z"}, "time must look like"),
    ({"at": "9999-12-31T20:00:00Z"}, "time must look like"),     # no Singapore time for it: the pages would crash
    ({"sequence": -1}, "sequence"),
    ({"sequence": True}, "sequence"),
    ({"sequence": "3"}, "sequence"),
    ({"previous_hash": "abc"}, "previous_hash"),
    ({"hash": "A" * 64}, "hash must be"),
    ({"event_id": "x" * 65}, "event id"),
])
def test_impossible_values_are_refused_with_a_message(changes, text):
    with pytest.raises(ValueError, match=text):
        _event(**changes)


def test_values_are_trimmed_and_details_are_copied():
    details = {"changes": []}
    event = _event(actor="  Shareen ", client_ref=" C-0007 ", details=details)
    details["changes"].append("later")
    assert event.actor == "Shareen" and event.client_ref == "C-0007" and event.details == {"changes": []}


def test_an_empty_client_ref_is_allowed():
    assert _event(client_ref="").client_ref == ""


def test_to_dict_has_the_documented_key_order_and_from_dict_round_trips():
    event = _event()
    event.seal(3, "a" * 64, KEY)
    data = event.to_dict()
    assert list(data) == ["event_id", "sequence", "at", "actor", "action", "client_ref", "result",
                          "details", "previous_hash", "hash"]
    again = AuditEvent.from_dict(data)
    assert again.to_dict() == data and again.hash_matches(KEY) and again.is_sealed()


def test_from_dict_accepts_an_unsealed_record_and_drops_unknown_keys():
    event = AuditEvent.from_dict({"action": "signed_in", "actor": "Adrian", "surprise": 1})
    assert event.action == "signed_in" and event.sequence == 0 and "surprise" not in event.to_dict()


@pytest.mark.parametrize("data", [None, [], "x", {}, {"action": ""}, {"action": "nope"},
                                  {"action": "signed_in", "result": "bad"}])
def test_from_dict_refuses_anything_wrong(data):
    with pytest.raises(ValueError):
        AuditEvent.from_dict(data)


def test_the_hash_is_the_same_each_time_and_64_hex():
    event = _event()
    event.seal(1, AuditEvent.GENESIS, KEY)
    assert event.hash == event.compute_hash(KEY) == _sealed().hash
    assert re.match(r"^[0-9a-f]{64}$", event.hash)


def _sealed(**changes) -> AuditEvent:
    event = _event(**changes)
    event.seal(1, AuditEvent.GENESIS, KEY)
    return event


@pytest.mark.parametrize("changes", [
    {"event_id": "id-2"}, {"at": "2026-11-15T06:02:12Z"}, {"actor": "Adrian"}, {"action": "client_created"},
    {"client_ref": "C-0008"}, {"result": "failed"}, {"details": {"changes": []}},
])
def test_the_hash_changes_when_any_field_changes(changes):
    assert _sealed(**changes).hash != _sealed().hash


def test_the_hash_changes_with_the_sequence_and_the_previous_hash():
    first, second, third = _event(), _event(), _event()
    first.seal(1, AuditEvent.GENESIS, KEY)
    second.seal(2, AuditEvent.GENESIS, KEY)
    third.seal(1, "b" * 64, KEY)
    assert len({first.hash, second.hash, third.hash}) == 3


def test_seal_sets_the_chain_fields_and_marks_the_event_sealed():
    event = _event()
    assert not event.is_sealed() and not event.hash_matches(KEY)
    event.seal(5, "c" * 64, KEY)
    assert event.sequence == 5 and event.previous_hash == "c" * 64 and event.is_sealed() and event.hash_matches(KEY)


@pytest.mark.parametrize("sequence, previous", [(0, AuditEvent.GENESIS), (-1, AuditEvent.GENESIS),
                                                (True, AuditEvent.GENESIS), ("1", AuditEvent.GENESIS),
                                                (1, ""), (1, "short"), (1, "G" * 64), (1, None)])
def test_seal_refuses_a_bad_sequence_or_previous_hash(sequence, previous):
    event = _event()
    with pytest.raises(ValueError):
        event.seal(sequence, previous, KEY)
    assert not event.is_sealed()                      # a refused seal changes nothing


def test_hash_matches_turns_false_when_the_stored_hash_is_wrong():
    event = _sealed()
    wrong = AuditEvent.from_dict({**event.to_dict(), "actor": "Someone Else"})
    assert wrong.hash == event.hash and not wrong.hash_matches(KEY)


@pytest.mark.parametrize("action, details, ref, expected", [
    ("signed_in", {}, "", "Signed in"),
    ("signed_out", {}, "", "Signed out"),
    ("sign_in_failed", {"portal": "admin"}, "", "Sign-in attempt at the admin portal"),
    ("sign_in_failed", {}, "", "Sign-in attempt"),
    ("client_created", {}, "C-0007", "Created client C-0007"),
    ("client_edited", {"changes": [{}, {}]}, "C-0007", "Edited client C-0007 (2 fields changed)"),
    ("client_edited", {"changes": [{}]}, "C-0007", "Edited client C-0007 (1 field changed)"),
    ("client_edited", {"changes": "bad"}, "C-0007", "Edited client C-0007 (0 fields changed)"),
    ("autofill_used", {"documents": 2, "fields": 5}, "", "Used document auto-fill (2 documents, 5 fields found)"),
    ("autofill_used", {"documents": 1}, "", "Used document auto-fill (1 document, 0 fields found)"),
    ("document_uploaded", {"file_id": "data/documents/a.pdf"}, "", "Uploaded document data/documents/a.pdf"),
    ("document_downloaded", {"file_id": "x.pdf"}, "", "Downloaded document x.pdf"),
    ("assessment_run", {"outcome": "RISKY"}, "C-0007", "Assessment saved for client C-0007: RISKY"),
    ("assessment_run", {}, "C-0007", "Assessment saved for client C-0007"),
    ("assessment_failed", {}, "C-0007", "Assessment for client C-0007 could not be completed"),
    ("assessment_archived", {"assessment_id": "1a2b3c4d-9999", "reason": "duplicate"}, "C-0007",
     "Archived assessment 1a2b3c4d… (reason: duplicate)"),
    ("assessment_archived", {"assessment_id": "abc"}, "C-0007", "Archived assessment abc"),
    ("assessment_restored", {"assessment_id": "1a2b3c4d-9999"}, "C-0007", "Restored assessment 1a2b3c4d…"),
    ("cloud_sync", {"synced": 4}, "", "Cloud sync (4 records synced)"),
    ("audit_verified", {}, "", "Checked the audit log: no changes found"),
    ("access_refused", {"what": "open the audit log"}, "", "Access refused: open the audit log"),
    ("access_refused", {}, "", "Access refused"),
    ("data_unavailable", {"what": "client records"}, "", "Database unreadable: client records"),
    ("data_unavailable", {}, "", "Database unreadable"),
    ("flag_updated", {"flag_id": "F-SHO-SOW-1-484", "from": "open", "to": "review"}, "SOW-1",
     "Updated flag F-SHO-SOW-1-484 (Open → In review)"),
    ("flag_updated", {"flag_id": "F-INT-303", "from": "review", "to": "review", "note": "checking"}, "",
     "Added a note to flag F-INT-303"),
    ("flag_updated", {}, "", "Added a note to flag"),
])
def test_summary_is_one_plain_line_per_action(action, details, ref, expected):
    assert _event(action=action, details=details, client_ref=ref).summary() == expected


def test_a_failed_event_says_so_at_the_end():
    assert _event(action="assessment_run", result="failed", details={"outcome": "RISKY"}).summary() == \
        "Assessment saved for client C-0007: RISKY — failed"


@pytest.mark.parametrize("action, expected", [
    ("client_created", "Created a client"),
    ("client_edited", "Edited a client (0 fields changed)"),
    ("assessment_run", "Assessment saved for a client"),
    ("assessment_failed", "Assessment for a client could not be completed"),
])
def test_an_action_with_no_client_ref_says_a_client_not_client_a_client(action, expected):
    assert _event(action=action, client_ref="", details={}).summary() == expected


@pytest.mark.parametrize("action, details, expected", [
    ("assessment_archived", {}, "Archived assessment"),
    ("assessment_archived", {"reason": "duplicate"}, "Archived assessment (reason: duplicate)"),
    ("assessment_restored", {}, "Restored assessment"),
    ("document_uploaded", {}, "Uploaded document"),
    ("document_downloaded", {"file_id": ""}, "Downloaded document"),
])
def test_lines_with_missing_parts_have_no_double_or_trailing_spaces(action, details, expected):
    text = _event(action=action, details=details).summary()
    assert text == expected and "  " not in text and text == text.strip()


@pytest.mark.parametrize("changes", [
    {"details": {"x": "\ud800"}}, {"details": {"\ud800": 1}}, {"actor": "a\ud800"},
])
def test_a_lone_surrogate_anywhere_is_refused_at_construction(changes):
    with pytest.raises(ValueError):
        _event(**changes)


def test_non_ascii_text_is_fine_and_is_hashed_as_written():
    event = _sealed(actor="Zoë Müller", details={"note": "日本語"})
    assert event.hash_matches(KEY) and event.details == {"note": "日本語"}


def test_every_action_has_one_group_and_one_label():
    seen = []
    for group, actions in AuditEvent.GROUPS.items():
        for action in actions:
            event = AuditEvent(action=action)
            assert event.group == group
            assert event.label == AuditEvent.LABELS[action] and event.label
            assert event.summary()                                    # nothing raises, nothing empty
            seen.append(action)
    assert tuple(seen) == AuditEvent.ACTIONS and len(set(seen)) == len(seen)
    assert set(AuditEvent.LABELS) == set(AuditEvent.ACTIONS)
    assert list(AuditEvent.GROUPS) == ["Sign-in", "Client", "Documents", "Assessment", "System", "Flag updates"]
    assert AuditEvent(action="flag_updated").label == "Updated a flag"
    assert AuditEvent(action="data_unavailable").group == "System"
    assert AuditEvent(action="data_unavailable").label == "Database unreadable"


def test_a_check_that_found_changes_says_so_and_has_no_failed_suffix():
    event = _event(action="audit_verified", result="failed", details={"intact": False})
    assert event.summary() == "Checked the audit log: changes found"
    assert event.label == "Checked the audit log"


def test_a_different_key_gives_a_different_hash_and_does_not_match():
    event = _sealed()
    other_key = "f" * 64
    assert event.compute_hash(other_key) != event.compute_hash(KEY)
    assert event.hash_matches(KEY) and not event.hash_matches(other_key)


def test_the_hash_is_a_keyed_hmac_not_a_plain_sha256():
    import hashlib
    import json
    event = _sealed()
    data = event.to_dict()
    del data["hash"]
    plain = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False).encode("utf-8")).hexdigest()
    assert event.hash != plain


def test_an_empty_key_is_refused_and_a_refused_seal_changes_nothing():
    event = _event()
    with pytest.raises(ValueError, match="key"):
        event.seal(1, AuditEvent.GENESIS, "")
    assert not event.is_sealed() and event.sequence == 0 and event.previous_hash == ""
    with pytest.raises(ValueError, match="key"):
        _sealed().compute_hash("")
    with pytest.raises(ValueError, match="key"):
        _sealed().hash_matches("")
