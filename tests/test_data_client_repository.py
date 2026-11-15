"""ClientRepository: one record per client, always in the current layout."""

import json

import pytest

from app.data.client_repository import ClientRepository


def _repository(tmp_path):
    return ClientRepository(str(tmp_path / "sow_cases.json"))


def test_saving_a_new_client_adds_it(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"client_ref": "SOW-1", "name": "Daniel Tan"})
    assert repository.save({"client_ref": "SOW-2", "name": "Marcus Lim"})
    assert [record["client_ref"] for record in repository.load()] == ["SOW-1", "SOW-2"]


def test_saving_the_same_client_again_replaces_the_record(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "name": "Daniel Tan"})
    repository.save({"client_ref": "SOW-1", "name": "Daniel Tan Wei Ming"})
    assert repository.load() == [{"client_ref": "SOW-1", "name": "Daniel Tan Wei Ming"}]


def test_a_record_with_no_client_reference_is_not_saved(tmp_path):
    repository = _repository(tmp_path)
    assert repository.save({"name": "No reference"}) is False
    assert repository.save("not a record") is False
    assert repository.load() == []


def test_find_returns_one_client_whatever_the_letter_case(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "name": "Daniel Tan"})
    assert repository.find("sow-1")["name"] == "Daniel Tan"
    assert repository.find("SOW-9") is None


def test_old_asset_names_are_renamed_when_saving(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "investments": [
        {"asset_type": "Property", "asset_description": "Condo", "current_value": 900000, "yearly_income": 12000}]})
    asset = repository.find("SOW-1")["investments"][0]
    assert asset == {"asset_type": "Property - Condo", "current_declared_value": 900000, "income_produced": 12000}


def test_a_record_saved_in_the_old_layout_is_read_in_the_current_one(tmp_path):
    path = tmp_path / "sow_cases.json"
    path.write_text(json.dumps([{"client_ref": "SOW-1", "investments": [
        {"asset_type": "Shares", "current_value": 5000}]}]), encoding="utf-8")
    asset = ClientRepository(str(path)).load()[0]["investments"][0]
    assert asset == {"asset_type": "Shares", "current_declared_value": 5000}


def test_a_description_already_in_the_asset_type_is_not_added_twice(tmp_path):
    repository = _repository(tmp_path)
    repository.save({"client_ref": "SOW-1", "investments": [
        {"asset_type": "Property - Condo", "description": "condo"}]})
    assert repository.find("SOW-1")["investments"][0]["asset_type"] == "Property - Condo"


def test_old_command_line_records_are_upgraded_when_loaded(tmp_path):
    path = tmp_path / "sow_cases.json"
    path.write_text(json.dumps([{"client_ref": "CL-OLD", "investments": [
        {"asset_type": "Property", "asset_description": "Condo", "current_value": 1500000,
         "yearly_income": 36000, "price_paid": 900000}]}]), encoding="utf-8")

    asset = ClientRepository(str(path)).find("CL-OLD")["investments"][0]

    assert asset == {"asset_type": "Property - Condo", "price_paid": 900000,
                     "current_declared_value": 1500000, "income_produced": 36000}


def test_a_damaged_file_is_not_overwritten_by_a_save(tmp_path):
    path = tmp_path / "sow_cases.json"
    path.write_bytes(b'[{"client_ref": "SOW-1", broken')
    before = path.read_bytes()
    assert _repository(tmp_path).save({"client_ref": "SOW-2"}) is False
    assert path.read_bytes() == before


def test_load_and_find_raise_when_the_file_is_damaged(tmp_path):
    (tmp_path / "sow_cases.json").write_text("not json", encoding="utf-8")
    repository = _repository(tmp_path)
    with pytest.raises(ValueError):
        repository.load()
    with pytest.raises(ValueError):
        repository.find("SOW-1")


def test_a_file_that_cannot_be_read_stops_load_and_save(tmp_path):
    (tmp_path / "sow_cases.json").mkdir()                    # a folder where the file should be
    repository = _repository(tmp_path)
    with pytest.raises(OSError):
        repository.load()
    assert repository.save({"client_ref": "SOW-1"}) is False


def test_a_record_with_the_wrong_shape_is_reported_as_a_damaged_file(tmp_path):
    path = tmp_path / "sow_cases.json"
    path.write_text('[{"client_ref": "CL-1", "investments": 5}]', encoding="utf-8")
    with pytest.raises(ValueError, match="damaged"):
        _repository(tmp_path).load()
