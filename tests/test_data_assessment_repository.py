"""AssessmentRepository: assessments are added, never replaced."""

import json
import logging
import threading

import pytest

from app.data.assessment_repository import AssessmentRepository


def _repository(tmp_path):
    return AssessmentRepository(str(tmp_path / "ai_assessments.json"))


def test_every_save_adds_a_record_even_for_the_same_client(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"client_ref": "SOW-1", "outcome": "RISKY"})
    assert repository.save({"client_ref": "SOW-1", "outcome": "PASSED"})
    assert len(repository.load()) == 2


def test_an_assessment_with_no_id_is_given_one(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1"})
    repository.save({"client_ref": "SOW-1", "assessment_id": "A-7"})
    first, second = repository.load()
    assert first["assessment_id"]
    assert second["assessment_id"] == "A-7"


def test_an_assessment_with_no_client_reference_is_not_saved(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"outcome": "PASSED"}) is False
    assert repository.load() == []


def test_find_returns_one_assessment_by_its_id(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "assessment_id": "A-7", "outcome": "RISKY"})
    assert repository.find("A-7")["outcome"] == "RISKY"
    assert repository.find("A-8") is None


def test_for_client_lists_only_that_client_newest_first(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "assessed_at": "2026-01-10", "outcome": "RISKY"})
    repository.save({"client_ref": "SOW-2", "assessed_at": "2026-02-01", "outcome": "PASSED"})
    repository.save({"client_ref": "SOW-1", "assessed_at": "2026-03-05", "outcome": "PASSED"})
    assert [record["assessed_at"] for record in repository.for_client("SOW-1")] == ["2026-03-05", "2026-01-10"]


def test_query_filters_by_outcome_and_reads_older_records(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "outcome": "RISKY"})
    repository.save({"client_ref": "SOW-2", "assessment": {"outcome": "RISKY"}})
    repository.save({"client_ref": "SOW-3", "outcome": "PASSED"})
    assert [record["client_ref"] for record in repository.query("RISKY")] == ["SOW-1", "SOW-2"]
    assert len(repository.query("")) == 3


def test_a_damaged_file_is_not_overwritten_by_a_save(tmp_path):
    path = tmp_path / "ai_assessments.json"
    path.write_bytes(b'[{"client_ref": "SOW-1", "assessment_id": "A-1"}, broken')
    before = path.read_bytes()
    assert _repository(tmp_path).save({"client_ref": "SOW-2"}) is False
    assert path.read_bytes() == before


def test_every_read_raises_when_the_file_is_damaged(tmp_path):
    (tmp_path / "ai_assessments.json").write_text("{}", encoding="utf-8")
    repository = _repository(tmp_path)
    for read in (repository.load, lambda: repository.find("A-1"), lambda: repository.for_client("SOW-1"),
                 lambda: repository.query(""), lambda: repository.query("PASSED")):
        with pytest.raises(ValueError):
            read()


def test_a_file_that_cannot_be_read_stops_save(tmp_path):
    (tmp_path / "ai_assessments.json").mkdir()
    repository = _repository(tmp_path)
    with pytest.raises(OSError):
        repository.load()
    assert repository.save({"client_ref": "SOW-1"}) is False


def test_query_skips_an_older_record_whose_assessment_part_is_not_a_dict(tmp_path):
    path = tmp_path / "ai_assessments.json"
    path.write_text('[{"assessment_id": "A1", "client_ref": "CL-1", "assessment": "old text"},'
                    ' {"assessment_id": "A2", "client_ref": "CL-1", "outcome": "PASSED"}]', encoding="utf-8")
    assert [r["assessment_id"] for r in _repository(tmp_path).query("PASSED")] == ["A2"]


# ----- archive and restore -------------------------------------------------------------------

R = AssessmentRepository


def _with_two(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "assessment_id": "A-1", "assessed_at": "2026-01-01", "outcome": "RISKY"})
    repository.save({"client_ref": "SOW-1", "assessment_id": "A-2", "assessed_at": "2026-02-01", "outcome": "PASSED"})
    return repository


def test_archive_adds_a_log_line_and_changes_nothing_else(tmp_path):
    repository = _with_two(tmp_path)
    before = repository.find("A-1")
    assert repository.archive("A-1", "  duplicate  ") == R.CHANGED
    after = repository.find("A-1")
    log = after.pop("archive_log")
    assert after == before
    assert len(log) == 1 and log[0]["action"] == "archived" and log[0]["reason"] == "duplicate"
    assert log[0]["at"].endswith("+00:00")


def test_archive_without_a_reason_leaves_the_reason_out(tmp_path):
    repository = _with_two(tmp_path)
    repository.archive("A-1")
    assert "reason" not in repository.find("A-1")["archive_log"][0]


def test_archive_twice_and_restore_when_not_archived_change_nothing(tmp_path):
    repository = _with_two(tmp_path)
    assert repository.restore("A-1") == R.NO_CHANGE
    assert repository.archive("A-1") == R.CHANGED
    assert repository.archive("A-1") == R.NO_CHANGE
    assert len(repository.find("A-1")["archive_log"]) == 1


def test_restore_appends_and_the_last_entry_decides(tmp_path):
    repository = _with_two(tmp_path)
    repository.archive("A-1")
    assert repository.restore("A-1") == R.CHANGED
    record = repository.find("A-1")
    assert [entry["action"] for entry in record["archive_log"]] == ["archived", "restored"]
    assert R.archive_state(record) == R.ACTIVE
    assert repository.archive("A-1") == R.CHANGED
    assert R.archive_state(repository.find("A-1")) == R.ARCHIVED


def test_unknown_or_empty_id_is_not_found(tmp_path):
    repository = _with_two(tmp_path)
    assert repository.archive("nope") == R.NOT_FOUND
    assert repository.restore("nope") == R.NOT_FOUND
    assert repository.archive("  ") == R.NOT_FOUND


def test_the_id_is_matched_like_find_does(tmp_path):
    repository = _with_two(tmp_path)
    assert repository.archive("  a-1 ") == R.CHANGED


def test_a_bad_reason_is_refused_and_nothing_is_written(tmp_path):
    repository = _with_two(tmp_path)
    for bad in ("x" * (R.MAX_REASON_LENGTH + 1), "two\nlines", "tab\there", 5):
        with pytest.raises(ValueError):
            repository.archive("A-1", bad)
    assert "archive_log" not in repository.find("A-1")
    assert repository.archive("A-1", "x" * R.MAX_REASON_LENGTH) == R.CHANGED


def test_reason_problem_explains_each_bad_reason_and_accepts_good_ones():
    assert R.reason_problem("") == "" and R.reason_problem("  typed the wrong net worth  ") == ""
    assert R.reason_problem(5) == "The reason must be text."
    assert "at most 200 characters" in R.reason_problem("x" * 201)
    assert "printable" in R.reason_problem("two\nlines")


def test_lists_hide_archived_unless_asked(tmp_path):
    repository = _with_two(tmp_path)
    repository.archive("A-1")
    assert [r["assessment_id"] for r in repository.for_client("SOW-1")] == ["A-2"]
    assert [r["assessment_id"] for r in repository.for_client("SOW-1", include_archived=True)] == ["A-2", "A-1"]
    assert [r["assessment_id"] for r in repository.query("")] == ["A-2"]
    assert [r["assessment_id"] for r in repository.query("", True)] == ["A-1", "A-2"]
    assert repository.query("RISKY") == []
    assert [r["assessment_id"] for r in repository.query("RISKY", include_archived=True)] == ["A-1"]
    repository.restore("A-1")
    assert len(repository.for_client("SOW-1")) == 2


DAMAGED_LOGS = ["text", 5, {"action": "archived"}, ["archived"], [None], [{"action": "deleted"}],
                [{"action": "archived"}, "x"], [{"at": "2026"}], [{"action": "bogus"}, {"action": "archived"}],
                "", {}, 0, False,                                            # empty, but not a list
                [{"action": "archived", "at": 12345}], [{"action": "archived", "at": {"x": 1}}],
                [{"action": "archived", "at": "2026-11-16", "reason": 7}]]


def test_archive_state_of_every_damaged_shape_is_unreadable():
    for log in DAMAGED_LOGS:
        assert R.archive_state({"archive_log": log}) == R.UNREADABLE, log
        assert R.is_archived({"archive_log": log}) is True


def test_archive_state_of_good_and_empty_logs():
    for log in (None, []):
        assert R.archive_state({"archive_log": log}) == R.ACTIVE
    assert R.archive_state({}) == R.ACTIVE
    assert R.is_archived({}) is False
    assert R.archive_state({"archive_log": [{"action": "archived"}, {"action": "restored"}]}) == R.ACTIVE
    assert R.archive_state({"archive_log": [{"action": "restored"}, {"action": "archived"}]}) == R.ARCHIVED


def test_archive_state_does_not_log(caplog):
    with caplog.at_level(logging.DEBUG):
        R.archive_state({"archive_log": "text"})
    assert caplog.records == []


def test_a_damaged_log_is_hidden_listed_on_request_and_warned_once_per_call(tmp_path, caplog):
    path = tmp_path / "ai_assessments.json"
    path.write_text(json.dumps([
        {"client_ref": "C", "assessment_id": "A-1", "archive_log": "text"},
        {"client_ref": "C", "assessment_id": "A-2", "archive_log": [{"action": "bogus"}]},
        {"client_ref": "C", "assessment_id": "A-3"}]), encoding="utf-8")
    repository = _repository(tmp_path)
    with caplog.at_level(logging.WARNING):
        assert [r["assessment_id"] for r in repository.for_client("C")] == ["A-3"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "A-1" in warnings[0].getMessage() and "A-2" in warnings[0].getMessage()
    assert len(repository.query("", include_archived=True)) == 3


def test_archive_and_restore_of_a_damaged_log_change_nothing(tmp_path):
    path = tmp_path / "ai_assessments.json"
    path.write_text(json.dumps([{"client_ref": "C", "assessment_id": "A-1", "archive_log": "text"}]), encoding="utf-8")
    before = path.read_bytes()
    repository = _repository(tmp_path)
    assert repository.archive("A-1") == R.UNREADABLE
    assert repository.restore("A-1") == R.UNREADABLE
    assert path.read_bytes() == before


def test_a_null_archive_log_gets_a_fresh_list(tmp_path):
    path = tmp_path / "ai_assessments.json"
    path.write_text(json.dumps([{"client_ref": "C", "assessment_id": "A-1", "archive_log": None}]), encoding="utf-8")
    repository = _repository(tmp_path)
    assert repository.archive("A-1") == R.CHANGED
    assert repository.find("A-1")["archive_log"][0]["action"] == "archived"


def test_archive_and_restore_raise_when_the_file_cannot_be_read(tmp_path):
    (tmp_path / "ai_assessments.json").write_text("{}", encoding="utf-8")
    repository = _repository(tmp_path)
    with pytest.raises(ValueError):
        repository.archive("A-1")
    with pytest.raises(ValueError):
        repository.restore("A-1")
    unreadable = tmp_path / "dir"
    unreadable.mkdir()
    (unreadable / "ai_assessments.json").mkdir()
    with pytest.raises(OSError):
        AssessmentRepository(str(unreadable / "ai_assessments.json")).archive("A-1")


def test_a_failed_write_is_reported_as_not_saved(tmp_path, caplog):
    class FailingWrite(AssessmentRepository):
        def _write_all(self, records):
            return False
    path = tmp_path / "ai_assessments.json"
    path.write_text(json.dumps([{"client_ref": "C", "assessment_id": "A-1"}]), encoding="utf-8")
    before = path.read_bytes()
    with caplog.at_level(logging.ERROR):
        assert FailingWrite(str(path)).archive("A-1") == R.NOT_SAVED
    assert path.read_bytes() == before
    assert any("not saved" in r.getMessage() for r in caplog.records)


def test_save_and_archive_hold_the_same_lock(tmp_path):
    """A write that is slow lets the other thread try to get in; both changes must survive."""
    entered = threading.Event()
    release = threading.Event()

    class SlowWrite(AssessmentRepository):
        def __init__(self, path):
            super().__init__(path)
            self.slow_once = True

        def _write_all(self, records):
            if self.slow_once:
                self.slow_once = False
                entered.set()
                release.wait(timeout=5)
            return super()._write_all(records)

    repository = SlowWrite(str(tmp_path / "ai_assessments.json"))
    repository.save({"client_ref": "C", "assessment_id": "A-1"})
    repository.slow_once = True
    saver = threading.Thread(target=lambda: repository.save({"client_ref": "C", "assessment_id": "A-2"}))
    results = []
    archiver = threading.Thread(target=lambda: results.append(repository.archive("A-1")))
    saver.start()
    assert entered.wait(timeout=5)
    archiver.start()
    archiver.join(timeout=0.3)
    assert archiver.is_alive()          # waiting for the lock while the save is in progress
    release.set()
    saver.join(timeout=5)
    archiver.join(timeout=5)
    assert results == [R.CHANGED]
    ids = {r["assessment_id"]: r for r in repository.load()}
    assert set(ids) == {"A-1", "A-2"}
    assert R.archive_state(ids["A-1"]) == R.ARCHIVED
