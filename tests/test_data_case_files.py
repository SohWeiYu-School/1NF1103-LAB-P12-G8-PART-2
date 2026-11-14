"""CaseFiles: single JSON files, including a missing and a damaged one."""
import os
import json

from app.data.case_files import CaseFiles


def test_the_real_sample_folder_holds_the_sample_cases():
    names = [os.path.basename(path) for path in CaseFiles().list_samples()]
    assert "case_001.json" in names
    assert names == sorted(names)


def test_a_missing_folder_has_no_samples(tmp_path):
    assert CaseFiles(str(tmp_path / "nowhere")).list_samples() == []


def test_only_json_files_are_listed(tmp_path):
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    assert [os.path.basename(path) for path in CaseFiles(str(tmp_path)).list_samples()] == ["a.json", "b.json"]


def test_load_returns_the_file_contents(tmp_path):
    path = tmp_path / "case.json"
    path.write_text(json.dumps({"client_ref": "SOW-1"}), encoding="utf-8")
    assert CaseFiles().load(str(path)) == {"client_ref": "SOW-1"}


def test_a_missing_file_gives_the_default(tmp_path):
    assert CaseFiles().load(str(tmp_path / "missing.json")) is None
    assert CaseFiles().load(str(tmp_path / "missing.json"), default={}) == {}


def test_a_damaged_file_gives_the_default(tmp_path):
    path = tmp_path / "case.json"
    path.write_text("{broken", encoding="utf-8")
    assert CaseFiles().load(str(path), default={}) == {}


def test_only_the_forecasting_layout_can_be_assessed_directly():
    files = CaseFiles()
    assert files.is_forecasting_case({"client_ref": "SOW-1", "career_history": []})
    assert not files.is_forecasting_case({"client_ref": "SOW-1", "client_profile": {}})
    assert not files.is_forecasting_case(None)
