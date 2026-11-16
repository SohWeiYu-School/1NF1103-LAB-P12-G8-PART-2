"""AuditRepository: append-only chaining, refusals, damaged files and concurrent saves."""

import json
import logging
import threading

from app.data.audit_repository import AuditRepository
from app.model.audit_event import AuditEvent


def _record(action="client_edited", ref="C-0007", actor="Shareen", **more) -> dict:
    return {"actor": actor, "action": action, "client_ref": ref, **more}


def _repo(tmp_path) -> AuditRepository:
    return AuditRepository(str(tmp_path / "audit_log.json"))


def _rows(tmp_path) -> list[dict]:
    return json.loads((tmp_path / "audit_log.json").read_text(encoding="utf-8"))


def test_the_first_event_is_sequence_1_chained_to_genesis(tmp_path):
    repo = _repo(tmp_path)
    assert repo.save(_record()) is True
    row = _rows(tmp_path)[0]
    assert row["sequence"] == 1 and row["previous_hash"] == AuditEvent.GENESIS
    assert AuditEvent.from_dict(row).hash_matches()


def test_each_event_is_chained_to_the_one_before(tmp_path):
    repo = _repo(tmp_path)
    for action in ("signed_in", "client_created", "client_edited"):
        assert repo.save(_record(action)) is True
    rows = _rows(tmp_path)
    assert [r["sequence"] for r in rows] == [1, 2, 3]
    assert rows[0]["previous_hash"] == AuditEvent.GENESIS
    assert rows[1]["previous_hash"] == rows[0]["hash"] and rows[2]["previous_hash"] == rows[1]["hash"]
    assert all(AuditEvent.from_dict(r).hash_matches() for r in rows)


def test_a_sealed_record_is_sealed_again_in_its_real_place(tmp_path):
    other = AuditEvent(action="signed_in")
    other.seal(99, "a" * 64)
    repo = _repo(tmp_path)
    repo.save(other.to_dict())
    assert _rows(tmp_path)[0]["sequence"] == 1 and _rows(tmp_path)[0]["previous_hash"] == AuditEvent.GENESIS


def test_a_bad_record_is_refused_logged_and_nothing_is_written(tmp_path, caplog):
    repo = _repo(tmp_path)
    repo.save(_record())
    before = (tmp_path / "audit_log.json").read_text(encoding="utf-8")
    for bad in (None, "text", {}, {"action": "deleted_everything"}, _record(result="maybe"),
                _record(details={"x": object()})):
        assert repo.save(bad) is False
    assert (tmp_path / "audit_log.json").read_text(encoding="utf-8") == before
    assert "not valid" in caplog.text


def test_an_unreadable_file_means_not_saved_and_the_file_is_left_as_it_was(tmp_path, caplog):
    path = tmp_path / "audit_log.json"
    path.write_text("{broken", encoding="utf-8")
    assert _repo(tmp_path).save(_record()) is False
    assert path.read_text(encoding="utf-8") == "{broken"
    assert "cannot be read" in caplog.text


def test_a_file_that_is_not_a_list_of_records_is_not_overwritten(tmp_path):
    path = tmp_path / "audit_log.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    assert _repo(tmp_path).save(_record()) is False and path.read_text(encoding="utf-8") == '{"a": 1}'


def test_a_damaged_last_row_still_lets_the_event_be_added_with_genesis_and_a_warning(tmp_path, caplog):
    repo = _repo(tmp_path)
    repo.save(_record())
    repo.save(_record("signed_in"))
    rows = _rows(tmp_path)
    rows[-1]["hash"] = "not a hash"
    (tmp_path / "audit_log.json").write_text(json.dumps(rows), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert repo.save(_record("signed_out")) is True
    last = _rows(tmp_path)[-1]
    assert last["previous_hash"] == AuditEvent.GENESIS and last["sequence"] == 3
    assert "no valid hash" in caplog.text


def test_a_last_row_with_no_sequence_numbers_the_next_one_by_count(tmp_path):
    (tmp_path / "audit_log.json").write_text(json.dumps([{"junk": 1}, {"junk": 2}]), encoding="utf-8")
    assert _repo(tmp_path).save(_record()) is True
    assert _rows(tmp_path)[-1]["sequence"] == 3 and len(_rows(tmp_path)) == 3


def test_a_missing_file_is_an_empty_log_and_is_created(tmp_path):
    assert not (tmp_path / "audit_log.json").exists()
    assert _repo(tmp_path).save(_record()) is True and len(_rows(tmp_path)) == 1


def test_a_write_that_fails_returns_false(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setattr(AuditRepository, "_write_all", lambda self, records: False)
    assert repo.save(_record()) is False


def test_there_is_no_way_to_replace_update_or_delete_an_event():
    for name in ("replace", "update", "delete", "remove", "archive", "restore"):
        assert not hasattr(AuditRepository, name)


def test_for_client_gives_that_clients_events_oldest_first_ignoring_case(tmp_path):
    repo = _repo(tmp_path)
    repo.save(_record("client_created", "C-0007"))
    repo.save(_record("client_created", "C-0008"))
    repo.save(_record("client_edited", "c-0007"))
    found = repo.for_client(" C-0007 ")
    assert [r["action"] for r in found] == ["client_created", "client_edited"]
    assert [r["sequence"] for r in found] == [1, 3]
    assert repo.for_client("C-9999") == [] and repo.for_client("") == []


def test_for_client_on_a_missing_file_is_empty_but_on_a_damaged_file_it_raises(tmp_path):
    import pytest
    repo = _repo(tmp_path)
    assert repo.for_client("C-1") == []
    (tmp_path / "audit_log.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        repo.for_client("C-1")


def test_two_threads_saving_twenty_events_each_keep_the_chain_valid(tmp_path):
    repo = _repo(tmp_path)
    results: list[bool] = []

    def work(actor: str) -> None:
        for _ in range(20):
            results.append(repo.save(_record("signed_in", "", actor)))

    threads = [threading.Thread(target=work, args=(name,)) for name in ("Shareen", "Adrian")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    rows = _rows(tmp_path)
    assert all(results) and len(rows) == 40
    assert [r["sequence"] for r in rows] == list(range(1, 41))
    assert rows[0]["previous_hash"] == AuditEvent.GENESIS
    for before, row in zip(rows, rows[1:]):
        assert row["previous_hash"] == before["hash"]
    assert all(AuditEvent.from_dict(r).hash_matches() for r in rows)


def test_a_surrogate_in_the_record_is_refused_not_crashed(tmp_path, caplog):
    repo = _repo(tmp_path)
    assert repo.save(_record(details={"x": "\ud800"})) is False
    assert repo.save(_record(actor="a\ud800")) is False
    assert not (tmp_path / "audit_log.json").exists()


def test_a_seal_that_fails_returns_false_logs_the_details_and_writes_nothing(tmp_path, monkeypatch, caplog):
    repo = _repo(tmp_path)
    repo.save(_record())
    before = (tmp_path / "audit_log.json").read_text(encoding="utf-8")

    def broken(self, sequence, previous_hash):
        raise ValueError("seal went wrong")

    monkeypatch.setattr(AuditEvent, "seal", broken)
    assert repo.save(_record("signed_in")) is False
    assert (tmp_path / "audit_log.json").read_text(encoding="utf-8") == before
    assert "ValueError('seal went wrong')" in caplog.text


def _save_many(path: str, actor: str, count: int, results) -> None:
    """Run in a separate OS process: its own repository on the shared file."""
    repo = AuditRepository(path)
    for _ in range(count):
        results.put(repo.save(_record("signed_in", "", actor)))


def test_two_processes_saving_twenty_five_events_each_lose_none_and_keep_the_chain(tmp_path):
    import multiprocessing
    from app.logic.audit_chain import AuditChain
    path = str(tmp_path / "audit_log.json")
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    processes = [context.Process(target=_save_many, args=(path, name, 25, results))
                 for name in ("Shareen", "Adrian")]
    for process in processes:
        process.start()
    outcomes = [results.get(timeout=120) for _ in range(50)]
    for process in processes:
        process.join(timeout=120)
        assert process.exitcode == 0
    rows = _rows(tmp_path)
    assert all(outcomes) and len(rows) == 50
    assert [r["sequence"] for r in rows] == list(range(1, 51))
    chain = AuditChain(rows)
    assert chain.intact() and chain.breaks() == [] and chain.unreadable_count() == 0


def test_a_lock_file_that_cannot_be_opened_means_not_saved_and_the_log_is_unchanged(tmp_path, caplog):
    repo = _repo(tmp_path)
    assert repo.save(_record()) is True
    before = (tmp_path / "audit_log.json").read_bytes()
    (tmp_path / "audit_log.json.lock").unlink()
    (tmp_path / "audit_log.json.lock").mkdir()      # a folder where the lock file should be
    with caplog.at_level(logging.ERROR):
        assert repo.save(_record("signed_in")) is False
    assert (tmp_path / "audit_log.json").read_bytes() == before
    assert "lock file" in caplog.text
