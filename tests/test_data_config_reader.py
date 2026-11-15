"""ConfigReader: the settings files, including a missing or damaged one."""

import json

import pytest

from app.data.config_reader import ConfigReader


def _write(folder, name, data):
    (folder / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


def test_the_real_config_folder_has_no_problems():
    assert ConfigReader().problems() == []


def test_file_names_lists_the_policy_then_the_vocabulary_and_each_has_required_keys():
    assert ConfigReader.FILE_NAMES == ("policy", "vocabulary")
    assert all(name in ConfigReader.REQUIRED for name in ConfigReader.FILE_NAMES)


def test_read_returns_the_file_contents(tmp_path):
    _write(tmp_path, "policy", {"policy_version": "1"})
    assert ConfigReader(str(tmp_path)).read("policy") == {"policy_version": "1"}


def test_a_file_is_read_once_and_kept(tmp_path):
    _write(tmp_path, "policy", {"policy_version": "1"})
    reader = ConfigReader(str(tmp_path))
    reader.read("policy")
    _write(tmp_path, "policy", {"policy_version": "2"})
    assert reader.read("policy") == {"policy_version": "1"}


def test_a_missing_file_raises_an_os_error_not_an_empty_dict(tmp_path):
    with pytest.raises(OSError):
        ConfigReader(str(tmp_path)).read("policy")


def test_a_damaged_file_raises_a_value_error_and_logs_the_details(tmp_path, caplog):
    (tmp_path / "policy.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        ConfigReader(str(tmp_path)).read("policy")
    assert "policy.json" in caplog.text


def test_a_file_that_is_not_an_object_raises_a_value_error(tmp_path):
    _write(tmp_path, "policy", ["a", "list"])
    with pytest.raises(ValueError):
        ConfigReader(str(tmp_path)).read("policy")


def test_a_file_that_really_holds_an_empty_object_is_read_as_empty(tmp_path):
    _write(tmp_path, "policy", {})
    assert ConfigReader(str(tmp_path)).read("policy") == {}


def test_problems_reports_a_file_that_cannot_be_read_instead_of_raising(tmp_path):
    _write(tmp_path, "vocabulary", {})
    (tmp_path / "policy.json").write_text("{not json", encoding="utf-8")
    problems = ConfigReader(str(tmp_path)).problems()
    assert len(problems) == 1 and "could not be read" in problems[0]


def test_problems_names_every_missing_setting(tmp_path):
    _write(tmp_path, "vocabulary", {"signal_codes": {"A": "a"}})
    _write(tmp_path, "policy", {"policy_version": "1"})
    problems = ConfigReader(str(tmp_path)).problems()
    assert "config/vocabulary.json is missing 'document_codes'" in problems
    assert "config/policy.json is missing 'routing'" in problems
    assert "config/vocabulary.json is missing 'signal_codes'" not in problems


def test_a_rate_limit_setting_that_cannot_be_right_is_reported(tmp_path):
    """CLAUDE.md §9: config is validated. A cooldown that is text, a fraction or negative, or an
    'enabled' that is not true/false, is reported instead of crashing the app later."""
    import shutil
    folder = tmp_path / "config"
    shutil.copytree("config", folder)
    policy = json.loads((folder / "policy.json").read_text())
    policy["assessment_rate_limit"] = {"enabled": "yes", "cooldown_seconds": "60"}
    (folder / "policy.json").write_text(json.dumps(policy))
    problems = ConfigReader(str(folder)).problems()
    assert any("cooldown_seconds" in p and "'60'" in p for p in problems)
    assert any("enabled" in p and "'yes'" in p for p in problems)
