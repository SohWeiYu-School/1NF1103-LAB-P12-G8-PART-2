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


def _explanation(**changes) -> dict:
    explanation = {"name": "Daniel Tan", "assessed_on": "2026-09-24", "policy_version": "v1",
                   "verdict_label": "RISKY", "summary": "Why.", "reasons": [{"level": "RISKY", "text": "Why."}],
                   "agreement": [], "types": [], "documents": [{"document": "Payslips", "reason": "Pay"}],
                   "clean": ["Liquidity"], "evidence": [{"title": "Research reports", "lines": []}]}
    explanation.update(changes)
    return explanation


def test_an_explanation_must_hold_every_part_and_nothing_else():
    verdict = Verdict("a1", "SOW-1", "2026-09-24", "RISKY")
    with pytest.raises(ValueError, match="missing: summary"):
        verdict.explanation = {key: value for key, value in _explanation().items() if key != "summary"}
    with pytest.raises(ValueError, match="not allowed: extra"):
        verdict.explanation = _explanation(extra=1)
    with pytest.raises(ValueError):
        verdict.explanation = ["not", "a", "dict"]
    verdict.explanation = _explanation()
    assert verdict.explanation == _explanation()


def test_a_check_from_an_unknown_feature_is_refused():
    with pytest.raises(ValueError, match="'payroll'"):
        Verdict().add_check(Check("payroll", "PAY", "Pay", "wealth"))


def test_details_cannot_be_laid_out_without_an_explanation():
    with pytest.raises(ValueError, match="no explanation"):
        Verdict("a1", "SOW-1", "2026-09-24", "RISKY").details()


def test_details_give_the_saved_layout_with_every_check_under_its_feature():
    verdict = Verdict("a1", "SOW-1", "2026-09-24T01:02:03+00:00", "RISKY", "Escalate", "2027-03-24",
                      notes=["a note"], not_run=["The forecast"])
    checks = [Check("forecast", "STABILITY", "Stability", "wealth"), _check("failed"),
              Check("documents", "NO_DOCUMENTS", "Supporting documents", "pattern", "info", sources=[]),
              Check("crime", "CRIME_SCAN", "Crime scan", "pattern", "skipped"), _check("passed")]
    for check in checks:
        verdict.add_check(check)
    verdict.explanation = _explanation()
    details = verdict.details()
    assert list(details) == ["client_ref", "name", "assessed_on", "policy_version", "verdict", "verdict_label",
                             "next_step", "next_review_date", "summary", "reasons", "agreement", "benchmark",
                             "forecast", "crime", "document_findings", "types", "documents", "clean", "not_run",
                             "notes", "evidence"]
    assert (details["client_ref"], details["verdict"], details["next_step"], details["next_review_date"]) == (
        "SOW-1", "RISKY", "Escalate", "2027-03-24")
    assert details["assessed_on"] == "2026-09-24"           # the case's date, not when it was saved
    assert details["benchmark"] == [checks[1].to_dict(), checks[4].to_dict()]
    assert details["forecast"] == [checks[0].to_dict()]
    assert details["crime"] == [checks[3].to_dict()]
    assert details["document_findings"] == [checks[2].to_dict()]
    assert (details["notes"], details["not_run"]) == (["a note"], ["The forecast"])
    for key in ("summary", "reasons", "agreement", "types", "documents", "clean", "evidence", "policy_version"):
        assert details[key] == _explanation()[key]
