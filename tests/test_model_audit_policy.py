"""AuditPolicy: defaults, each setting's limits, from_dict and to_dict."""

import json

import pytest

from app.model.audit_policy import AuditPolicy

DEFAULTS = {"watched_fields": ["claims.declared_net_worth", "career.annual_income", "claims.expected_aum",
                               "claims.asset_composition", "claims.pep_status", "sow_declaration"],
            "window_days": 30, "repeat_assessments": 3, "jump_levels": 2, "work_start": "08:00",
            "work_end": "20:00", "spike_multiplier": 3, "spike_min": 3, "spike_baseline_days": 14}


def test_the_defaults_are_the_mockup_values():
    policy = AuditPolicy()
    assert policy.to_dict() == DEFAULTS
    assert policy.watched_fields[0] == "claims.declared_net_worth" and len(policy.watched_fields) == 6
    assert (policy.window_days, policy.repeat_assessments, policy.jump_levels) == (30, 3, 2)
    assert (policy.work_start, policy.work_end, policy.spike_multiplier) == ("08:00", "20:00", 3)
    assert (policy.spike_min, policy.spike_baseline_days) == (3, 14)
    assert (policy.work_start_minutes, policy.work_end_minutes) == (480, 1200)


def test_the_real_policy_file_holds_exactly_the_defaults():
    with open("config/policy.json", encoding="utf-8") as handle:
        assert json.load(handle)["audit"] == DEFAULTS
    assert AuditPolicy.from_dict(DEFAULTS).to_dict() == DEFAULTS


def test_from_dict_keeps_a_default_for_a_missing_key_and_round_trips():
    policy = AuditPolicy.from_dict({"window_days": 10, "spike_multiplier": 2.5})
    assert policy.window_days == 10 and policy.spike_multiplier == 2.5 and policy.jump_levels == 2
    assert AuditPolicy.from_dict(policy.to_dict()).to_dict() == policy.to_dict()


def test_from_dict_rejects_an_unknown_key_and_a_non_object():
    with pytest.raises(ValueError, match="Unknown audit setting: window_day"):
        AuditPolicy.from_dict({"window_day": 5})
    with pytest.raises(ValueError, match="must be an object"):
        AuditPolicy.from_dict([1])


@pytest.mark.parametrize("name,value", [
    ("window_days", 0), ("window_days", 1.5), ("window_days", "30"), ("window_days", True),
    ("repeat_assessments", 0), ("repeat_assessments", -1), ("jump_levels", 0), ("jump_levels", 4),
    ("spike_min", 0), ("spike_baseline_days", 0), ("spike_baseline_days", None),
])
def test_a_count_that_cannot_be_right_is_refused_with_its_name(name, value):
    with pytest.raises(ValueError, match=name):
        AuditPolicy(**{name: value})


@pytest.mark.parametrize("value", [0, -1, "3", True, float("nan"), float("inf"), None])
def test_the_spike_multiplier_must_be_a_number_above_zero(value):
    with pytest.raises(ValueError, match="spike_multiplier"):
        AuditPolicy(spike_multiplier=value)


def test_the_smallest_allowed_values_are_accepted():
    policy = AuditPolicy(window_days=1, repeat_assessments=1, jump_levels=1, spike_multiplier=0.5,
                         spike_min=1, spike_baseline_days=1)
    assert policy.jump_levels == 1 and AuditPolicy(jump_levels=3).jump_levels == 3


@pytest.mark.parametrize("name,value", [
    ("work_start", "8:00"), ("work_start", "24:00"), ("work_start", "08:60"), ("work_start", 8),
    ("work_end", "25:00"), ("work_end", "noon"), ("work_end", ""),
])
def test_a_time_must_be_written_hh_mm(name, value):
    with pytest.raises(ValueError, match=name):
        AuditPolicy(**{name: value})


def test_working_hours_must_start_before_they_end():
    with pytest.raises(ValueError, match="earlier than"):
        AuditPolicy(work_start="20:00", work_end="08:00")
    with pytest.raises(ValueError, match="earlier than"):
        AuditPolicy(work_start="09:00", work_end="09:00")
    assert AuditPolicy(work_start="00:00", work_end="24:00").work_end_minutes == 1440


@pytest.mark.parametrize("fields", ["claims.pep_status", (), [], ("a", "a"), ("",), (3,), ("x" * 81,), None])
def test_watched_fields_must_be_a_non_empty_list_of_different_names(fields):
    with pytest.raises(ValueError, match="watched field|watched_fields"):
        AuditPolicy(watched_fields=fields)


def test_a_list_of_watched_fields_is_kept_as_a_tuple():
    assert AuditPolicy(watched_fields=["a.b"]).watched_fields == ("a.b",)
