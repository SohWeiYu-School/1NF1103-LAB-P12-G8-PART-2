"""Repository and JsonRepository: the shared loading and finding, with missing and damaged files."""

import json

import pytest

from app.data.json_repository import JsonRepository
from app.data.repository import Repository


class _Notes(JsonRepository):
    """A small child for these tests: every save adds the record."""

    def save(self, record: dict) -> bool:
        return self._write_all(self.load() + [record])


def _repository(tmp_path):
    return _Notes(str(tmp_path / "db" / "notes.json"), "note_id")


def test_the_interface_and_the_abstract_parent_cannot_be_created(tmp_path):
    with pytest.raises(TypeError):
        Repository()
    with pytest.raises(TypeError):
        JsonRepository(str(tmp_path / "x.json"), "id")


def test_a_json_repository_is_a_repository(tmp_path):
    assert isinstance(_repository(tmp_path), Repository)


def test_a_missing_file_loads_as_no_records(tmp_path):
    assert _repository(tmp_path).load() == []


def test_a_damaged_file_loads_as_no_records(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "notes.json").write_text("[{broken", encoding="utf-8")
    assert repository.load() == []


def test_a_file_that_is_not_a_list_loads_as_no_records(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "notes.json").write_text(json.dumps({"note_id": "N1"}), encoding="utf-8")
    assert repository.load() == []


def test_saving_creates_the_folder_and_the_file(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"note_id": "N1"})
    assert repository.load() == [{"note_id": "N1"}]


def test_find_ignores_upper_and_lower_case(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"note_id": "N1", "text": "first"})
    assert repository.find(" n1 ")["text"] == "first"
    assert repository.find("N2") is None
    assert repository.find("") is None


def test_writing_to_a_place_that_cannot_be_written_returns_false(tmp_path):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x", encoding="utf-8")
    assert _Notes(str(blocker / "notes.json"), "note_id").save({"note_id": "N1"}) is False
