"""ConfigReader: the settings files, including a missing or damaged one."""

import json

import pytest

from app.data.config_reader import ConfigReader


def _write(folder, name, data):
    (folder / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


def test_the_real_config_folder_has_no_problems():
    assert ConfigReader().problems() == []


def test_file_names_lists_the_policy_the_vocabulary_then_the_accounts_and_each_has_required_keys():
    assert ConfigReader.FILE_NAMES == ("policy", "vocabulary", "accounts")
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
    _write(tmp_path, "accounts", {"accounts": []})
    (tmp_path / "policy.json").write_text("{not json", encoding="utf-8")
    problems = ConfigReader(str(tmp_path)).problems()
    assert problems == ["config/policy.json could not be read (see the log)."]    # no path, no Errno, no JSON error


def test_problems_names_a_missing_file_without_technical_details(tmp_path):
    problems = ConfigReader(str(tmp_path)).problems()
    assert problems == ["config/vocabulary.json could not be read (see the log)."]
    assert str(tmp_path) not in problems[0] and "Errno" not in problems[0]


def test_problems_names_every_missing_setting(tmp_path):
    _write(tmp_path, "vocabulary", {"signal_codes": {"A": "a"}})
    _write(tmp_path, "policy", {"policy_version": "1"})
    _write(tmp_path, "accounts", {"accounts": [ADMIN, OFFICER]})
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


def test_a_rate_limit_with_no_cooldown_is_not_a_problem(tmp_path):
    import shutil
    folder = tmp_path / "config"
    shutil.copytree("config", folder)
    policy = json.loads((folder / "policy.json").read_text())
    policy["assessment_rate_limit"] = {"enabled": True}
    (folder / "policy.json").write_text(json.dumps(policy))
    assert not any("cooldown_seconds" in p for p in ConfigReader(str(folder)).problems())


ADMIN = {"email": "admin@orbit.local", "name": "Orbit Admin", "role": "admin"}
OFFICER = {"email": "shareen@orbit.local", "name": "Shareen", "role": "officer"}


def _config_with_accounts(tmp_path, accounts):
    import shutil
    folder = tmp_path / "config"
    shutil.copytree("config", folder)
    if accounts is not None:
        (folder / "accounts.json").write_text(json.dumps({"accounts": accounts}))
    return ConfigReader(str(folder))


def test_the_real_accounts_file_has_one_admin_and_officers():
    reader = ConfigReader()
    roles = [entry["role"] for entry in reader.read("accounts")["accounts"]]
    assert roles.count("admin") == 1 and roles.count("officer") == 5


def test_problems_names_an_accounts_file_that_cannot_be_read_without_details(tmp_path):
    reader = _config_with_accounts(tmp_path, None)
    (tmp_path / "config" / "accounts.json").write_text("{broken")
    assert reader.problems() == ["config/accounts.json could not be read (see the log)."]


def test_problems_names_a_missing_accounts_file(tmp_path):
    reader = _config_with_accounts(tmp_path, None)
    (tmp_path / "config" / "accounts.json").unlink()
    assert reader.problems() == ["config/accounts.json could not be read (see the log)."]


@pytest.mark.parametrize("accounts", [[], "text", 5, {}])
def test_accounts_must_be_a_non_empty_list(tmp_path, accounts):
    problems = _config_with_accounts(tmp_path, accounts).problems()
    assert any("must be a list with at least one account" in p for p in problems)


def test_a_bad_account_is_named_by_its_number_and_reason(tmp_path):
    problems = _config_with_accounts(tmp_path, [ADMIN, {**OFFICER, "email": "nope"}]).problems()
    assert len(problems) == 1 and "account 2" in problems[0] and "email" in problems[0]


def test_an_account_that_is_not_an_object_is_reported(tmp_path):
    problems = _config_with_accounts(tmp_path, [ADMIN, OFFICER, "Shareen"]).problems()
    assert any("account 3" in p for p in problems)


def test_a_repeated_email_or_name_is_reported(tmp_path):
    other = {"email": "shareen@orbit.local", "name": "Other Name", "role": "officer"}
    same_name = {"email": "x@orbit.local", "name": "shareen", "role": "officer"}
    problems = _config_with_accounts(tmp_path, [ADMIN, OFFICER, other, same_name]).problems()
    assert any("same email" in p and "shareen@orbit.local" in p for p in problems)
    assert any("same name" in p for p in problems)


def test_there_must_be_exactly_one_admin_and_at_least_one_officer(tmp_path):
    two_admins = _config_with_accounts(tmp_path, [ADMIN, {**OFFICER, "role": "admin"}, OFFICER,
                                                  {**OFFICER, "email": "b@orbit.local", "name": "Bee"}]).problems()
    assert any("exactly one admin" in p for p in two_admins)
    folder2 = tmp_path / "second"
    folder2.mkdir()
    no_officer = _config_with_accounts(folder2, [ADMIN]).problems()
    assert any("at least one officer" in p for p in no_officer)
    folder3 = tmp_path / "third"
    folder3.mkdir()
    no_admin = _config_with_accounts(folder3, [OFFICER]).problems()
    assert any("exactly one admin" in p and "found 0" in p for p in no_admin)
