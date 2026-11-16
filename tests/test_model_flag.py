"""Flag: validation in __init__, the id, and the names."""

import pytest

from app.model.flag import Flag


def _flag(**changes) -> Flag:
    values = dict(flag_id="F-SHO-SOW-1-484", kind="shop", severity="high", client_ref="SOW-1",
                  headline="Verdict worsened by 2 levels", meaning="Because.", sequences=(480, 481, 484),
                  raised_at="2026-11-13T06:05:00Z", owner="Tan Mei Ling",
                  changes=[{"field": "career.annual_income", "before": 1, "after": 2}])
    values.update(changes)
    return Flag(**values)


def test_a_flag_keeps_what_it_was_given_and_names_its_kind_and_severity():
    flag = _flag()
    assert (flag.flag_id, flag.kind, flag.severity, flag.client_ref) == ("F-SHO-SOW-1-484", "shop", "high", "SOW-1")
    assert flag.sequences == (480, 481, 484) and flag.owner == "Tan Mei Ling" and flag.meaning == "Because."
    assert flag.changes == ({"field": "career.annual_income", "before": 1, "after": 2},)
    assert (flag.name, flag.severity_name) == ("Verdict jump after edit", "High")
    assert (flag.day, flag.usual, flag.broken_at) == ("", 0, 0)


def test_every_kind_and_severity_has_a_name():
    assert set(Flag.NAMES) == set(Flag.KINDS) and set(Flag.SEVERITY_NAMES) == set(Flag.SEVERITIES)
    assert Flag.NAMES["other"] == "Edited by non-owner" and Flag.NAMES["integrity"] == "Log changed outside app"
    assert Flag.SEVERITY_NAMES["low"] == "Low"


def test_the_defaults_make_a_valid_flag():
    assert Flag().flag_id == "F-SHO-1"


def test_a_list_of_entries_is_kept_as_a_tuple():
    assert _flag(sequences=[1, 2]).sequences == (1, 2)


def test_the_changes_cannot_be_edited_through_the_flag():
    source = [{"field": "x", "before": 1, "after": 2}]
    flag = _flag(changes=source)
    source[0]["after"] = 99
    flag.changes[0]["after"] = 5
    assert flag.changes[0]["after"] == 2


@pytest.mark.parametrize("ref,sequence,expected", [
    ("SOW-1", 484, "F-SHO-SOW-1-484"), ("", 303, "F-SHO-303"), ("cl 1/a", 5, "F-SHO-CL-1-A-5"),
    ("--x--", 7, "F-SHO-X-7"), ("!!!", 7, "F-SHO-7"), ("C-0007", 12, "F-SHO-C-0007-12"),
])
def test_make_id_cleans_the_client_reference(ref, sequence, expected):
    assert Flag.make_id("shop", ref, sequence) == expected


def test_make_id_uses_the_first_three_letters_of_the_kind():
    assert Flag.make_id("integrity", "", 303) == "F-INT-303"
    assert Flag.make_id("hours", "CL-1", 9) == "F-HOU-CL-1-9"


def test_an_id_made_by_make_id_is_always_accepted():
    for ref in ("SOW-1", "cl 1/a", "", "C-0007"):
        assert _flag(flag_id=Flag.make_id("shop", ref, 3)).flag_id == Flag.make_id("shop", ref, 3)


@pytest.mark.parametrize("flag_id", ["", "SHO-1", "F-SHO", "F-REP-SOW-1-4", "f-sho-1-4", "F-SHO-sow-1", "F-SHO-1-", 5])
def test_an_id_with_the_wrong_shape_or_kind_is_refused(flag_id):
    with pytest.raises(ValueError, match="flag id|flag_id"):
        _flag(flag_id=flag_id)


@pytest.mark.parametrize("field,value,text", [
    ("kind", "other_kind", "kind must be one of"), ("kind", None, "must be text"),
    ("severity", "alert", "severity must be one of"), ("headline", "  ", "headline"),
    ("headline", "x" * 301, "headline"), ("meaning", "x" * 801, "explanation"),
    ("client_ref", "x" * 41, "client reference"), ("client_ref", "a\nb", "client reference"),
    ("owner", "x" * 81, "owner"), ("sequences", (), "at least one log entry"),
    ("sequences", (0,), "entry number"), ("sequences", ("1",), "entry number"), ("sequences", (True,), "entry number"),
    ("sequences", "12", "list of entry numbers"), ("raised_at", "yesterday", "raised_at"),
    ("raised_at", "2026-11-13T06:05:00", "offset"), ("raised_at", "", "raised_at"),
    ("changes", [1], "Each change"), ("changes", "x", "list of changed fields"),
    ("usual", -1, "usual"), ("usual", "3", "usual"), ("usual", float("nan"), "usual"),
    ("day", "2026-11-13", "Only a failure-spike"), ("broken_at", 3, "Only a log-changed"),
    ("broken_at", -1, "broken_at"),
])
def test_an_impossible_value_is_refused_with_a_clear_message(field, value, text):
    with pytest.raises(ValueError, match=text):
        _flag(**{field: value})


def test_a_time_with_an_offset_is_accepted():
    assert _flag(raised_at="2026-11-13T14:05:00+08:00").raised_at == "2026-11-13T14:05:00+08:00"


def test_a_spike_flag_needs_a_real_day():
    spike = dict(flag_id="F-SPI-9", kind="spike", severity="medium", sequences=(9, 10), usual=1.5, client_ref="")
    assert _flag(**spike, day="2026-11-13").usual == 1.5
    for bad in ("", "2026-13-01", "13/11/2026"):
        with pytest.raises(ValueError, match="needs its day"):
            _flag(**spike, day=bad)


def test_an_integrity_flag_needs_the_broken_entry_but_may_name_no_entries():
    flag = _flag(flag_id="F-INT-303", kind="integrity", client_ref="", sequences=(), broken_at=303)
    assert flag.broken_at == 303 and flag.sequences == ()
    with pytest.raises(ValueError, match="broken_at"):
        _flag(flag_id="F-INT-303", kind="integrity", client_ref="", sequences=(), broken_at=0)
