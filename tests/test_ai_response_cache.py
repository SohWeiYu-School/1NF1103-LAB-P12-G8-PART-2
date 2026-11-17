"""ResponseCache: one saved-replies file per client, including missing and damaged files."""

import os

from app.ai.response_cache import ResponseCache


# ----- one saved-replies file per client -------------------------------------------------------

CASE = {"client_ref": "SOW-1", "name": "Tan Ah Kow", "current_date": "2026-01-01",
        "career": [{"employer": "Acme", "start_year": 2010}], "claims": {"amount": 1000},
        "sow_declaration": "I saved my salary."}
DOCUMENTS = [{"file_name": "a.pdf", "kind": "text", "text": "payslip"},
             {"file_name": "b.png", "kind": "image", "data_b64": "AAAA"}]
REPLIES = {"research": {"question": "q1", "reply": {"a": 1}}, "forecast": {"step0_declaration": "raw"}}


def test_no_client_file_gives_no_replies(tmp_path):
    assert ResponseCache(str(tmp_path)).load_client_replies("SOW-1", "f") == {}


def test_saved_replies_come_back_for_the_same_fingerprint(tmp_path):
    cache = ResponseCache(str(tmp_path))
    assert cache.save_client_replies("SOW-1", "f", REPLIES) is True
    assert os.path.isfile(tmp_path / "clients" / "SOW-1.json")
    assert cache.load_client_replies("SOW-1", "f") == REPLIES
    assert cache.load_client_replies("SOW-2", "f") == {}


def test_a_different_fingerprint_gives_no_replies(tmp_path):
    cache = ResponseCache(str(tmp_path))
    cache.save_client_replies("SOW-1", "f", REPLIES)
    assert cache.load_client_replies("SOW-1", "other") == {}


def test_saving_again_replaces_the_earlier_file(tmp_path):
    cache = ResponseCache(str(tmp_path))
    cache.save_client_replies("SOW-1", "f", REPLIES)
    cache.save_client_replies("SOW-1", "g", {"research": {"question": "q2", "reply": {}}})
    assert cache.load_client_replies("SOW-1", "f") == {}
    assert cache.load_client_replies("SOW-1", "g") == {"research": {"question": "q2", "reply": {}}}


def test_a_damaged_client_file_gives_no_replies_and_a_warning(tmp_path, caplog):
    cache = ResponseCache(str(tmp_path))
    os.makedirs(tmp_path / "clients")
    (tmp_path / "clients" / "SOW-1.json").write_text("{not json", encoding="utf-8")
    with caplog.at_level("WARNING"):
        assert cache.load_client_replies("SOW-1", "f") == {}
    assert "SOW-1.json" in caplog.text


def test_a_client_file_with_the_wrong_layout_gives_no_replies(tmp_path, caplog):
    cache = ResponseCache(str(tmp_path))
    os.makedirs(tmp_path / "clients")
    for content in ('["a"]', '{"fingerprint": "f"}', '{"fingerprint": "f", "replies": []}',
                    '{"fingerprint": 1, "replies": {}}'):
        (tmp_path / "clients" / "SOW-1.json").write_text(content, encoding="utf-8")
        with caplog.at_level("WARNING"):
            assert cache.load_client_replies("SOW-1", "f") == {}


def test_a_bad_client_ref_is_rejected(tmp_path):
    cache = ResponseCache(str(tmp_path))
    for ref in ("../x", "a/b", "", "a b", "x.json"):
        for call in (lambda r=ref: cache.load_client_replies(r, "f"),
                     lambda r=ref: cache.save_client_replies(r, "f", {})):
            try:
                call()
            except ValueError as error:
                assert "client_ref" in str(error)
            else:
                raise AssertionError(f"{ref!r} was accepted")


def test_saving_leaves_no_temporary_file(tmp_path):
    cache = ResponseCache(str(tmp_path))
    cache.save_client_replies("SOW-1", "f", REPLIES)
    assert os.listdir(tmp_path / "clients") == ["SOW-1.json"]


def test_a_save_that_fails_gives_false_and_a_warning(tmp_path, caplog):
    blocker = tmp_path / "blocked"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    cache = ResponseCache(str(blocker))
    with caplog.at_level("WARNING"):
        assert cache.save_client_replies("SOW-1", "f", REPLIES) is False
    assert "could not write" in caplog.text


def test_the_fingerprint_ignores_key_order_and_the_run_date(tmp_path):
    cache = ResponseCache(str(tmp_path))
    base = cache.fingerprint(CASE, DOCUMENTS)
    assert base == cache.fingerprint(dict(reversed(list(CASE.items()))), DOCUMENTS)
    assert base == cache.fingerprint({**CASE, "current_date": "2030-05-05"}, DOCUMENTS)


def test_the_fingerprint_changes_when_the_client_changes(tmp_path):
    cache = ResponseCache(str(tmp_path))
    base = cache.fingerprint(CASE, DOCUMENTS)
    changed = [
        {**CASE, "name": "Tan Ah Kowe"},
        {**CASE, "sow_declaration": "I saved my salary!"},
        {**CASE, "career": [{"employer": "Acme", "start_year": 2011}]},
        {**CASE, "claims": {"amount": 1001}},
    ]
    for case in changed:
        assert cache.fingerprint(case, DOCUMENTS) != base


def test_the_fingerprint_changes_when_the_documents_change(tmp_path):
    cache = ResponseCache(str(tmp_path))
    base = cache.fingerprint(CASE, DOCUMENTS)
    assert cache.fingerprint(CASE, [{**DOCUMENTS[0], "text": "payslip!"}, DOCUMENTS[1]]) != base
    assert cache.fingerprint(CASE, [{**DOCUMENTS[0], "file_name": "c.pdf"}, DOCUMENTS[1]]) != base
    assert cache.fingerprint(CASE, DOCUMENTS + [{"file_name": "z.txt", "kind": "text", "text": "x"}]) != base
    assert cache.fingerprint(CASE, DOCUMENTS[:1]) != base
    assert cache.fingerprint(CASE, []) != base
    error = {"file_name": "a.pdf", "kind": "error", "error": "could not be read"}
    assert cache.fingerprint(CASE, [error, DOCUMENTS[1]]) != base


def test_saves_of_the_same_client_at_the_same_time_each_use_their_own_temporary_file(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    cache = ResponseCache(str(tmp_path))

    def save(number):
        return [cache.save_client_replies("SOW-1", f"f{number}", {"n": {"reply": {"a": number}}})
                for _ in range(40)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [ok for outcome in pool.map(save, range(8)) for ok in outcome]
    assert all(results)
    assert os.listdir(tmp_path / "clients") == ["SOW-1.json"]
    fingerprint = next(number for number in range(8) if cache.load_client_replies("SOW-1", f"f{number}"))
    assert cache.load_client_replies("SOW-1", f"f{fingerprint}") == {"n": {"reply": {"a": fingerprint}}}
