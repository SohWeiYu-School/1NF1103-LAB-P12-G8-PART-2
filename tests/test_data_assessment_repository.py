"""AssessmentRepository: assessments are added, never replaced."""

import copy

from app.data.assessment_repository import AssessmentRepository
from app.data.client_repository import ClientRepository

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


def test_an_assessment_keeps_the_client_as_it_was(tmp_path):
    clients = ClientRepository(str(tmp_path / "sow_cases.json"))
    repository = _repository(tmp_path)
    client = {"client_ref": "SOW-1", "name": "Old Name"}
    clients.save(client)
    repository.save({"client_ref": "SOW-1", "assessed_at": "2026-10-23", "case": copy.deepcopy(client)})
    clients.save({"client_ref": "SOW-1", "name": "New Name"})
    assert repository.for_client("SOW-1")[0]["case"]["name"] == "Old Name"


def test_an_archived_assessment_is_hidden_from_the_lists_but_not_deleted(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "assessment_id": "A-1", "assessed_at": "2026-01-10", "outcome": "RISKY"})
    repository.save({"client_ref": "SOW-1", "assessment_id": "A-2", "assessed_at": "2026-03-05", "outcome": "RISKY"})
    assert repository.archive("A-1", "typed the wrong net worth")
    assert [record["assessment_id"] for record in repository.for_client("SOW-1")] == ["A-2"]
    assert [record["assessment_id"] for record in repository.query("RISKY")] == ["A-2"]
    assert len(repository.load()) == 2
    assert repository.find("A-1") is not None
    assert len(repository.for_client("SOW-1", include_archived=True)) == 2


def test_a_restored_assessment_is_back_in_the_lists_and_the_log_keeps_both_steps(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "assessment_id": "A-1", "outcome": "RISKY"})
    repository.archive("A-1", "outdated")
    assert repository.restore("A-1")
    assert [record["assessment_id"] for record in repository.for_client("SOW-1")] == ["A-1"]
    log = repository.find("A-1")["archive_log"]
    assert [line["action"] for line in log] == ["archived", "restored"]
    assert log[0]["reason"] == "outdated"


def test_archiving_changes_nothing_but_the_archive_log(tmp_path):
    repository = _repository(tmp_path)
    original = {"client_ref": "SOW-1", "assessment_id": "A-1", "outcome": "RISKY",
                "case": {"name": "Old Name"}, "verdict": {"verdict": "RISKY"}}
    repository.save(original)
    repository.archive("A-1")
    saved = repository.find("A-1")
    saved.pop("archive_log")
    assert saved == original


def test_archiving_an_unknown_or_already_archived_assessment_does_nothing(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "assessment_id": "A-1"})
    assert repository.archive("A-9") is False
    assert repository.restore("A-1") is False          # not archived yet
    assert repository.archive("A-1") is True
    assert repository.archive("A-1") is False          # already archived
    assert len(repository.find("A-1")["archive_log"]) == 1
