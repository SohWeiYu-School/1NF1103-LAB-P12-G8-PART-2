"""The app reads clients, assessments and documents from the local files only.
MongoDB is a backup that Manual Sync writes to; nothing is ever read back from it."""

import json

import pytest

from app.application.app import App
from app.data.document_store import DocumentStore
from app.data.mongo_repository import MongoRepository


@pytest.fixture
def local_db(tmp_path, monkeypatch):
    """An App with an empty local database in a temporary folder, and MongoDB that fails the test if used."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))

    def no_mongo(*args, **kwargs):
        raise AssertionError("MongoDB was read")
    monkeypatch.setattr(MongoRepository, "_connect", no_mongo)
    application = App(None, data_folder=str(tmp_path / "data"))
    db = tmp_path / "data" / "local database"
    db.mkdir(parents=True)
    return application, db


def test_deleted_local_database_means_no_clients(local_db):
    application, _ = local_db
    assert application.clients().load() == []
    assert application.clients().find("SOW-2026-0001") is None
    assert application.assessments().load() == []


def test_clients_and_assessments_come_from_the_local_files(local_db):
    application, db = local_db
    (db / "sow_cases.json").write_text(json.dumps([{"client_ref": "SOW-2026-0001", "full_name": "A"}]))
    (db / "ai_assessments.json").write_text(json.dumps([{"client_ref": "SOW-2026-0001", "outcome": "PASSED"}]))
    assert [r["client_ref"] for r in application.clients().load()] == ["SOW-2026-0001"]
    assert application.clients().find("sow-2026-0001")["full_name"] == "A"
    assert len(application.assessments().load()) == 1


def test_documents_are_copied_from_the_local_copy_only(tmp_path):
    store = DocumentStore("data", root=str(tmp_path))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "payslip.txt").write_text("Basic salary 5,000")
    out = tmp_path / "out" / "payslip.txt"
    assert store.download("data/payslip.txt", str(out))
    assert out.read_text() == "Basic salary 5,000"
    # an id that only exists in MongoDB (after a sync) is not fetched from the cloud
    assert not store.download("652f1c2e9b1e8a3f4c5d6e7f", str(tmp_path / "x.txt"))


def test_synced_document_is_read_from_its_local_path(tmp_path):
    store = DocumentStore("data", root=str(tmp_path))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "letter.txt").write_text("Employment letter")
    entry = {"file_name": "letter.txt", "file_path": "data/letter.txt", "file_id": "652f1c2e9b1e8a3f4c5d6e7f"}
    read = store.read_all([entry])
    assert read[0]["kind"] == "text" and "Employment letter" in read[0]["text"]
