"""AuditChain: intact chains, edits, deletions, reordering, unreadable rows and the summary texts."""

import copy

import pytest

from app.logic.audit_chain import AuditChain
from app.model.audit_event import AuditEvent
from tests.conftest import TEST_AUDIT_KEY as KEY


def _chain(count: int) -> list[dict]:
    """Rows sealed one after another, the way the repository would, but with no file."""
    rows: list[dict] = []
    previous = AuditEvent.GENESIS
    for number in range(1, count + 1):
        event = AuditEvent(event_id=f"id-{number}", at=f"2026-11-15T06:00:{number:02d}Z", actor="Shareen",
                           action="client_edited", client_ref="C-0007", details={"changes": [{"n": number}]})
        event.seal(number, previous, KEY)
        previous = event.hash
        rows.append(event.to_dict())
    return rows


def test_an_empty_list_is_intact_and_says_no_entries_yet():
    chain = AuditChain([], KEY)
    assert chain.intact() and chain.breaks() == [] and chain.events() == [] and chain.unreadable_count() == 0
    assert chain.summary() == "No entries yet."
    assert AuditChain().summary() == "No entries yet."


def test_an_intact_chain_checks_out():
    chain = AuditChain(_chain(5), KEY)
    assert chain.intact() and chain.breaks() == [] and len(chain.events()) == 5
    assert chain.summary() == "No changes found in the 5 entries."
    assert AuditChain(_chain(1), KEY).summary() == "No changes found in the 1 entry."


def test_events_come_back_in_file_order():
    assert [e.sequence for e in AuditChain(_chain(4), KEY).events()] == [1, 2, 3, 4]


def test_an_edited_field_breaks_the_chain_at_that_sequence_only():
    rows = _chain(5)
    rows[2]["actor"] = "Someone Else"
    chain = AuditChain(rows, KEY)
    assert not chain.intact() and chain.breaks() == [3]
    assert chain.summary() == "The log has been changed outside the app: entry 3 does not match."


def test_an_edited_detail_is_caught_too():
    rows = _chain(3)
    rows[0]["details"]["changes"][0]["n"] = 99
    assert AuditChain(rows, KEY).breaks() == [1]


def test_a_deleted_middle_row_breaks_at_the_position_of_the_row_after_it():
    rows = _chain(5)
    del rows[2]
    chain = AuditChain(rows, KEY)
    assert chain.breaks() == [3] and not chain.intact()          # position 3 now holds the row with sequence 4


def test_a_deleted_first_row_is_caught():
    assert AuditChain(_chain(3)[1:], KEY).breaks() == [1]


def test_a_deleted_last_row_cannot_be_seen_by_the_chain_itself():
    assert AuditChain(_chain(5)[:-1], KEY).intact()           # the chain only proves what is there


def test_swapped_rows_are_caught():
    rows = _chain(4)
    rows[1], rows[2] = rows[2], rows[1]
    assert AuditChain(rows, KEY).breaks() == [2, 3, 4]


def test_a_row_whose_hash_was_recomputed_after_editing_still_breaks_the_link_after_it():
    rows = _chain(4)
    rows[1]["actor"] = "Forger"
    forged = AuditEvent.from_dict(rows[1])
    rows[1]["hash"] = forged.compute_hash(KEY)
    assert AuditChain(rows, KEY).breaks() == [3]               # row 3's previous_hash no longer matches


def test_a_row_with_the_wrong_sequence_breaks():
    rows = _chain(3)
    rows[1]["sequence"] = 5
    assert AuditChain(rows, KEY).breaks()[0] == 2              # named by position, not by the 5 stored in the row


def test_a_row_that_was_never_sealed_breaks():
    rows = _chain(2) + [AuditEvent(action="signed_in").to_dict()]
    assert AuditChain(rows, KEY).breaks() == [3]


def test_an_unreadable_row_is_counted_kept_out_of_events_and_is_a_break():
    rows = _chain(4)
    rows[1]["action"] = "made_up_action"
    chain = AuditChain(rows, KEY)
    assert chain.unreadable_count() == 1 and len(chain.events()) == 3
    assert not chain.intact() and chain.breaks() == [2]
    assert chain.summary() == "The log has been changed outside the app: 1 entry can't be read."


def test_rows_that_are_not_even_objects_are_unreadable_not_a_crash():
    rows = _chain(2) + ["junk", None, 5]
    chain = AuditChain(rows, KEY)
    assert chain.unreadable_count() == 3 and chain.breaks() == [3, 4, 5]


def test_the_row_after_an_unreadable_one_is_still_checked_against_its_stored_hash():
    rows = _chain(4)
    rows[1]["result"] = "maybe"                          # unreadable, but its hash field is still there
    assert AuditChain(rows, KEY).breaks() == [2]               # rows 3 and 4 still link up


def test_a_mismatch_and_unreadable_rows_are_both_reported():
    rows = _chain(6)
    rows[1]["actor"] = "Forger"
    rows[3]["action"] = "nope"
    rows[4]["action"] = "nope"
    assert AuditChain(rows, KEY).summary() == ("The log has been changed outside the app: entry 2 does not match. "
                                         "2 entries can't be read.")


def test_several_mismatches_are_named_and_a_long_list_is_cut_short():
    rows = _chain(10)
    for index in (1, 3):
        rows[index]["actor"] = "Forger"
    assert AuditChain(rows, KEY).summary() == "The log has been changed outside the app: entries 2, 4 do not match."
    for index in range(10):
        rows[index]["actor"] = "Forger"
    assert AuditChain(rows, KEY).summary().endswith("entries 1, 2, 3, 4, 5 and 5 more do not match.")


def test_the_rows_given_are_not_changed():
    rows = _chain(3)
    snapshot = copy.deepcopy(rows)
    AuditChain(rows, KEY).summary()
    assert rows == snapshot


def test_rows_that_are_not_a_list_are_refused():
    with pytest.raises(ValueError, match="list"):
        AuditChain({"a": 1}, KEY)


@pytest.mark.parametrize("key", ["event_id", "sequence", "at", "action", "previous_hash", "hash"])
def test_a_row_missing_any_required_field_is_unreadable_and_never_filled_in(key):
    rows = _chain(3)
    del rows[1][key]
    chain = AuditChain(rows, KEY)
    assert chain.unreadable_count() == 1 and len(chain.events()) == 2 and chain.breaks()[0] == 2


@pytest.mark.parametrize("key", ["event_id", "at"])
def test_a_row_with_an_empty_id_or_time_is_unreadable_not_given_a_new_one(key):
    rows = _chain(3)
    rows[1][key] = ""
    assert AuditChain(rows, KEY).unreadable_count() == 1


def test_breaks_are_positions_even_when_the_stored_sequences_are_forged():
    rows = _chain(4)
    for row in rows:
        row["sequence"] = 1000
    assert AuditChain(rows, KEY).breaks()[0] == 1


def test_broken_ids_are_the_event_ids_of_the_readable_rows_that_break():
    rows = _chain(5)
    rows[2]["actor"] = "Someone Else"
    rows[4]["details"] = {"changes": []}
    chain = AuditChain(rows, KEY)
    assert chain.broken_ids() == ["id-3", "id-5"]
    assert AuditChain(_chain(3), KEY).broken_ids() == []
    assert AuditChain([], KEY).broken_ids() == []


def test_an_unreadable_row_has_no_id_to_name_but_the_rows_around_it_are_still_checked():
    rows = _chain(4)
    rows[1] = {"action": "bogus"}
    rows[2]["actor"] = "Someone Else"
    chain = AuditChain(rows, KEY)
    assert chain.unreadable_count() == 1 and chain.broken_ids() == ["id-3"]


def test_broken_ids_is_a_copy():
    chain = AuditChain(_chain(2), KEY)
    chain.broken_ids().append("x")
    assert chain.broken_ids() == []


def test_a_chain_checked_with_the_wrong_key_breaks_everywhere():
    chain = AuditChain(_chain(3), "f" * 64)
    assert chain.breaks() == [1, 2, 3] and not chain.intact()


def test_a_row_recomputed_with_plain_sha256_and_no_key_is_a_break():
    import hashlib
    import json
    rows = _chain(3)
    rows[1]["actor"] = "Forger"
    data = {k: v for k, v in rows[1].items() if k != "hash"}
    rows[1]["hash"] = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                                ensure_ascii=False).encode("utf-8")).hexdigest()
    assert 2 in AuditChain(rows, KEY).breaks()


def test_padded_text_does_not_change_the_hash_but_is_still_a_break():
    rows = _chain(3)
    rows[1]["actor"] = "  Shareen  "
    assert AuditEvent.from_dict(rows[1]).hash_matches(KEY)         # the normalised hash cannot see it
    assert AuditChain(rows, KEY).breaks() == [2]


def test_an_extra_key_is_a_break():
    rows = _chain(3)
    rows[0]["note"] = "added by hand"
    assert AuditChain(rows, KEY).breaks() == [1]


def test_a_removed_default_valued_key_is_a_break():
    rows = _chain(3)
    rows[2].pop("result")      # "result" is "ok", the default
    assert AuditChain(rows, KEY).breaks() == [3]


def test_rows_with_an_empty_key_are_refused_but_no_rows_need_none():
    with pytest.raises(ValueError, match="key"):
        AuditChain(_chain(1), "")
    assert AuditChain([], "").intact()
