"""ConfigReader: the settings files, including a missing or damaged one."""

import json

from app.data.config_reader import ConfigReader


def _write(folder, name, data):
    (folder / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


def test_the_real_config_folder_has_no_problems():
    assert ConfigReader().problems() == []


def test_read_returns_the_file_contents(tmp_path):
    _write(tmp_path, "policy", {"policy_version": "1"})
    assert ConfigReader(str(tmp_path)).read("policy") == {"policy_version": "1"}


def test_a_file_is_read_once_and_kept(tmp_path):
    _write(tmp_path, "policy", {"policy_version": "1"})
    reader = ConfigReader(str(tmp_path))
    reader.read("policy")
    _write(tmp_path, "policy", {"policy_version": "2"})
    assert reader.read("policy") == {"policy_version": "1"}


def test_a_missing_file_gives_an_empty_dict(tmp_path):
    assert ConfigReader(str(tmp_path)).read("policy") == {}


def test_a_damaged_file_gives_an_empty_dict(tmp_path):
    (tmp_path / "policy.json").write_text("{not json", encoding="utf-8")
    assert ConfigReader(str(tmp_path)).read("policy") == {}


def test_a_file_that_is_not_an_object_gives_an_empty_dict(tmp_path):
    _write(tmp_path, "policy", ["a", "list"])
    assert ConfigReader(str(tmp_path)).read("policy") == {}


def test_problems_names_every_missing_setting(tmp_path):
    _write(tmp_path, "vocabulary", {"signal_codes": {"A": "a"}})
    _write(tmp_path, "policy", {"policy_version": "1"})
    problems = ConfigReader(str(tmp_path)).problems()
    assert "config/vocabulary.json is missing 'document_codes'" in problems
    assert "config/policy.json is missing 'routing'" in problems
    assert "config/vocabulary.json is missing 'signal_codes'" not in problems
