"""RecordDiff: nested fields, list items, ignored review-status keys, new clients and touches."""

import copy

import pytest

from app.logic.record_diff import RecordDiff
from app.model.client_record import ClientRecord
from app.model.review_status import ReviewStatus
from tests.logic_fixtures import sample_case


def _fields(diff: RecordDiff) -> list[str]:
    return [row["field"] for row in diff.changes()]


def test_no_change_gives_no_rows():
    record = {"name": "Tan", "claims": {"declared_net_worth": 5}, "investments": [{"amount": 1}]}
    assert RecordDiff(record, copy.deepcopy(record)).changes() == []
    assert RecordDiff().changes() == []


def test_a_nested_value_becomes_a_dotted_path_with_before_and_after():
    before = {"claims": {"declared_net_worth": 2000000, "pep_status": False}}
    after = {"claims": {"declared_net_worth": 3500000, "pep_status": False}}
    assert RecordDiff(before, after).changes() == [
        {"field": "claims.declared_net_worth", "before": 2000000, "after": 3500000}]


def test_a_list_item_is_named_by_its_index():
    before = {"investments": [{"amount": 1, "type": "property"}, {"amount": 5, "type": "shares"}]}
    after = {"investments": [{"amount": 1, "type": "property"}, {"amount": 9, "type": "shares"}]}
    assert RecordDiff(before, after).changes() == [{"field": "investments[1].amount", "before": 5, "after": 9}]


def test_a_list_that_grew_shows_the_extra_items_as_added():
    before = {"investments": [{"amount": 1}]}
    after = {"investments": [{"amount": 1}, {"amount": 7}]}
    assert RecordDiff(before, after).changes() == [{"field": "investments[1].amount", "before": None, "after": 7}]


def test_a_list_that_shrank_shows_the_missing_items_as_removed():
    before = {"tags": ["a", "b", "c"]}
    after = {"tags": ["a"]}
    assert RecordDiff(before, after).changes() == [{"field": "tags[1]", "before": "b", "after": None},
                                                   {"field": "tags[2]", "before": "c", "after": None}]


def test_a_list_that_went_from_empty_to_something_gives_only_the_items():
    assert _fields(RecordDiff({"investments": []}, {"investments": [{"amount": 3}]})) == ["investments[0].amount"]


def test_a_value_cleared_to_empty_text_is_a_change():
    assert RecordDiff({"name": "Tan"}, {"name": ""}).changes() == [{"field": "name", "before": "Tan", "after": ""}]


def test_true_is_not_the_same_as_one_but_a_whole_float_equals_its_int():
    assert len(RecordDiff({"x": 1}, {"x": True}).changes()) == 1
    assert RecordDiff({"x": 1}, {"x": 1.0}).changes() == []


def test_rows_are_sorted_by_field_with_list_indexes_in_number_order():
    before = {"z": 1, "a": 1, "investments": [{"v": 0}] * 12}
    after = {"z": 2, "a": 2, "investments": [{"v": n + 1} for n in range(12)]}
    fields = _fields(RecordDiff(before, after))
    assert fields[0] == "a" and fields[-1] == "z"
    assert fields[1:4] == ["investments[0].v", "investments[1].v", "investments[2].v"]
    assert fields[-2] == "investments[11].v"


@pytest.mark.parametrize("key", RecordDiff.IGNORED)
def test_each_review_status_key_is_ignored(key):
    assert RecordDiff({key: "old"}, {key: "new"}).changes() == []


def test_the_ignored_keys_are_exactly_what_the_record_writes_for_a_review():
    status = ReviewStatus()
    status.update("RISKY", "Escalate", "2027-05-16", "2026-11-16", {"anything": 1})
    assert set(status.to_dict()) | {"current_date"} == set(RecordDiff.IGNORED)


def test_an_assessment_written_back_to_a_real_record_is_not_an_edit():
    saved = ClientRecord.from_dict(sample_case()).to_dict()
    status = ReviewStatus()
    status.update("PASSED", "Approve", "2027-11-16", "2026-11-16", {"case": {"a": 1}})
    assessed = {**saved, **status.to_dict(), "current_date": "2026-11-16"}
    assert RecordDiff(saved, assessed).changes() == []
    assert RecordDiff(assessed, saved).changes() == []


def test_a_real_edit_to_a_real_record_is_found_through_the_ignored_keys():
    saved = ClientRecord.from_dict(sample_case()).to_dict()
    edited = copy.deepcopy(saved)
    edited["claims"]["declared_net_worth"] = (edited["claims"].get("declared_net_worth") or 0) + 1_000_000
    edited["outcome"] = "PASSED"
    rows = RecordDiff(saved, edited).changes()
    assert [r["field"] for r in rows] == ["claims.declared_net_worth"]
    assert rows[0]["after"] == rows[0]["before"] + 1_000_000


def test_only_top_level_review_keys_are_ignored():
    assert _fields(RecordDiff({"claims": {"outcome": 1}}, {"claims": {"outcome": 2}})) == ["claims.outcome"]


def test_a_new_client_lists_every_field_with_a_value_and_before_none():
    after = {"client_ref": "C-0007", "name": "Tan", "nationality": "", "career": {"age": 40, "employer": None},
             "investments": [], "claims": {"pep_status": False, "declared_net_worth": 0}, "outcome": "RISKY"}
    rows = RecordDiff(None, after).changes()
    assert [r["field"] for r in rows] == ["career.age", "claims.declared_net_worth", "claims.pep_status",
                                          "client_ref", "name"]
    assert all(r["before"] is None for r in rows)
    assert {r["field"]: r["after"] for r in rows}["claims.pep_status"] is False     # False is a value


def test_a_new_real_client_lists_its_fields_and_ignores_review_status():
    rows = RecordDiff(None, ClientRecord.from_dict(sample_case()).to_dict()).changes()
    assert rows and all(r["before"] is None and r["after"] not in (None, "") for r in rows)
    assert "client_ref" in [r["field"] for r in rows] and "current_date" not in [r["field"] for r in rows]


def test_the_inputs_are_not_changed_and_later_changes_to_them_do_not_matter():
    before, after = {"a": [1]}, {"a": [2]}
    diff = RecordDiff(before, after)
    after["a"][0] = 1
    assert diff.changes() == [{"field": "a[0]", "before": 1, "after": 2}]
    assert before == {"a": [1]}


@pytest.mark.parametrize("before, after", [([], {}), ({}, []), ("x", {}), ({}, "x")])
def test_something_that_is_not_a_record_is_refused(before, after):
    with pytest.raises(ValueError):
        RecordDiff(before, after)


def test_touches_matches_a_field_or_anything_inside_it():
    diff = RecordDiff({"investments": [{"amount": 1}], "claims": {"declared_net_worth": 1}, "name": "A"},
                      {"investments": [{"amount": 2}], "claims": {"declared_net_worth": 1}, "name": "A"})
    assert diff.touches(["investments"]) and diff.touches(["investments[0].amount"])
    assert diff.touches(["name", "investments"])
    assert not diff.touches(["claims"]) and not diff.touches(["invest"]) and not diff.touches([])
    assert not diff.touches(["investments[0].amount.x"])


def test_touches_sees_a_dotted_parent_and_nothing_when_nothing_changed():
    diff = RecordDiff({"claims": {"declared_net_worth": 1}}, {"claims": {"declared_net_worth": 2}})
    assert diff.touches(["claims"]) and diff.touches(["claims.declared_net_worth"])
    assert not RecordDiff({"a": 1}, {"a": 1}).touches(["a"])


@pytest.mark.parametrize("fields", ["investments", None, [1], ("a",)])
def test_touches_refuses_fields_that_are_not_a_list_of_text(fields):
    with pytest.raises(ValueError):
        RecordDiff().touches(fields)


def test_a_missing_field_and_a_field_holding_none_are_the_same():
    assert RecordDiff({"a": None}, {}).changes() == [] and RecordDiff({}, {"a": None}).changes() == []


def test_a_value_replacing_an_empty_container_shows_the_value_with_before_none():
    assert RecordDiff({"claims": {}}, {"claims": {"pep_status": True}}).changes() == [
        {"field": "claims.pep_status", "before": None, "after": True}]
