"""DatabaseRepository and MongoRepository. No real database is used."""

import pytest

from app.data import mongo_repository
from app.data.database_repository import DatabaseRepository
from app.data.mongo_repository import MongoRepository
from app.data.repository import Repository
from tests.fake_database import FakeDatabase


def test_the_abstract_parent_cannot_be_created():
    with pytest.raises(TypeError):
        DatabaseRepository("client_cases", "client_ref", "uri")


def test_a_database_repository_is_a_repository_like_the_json_ones():
    assert isinstance(FakeDatabase(), Repository)
    assert issubclass(MongoRepository, DatabaseRepository)


def test_save_load_and_find_use_the_same_names_as_every_repository():
    database = FakeDatabase()
    assert database.save({"client_ref": "SOW-1", "name": "Daniel Tan"})
    assert database.save({"client_ref": "SOW-1", "name": "Daniel Tan Wei Ming"})
    assert database.load() == [{"client_ref": "SOW-1", "name": "Daniel Tan Wei Ming"}]
    assert database.find("SOW-1")["name"] == "Daniel Tan Wei Ming"
    assert database.find("SOW-9") is None


def test_an_offline_database_fails_safely():
    database = FakeDatabase(online=False)
    assert database.is_online() is False
    assert database.save({"client_ref": "SOW-1"}) is False
    assert database.load() == []
    assert database.find("SOW-1") is None
    assert database.upload_local_documents({"supporting_documents": [{"file_path": "x.pdf"}]}) == 0


def test_only_documents_that_exist_locally_and_have_no_id_are_uploaded(tmp_path):
    payslip = tmp_path / "payslip.txt"
    payslip.write_text("Basic salary 5,000", encoding="utf-8")
    record = {"client_ref": "SOW-1", "supporting_documents": [
        {"file_name": "payslip.txt", "file_path": str(payslip)},
        {"file_name": "old.txt", "file_path": str(payslip), "file_id": "already-there"},
        {"file_name": "gone.txt", "file_path": str(tmp_path / "gone.txt")},
        {"file_name": "no-path.txt"}]}
    database = FakeDatabase()
    assert database.upload_local_documents(record) == 1
    assert database.files == ["payslip.txt"]
    assert record["supporting_documents"][0]["file_id"] == "file-1"
    assert "file_id" not in record["supporting_documents"][2]


def test_mongo_with_no_address_is_offline():
    repository = MongoRepository("client_cases", "client_ref", "")
    assert repository.is_online() is False
    assert repository.save({"client_ref": "SOW-1"}) is False


def test_mongo_that_cannot_be_reached_is_offline(monkeypatch):
    def unreachable(*args, **kwargs):
        raise ConnectionError("no network")
    monkeypatch.setattr(mongo_repository, "MongoClient", unreachable)
    repository = MongoRepository("client_cases", "client_ref", "mongodb://nowhere")
    assert repository.is_online() is False
    assert repository.load() == []


class _Collection:
    def __init__(self):
        self.writes = []

    def update_one(self, query, change, upsert=False):
        self.writes.append((query, change["$set"], upsert))

    def find(self, query, fields):
        return [{"client_ref": "SOW-1"}]


class _Client:
    def __init__(self, *args, **kwargs):
        self.collection = _Collection()
        self.admin = self

    def command(self, name):
        return {"ok": 1}

    def __getitem__(self, name):
        return {"client_cases": self.collection, "ai_assessments": self.collection}


def test_mongo_writes_one_record_per_key(monkeypatch):
    client = _Client()
    monkeypatch.setattr(mongo_repository, "MongoClient", lambda *args, **kwargs: client)
    repository = MongoRepository("client_cases", "client_ref", "mongodb://test")
    assert repository.save({"client_ref": "SOW-1", "name": "Daniel Tan"})
    assert client.collection.writes == [({"client_ref": "SOW-1"}, {"client_ref": "SOW-1", "name": "Daniel Tan"}, True)]
    assert repository.load() == [{"client_ref": "SOW-1"}]


def test_an_old_assessment_with_no_id_is_matched_on_client_and_time(monkeypatch):
    client = _Client()
    monkeypatch.setattr(mongo_repository, "MongoClient", lambda *args, **kwargs: client)
    repository = MongoRepository("ai_assessments", "assessment_id", "mongodb://test")
    repository.save({"client_ref": "SOW-1", "assessed_at": "2026-01-10"})
    assert client.collection.writes[0][0] == {"client_ref": "SOW-1", "assessed_at": "2026-01-10"}
