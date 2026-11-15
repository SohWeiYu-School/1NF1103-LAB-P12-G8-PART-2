"""Verdict: the result of an assessment, made up of Check findings."""

import pytest

from app.model.check import Check
from app.model.verdict import Verdict


def _check(status="passed", **extra):
    return Check("benchmark", "TOTAL_WEALTH", "Total wealth", "wealth", status, "detail", **extra)


def test_only_a_failed_check_counts_as_failed():
    assert _check("failed").failed()
    assert not _check("weak").failed()


def test_verdict_rejects_an_unknown_outcome():
    with pytest.raises(ValueError):
        Verdict("a1", "SOW-1", "2026-09-24", "FINE")


def test_verdict_collects_checks_that_were_made_elsewhere():
    verdict = Verdict("a1", "SOW-1", "2026-09-24", "RISKY", next_step="Escalate")
    check = _check("failed")
    verdict.add_check(check)
    assert verdict.checks() == [check]
    assert verdict.to_dict()["checks"][0]["status"] == "failed"


def test_verdict_only_accepts_check_objects():
    with pytest.raises(ValueError):
        Verdict("a1", "SOW-1", "2026-09-24", "PASSED").add_check({"status": "passed"})


def test_verdict_report_must_be_a_dict():
    verdict = Verdict("a1", "SOW-1", "2026-09-24", "PASSED")
    verdict.report = {"summary": "clean"}
    assert verdict.report == {"summary": "clean"}
    with pytest.raises(ValueError):
        verdict.report = "clean"


def test_verdict_notes_and_not_run_are_copied():
    notes = ["one"]
    verdict = Verdict("a1", "SOW-1", "2026-09-24", "MANUAL_REVIEW", notes=notes, not_run=["forecast"])
    notes.append("two")
    assert verdict.notes == ["one"]
    assert verdict.not_run == ["forecast"]


def test_outcomes_can_be_compared_by_severity():
    assert Verdict.SEVERITY["SERIOUS_RISK"] > Verdict.SEVERITY["RISKY"] > Verdict.SEVERITY["MANUAL_REVIEW"] > Verdict.SEVERITY["PASSED"]
