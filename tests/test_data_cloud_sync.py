"""CloudSync: only new and changed records are sent. No real database is used."""

from app.data.assessment_repository import AssessmentRepository
from app.data.client_repository import ClientRepository
from app.data.cloud_sync import CloudSync
from tests.fake_database import FakeDatabase


def _sync(tmp_path, remote=None):
    local = ClientRepository(str(tmp_path / "sow_cases.json"))
    remote = remote or FakeDatabase()
    return local, remote, CloudSync(local, remote, str(tmp_path / "sync_state.json"))


def test_new_records_are_sent(tmp_path):
    local, remote, sync = _sync(tmp_path)
    local.save({"client_ref": "SOW-1", "name": "Daniel Tan"})
    local.save({"client_ref": "SOW-2", "name": "Marcus Lim"})
    assert sync.sync() == {"synced": 2, "skipped": 0, "errors": []}
    assert sorted(remote.records) == ["SOW-1", "SOW-2"]


def test_unchanged_records_are_skipped_the_next_time(tmp_path):
    local, remote, sync = _sync(tmp_path)
    local.save({"client_ref": "SOW-1", "name": "Daniel Tan"})
    sync.sync()
    assert sync.sync() == {"synced": 0, "skipped": 1, "errors": []}


def test_a_changed_record_is_sent_again(tmp_path):
    local, remote, sync = _sync(tmp_path)
    local.save({"client_ref": "SOW-1", "name": "Daniel Tan"})
    sync.sync()
    local.save({"client_ref": "SOW-1", "name": "Daniel Tan Wei Ming"})
    assert sync.sync()["synced"] == 1
    assert remote.records["SOW-1"]["name"] == "Daniel Tan Wei Ming"


def test_an_offline_database_sends_nothing_and_says_why(tmp_path):
    local, remote, sync = _sync(tmp_path, FakeDatabase(online=False))
    local.save({"client_ref": "SOW-1"})
    result = sync.sync()
    assert result["synced"] == 0
    assert "Cannot reach the cloud database" in result["errors"][0]
    assert remote.records == {}


def test_a_record_that_fails_is_reported_and_tried_again_next_time(tmp_path):
    local, remote, sync = _sync(tmp_path)
    local.save({"client_ref": "SOW-1"})
    local.save({"client_ref": "SOW-2"})
    remote.fail_on.add("SOW-2")
    result = sync.sync()
    assert result["synced"] == 1
    assert result["errors"] == ["SOW-2: could not be sent to the cloud database."]
    remote.fail_on.clear()
    assert sync.sync() == {"synced": 1, "skipped": 1, "errors": []}


def test_local_documents_are_uploaded_and_their_ids_saved_locally(tmp_path):
    payslip = tmp_path / "payslip.txt"
    payslip.write_text("Basic salary 5,000", encoding="utf-8")
    local, remote, sync = _sync(tmp_path)
    local.save({"client_ref": "SOW-1", "supporting_documents": [
        {"file_name": "payslip.txt", "file_path": str(payslip)}]})
    sync.sync()
    assert remote.files == ["payslip.txt"]
    assert local.find("SOW-1")["supporting_documents"][0]["file_id"] == "file-1"
    assert sync.sync()["skipped"] == 1


def test_two_syncs_can_share_one_state_file(tmp_path):
    state = str(tmp_path / "sync_state.json")
    clients = ClientRepository(str(tmp_path / "sow_cases.json"))
    assessments = AssessmentRepository(str(tmp_path / "ai_assessments.json"))
    clients.save({"client_ref": "SOW-1"})
    assessments.save({"client_ref": "SOW-1", "assessment_id": "A-1", "outcome": "PASSED"})
    client_sync = CloudSync(clients, FakeDatabase("client_cases", "client_ref"), state)
    assessment_sync = CloudSync(assessments, FakeDatabase("ai_assessments", "assessment_id"), state)
    assert client_sync.sync()["synced"] == 1
    assert assessment_sync.sync()["synced"] == 1
    assert client_sync.sync()["skipped"] == 1
    assert assessment_sync.sync()["skipped"] == 1


def test_a_damaged_state_file_means_everything_is_sent_again(tmp_path):
    local, remote, sync = _sync(tmp_path)
    local.save({"client_ref": "SOW-1"})
    sync.sync()
    (tmp_path / "sync_state.json").write_text("{broken", encoding="utf-8")
    assert sync.sync()["synced"] == 1
