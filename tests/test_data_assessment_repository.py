"""AssessmentRepository: assessments are added, never replaced."""

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
