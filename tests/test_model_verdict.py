"""Check and Verdict: a finding, and the result made up of findings."""

import pytest

from app.model.check import Check
from app.model.verdict import Verdict


def _check(status="passed", **extra):
    return Check("benchmark", "TOTAL_WEALTH", "Total wealth", "wealth", status, "detail", **extra)


def test_check_group_defaults_to_its_label():
    assert _check().group == "Total wealth"
    assert _check(group="Wealth").group == "Wealth"


def test_check_rejects_an_unknown_status():
    with pytest.raises(ValueError):
        _check(status="broken")


def test_check_status_setter_validates_too():
    check = _check()
    check.status = "explained"
    assert check.status == "explained"
    with pytest.raises(ValueError):
        check.status = "maybe"


def test_only_a_failed_check_counts_as_failed():
    assert _check("failed").failed()
    assert not _check("weak").failed()


def test_check_to_dict_keeps_the_shape_the_report_reads():
    assert _check().to_dict() == {
        "feature": "benchmark", "check": "TOTAL_WEALTH", "label": "Total wealth", "theme": "wealth",
        "status": "passed", "detail": "detail", "explanation": "", "group": "Total wealth"}


def test_check_to_dict_adds_sources_and_supports_only_when_given():
    data = _check(sources=["tax.pdf"], supports=["T2"]).to_dict()
    assert data["sources"] == ["tax.pdf"]
    assert data["supports"] == ["T2"]


def test_check_lists_cannot_be_changed_from_outside():
    check = _check(sources=["tax.pdf"])
    check.sources.append("other.pdf")
    assert check.sources == ["tax.pdf"]


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
