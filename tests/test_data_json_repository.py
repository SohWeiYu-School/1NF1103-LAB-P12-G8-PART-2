"""Repository and JsonRepository: the shared loading and finding, with missing and damaged files."""

import json
import os
import stat

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


def test_a_json_repository_needs_a_path_and_a_key_field(tmp_path):
    with pytest.raises(TypeError):
        _Notes(str(tmp_path / "x.json"))
    with pytest.raises(ValueError, match="key field"):
        _Notes(str(tmp_path / "x.json"), "")
    with pytest.raises(ValueError, match="key field"):
        _Notes(str(tmp_path / "x.json"), "   ")
    with pytest.raises(ValueError, match="path"):
        _Notes("", "note_id")
    with pytest.raises(ValueError, match="path"):
        _Notes(None, "note_id")


def test_a_json_repository_is_a_repository(tmp_path):
    assert isinstance(_repository(tmp_path), Repository)


def test_a_missing_file_loads_as_no_records(tmp_path):
    assert _repository(tmp_path).load() == []


def test_a_damaged_file_raises_value_error_not_an_empty_list(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "notes.json").write_text("[{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="damaged"):
        repository.load()


def test_a_file_that_is_not_a_list_raises_value_error(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "notes.json").write_text(json.dumps({"note_id": "N1"}), encoding="utf-8")
    with pytest.raises(ValueError, match="list of records"):
        repository.load()


def test_a_list_holding_something_other_than_records_raises_value_error(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "notes.json").write_text(json.dumps([{"note_id": "N1"}, 5]), encoding="utf-8")
    with pytest.raises(ValueError):
        repository.load()


def test_a_file_that_is_not_text_raises_value_error(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "notes.json").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(ValueError):
        repository.load()


def test_a_file_that_cannot_be_read_raises_os_error(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db" / "notes.json").mkdir(parents=True)     # a folder where the file should be
    with pytest.raises(OSError):
        repository.load()


def test_an_empty_list_in_the_file_is_no_records_not_an_error(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "notes.json").write_text("[]", encoding="utf-8")
    assert repository.load() == []


def test_find_raises_when_the_file_is_damaged_and_none_only_when_not_found(tmp_path):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    path = tmp_path / "db" / "notes.json"
    path.write_text("[{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        repository.find("N1")
    path.write_text("[]", encoding="utf-8")
    assert repository.find("N1") is None


def test_a_failed_read_is_logged_with_the_real_details(tmp_path, caplog):
    repository = _repository(tmp_path)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "notes.json").write_text("[{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        repository.load()
    assert "notes.json" in caplog.text and "JSONDecodeError" in caplog.text


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


def _leftover_temporary_files(folder):
    return [name for name in os.listdir(folder) if name.endswith(".tmp")]


def test_a_successful_write_leaves_no_temporary_file(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"note_id": "N1", "text": "café"})
    assert repository.save({"note_id": "N2"})
    assert repository.load() == [{"note_id": "N1", "text": "café"}, {"note_id": "N2"}]
    assert "café" in (tmp_path / "db" / "notes.json").read_text(encoding="utf-8")   # ensure_ascii=False
    assert _leftover_temporary_files(tmp_path / "db") == []


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0,
                    reason="needs a user that a read-only folder can stop")
def test_a_failed_write_returns_false_and_keeps_the_old_file_whole(tmp_path, caplog):
    repository = _repository(tmp_path)
    assert repository.save({"note_id": "N1"})
    path = tmp_path / "db" / "notes.json"
    before = path.read_text(encoding="utf-8")
    os.chmod(tmp_path / "db", stat.S_IRUSR | stat.S_IXUSR)       # read-only folder: no new file can be made
    try:
        assert repository.save({"note_id": "N2"}) is False
        assert path.read_text(encoding="utf-8") == before
        assert _leftover_temporary_files(tmp_path / "db") == []
    finally:
        os.chmod(tmp_path / "db", stat.S_IRWXU)
    assert "notes.json" in caplog.text and "PermissionError" in caplog.text


def test_a_record_json_cannot_hold_returns_false_and_keeps_the_old_file_whole(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"note_id": "N1"})
    path = tmp_path / "db" / "notes.json"
    before = path.read_text(encoding="utf-8")
    assert repository.save({"note_id": "N2", "tags": {"a", "b"}}) is False     # a set is not JSON
    assert path.read_text(encoding="utf-8") == before
    assert _leftover_temporary_files(tmp_path / "db") == []


def test_no_temporary_file_is_left_after_a_good_write(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"note_id": "N-1"}) is True
    assert os.listdir(tmp_path / "db") == ["notes.json"]


def test_no_temporary_file_is_left_after_a_failed_write(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"note_id": "N-1"}) is True
    assert repository.save({"note_id": object()}) is False     # JSON cannot hold this
    assert os.listdir(tmp_path / "db") == ["notes.json"]
    assert repository.load() == [{"note_id": "N-1"}]


def test_two_repositories_writing_one_file_from_threads_leave_valid_json(tmp_path):
    import threading
    first, second = _repository(tmp_path), _repository(tmp_path)
    results = []

    def work(repository, tag):
        for number in range(20):
            results.append(repository._write_all([{"note_id": f"{tag}-{number}"}] * 50))

    threads = [threading.Thread(target=work, args=(first, "a")), threading.Thread(target=work, args=(second, "b"))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(results)
    assert len(first.load()) == 50
    assert os.listdir(tmp_path / "db") == ["notes.json"]
