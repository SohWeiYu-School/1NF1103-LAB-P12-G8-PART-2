"""ResponseCache: saved AI replies, including missing and damaged files."""

import json
import os

from app.ai.response_cache import ResponseCache

PAYLOAD = {"industry": "shipping"}


def test_nothing_saved_gives_none(tmp_path):
    assert ResponseCache(str(tmp_path)).get("typology", PAYLOAD, "gpt-4o") is None


def test_a_saved_answer_is_found_by_the_same_question(tmp_path):
    cache = ResponseCache(str(tmp_path))
    cache.put("typology", cache.key("typology", PAYLOAD, "gpt-4o", "v1"), {"sector_typologies": []})
    found = cache.get("typology", PAYLOAD, "gpt-4o", "v1")
    assert found["sector_typologies"] == []
    assert os.path.isfile(found["_cache_path"])


def test_a_different_payload_model_or_prompt_version_is_a_different_question(tmp_path):
    cache = ResponseCache(str(tmp_path))
    key = cache.key("typology", PAYLOAD, "gpt-4o", "v1")
    assert key == cache.key("typology", dict(PAYLOAD), "gpt-4o", "v1")
    assert key != cache.key("typology", {"industry": "banking"}, "gpt-4o", "v1")
    assert key != cache.key("typology", PAYLOAD, "gpt-4o-mini", "v1")
    assert key != cache.key("typology", PAYLOAD, "gpt-4o", "v2")
    assert key != cache.key("research", PAYLOAD, "gpt-4o", "v1")


def test_a_damaged_saved_answer_is_treated_as_not_saved(tmp_path):
    cache = ResponseCache(str(tmp_path))
    key = cache.key("typology", PAYLOAD, "gpt-4o")
    cache.put("typology", key, {"ok": True})
    with open(cache.path_for("typology", key), "w", encoding="utf-8") as handle:
        handle.write("{broken")
    assert cache.get("typology", PAYLOAD, "gpt-4o") is None


def test_put_leaves_no_temporary_file_behind(tmp_path):
    cache = ResponseCache(str(tmp_path))
    cache.put("benchmark", "abc", {"expected_wealth": 1})
    assert os.listdir(tmp_path / "benchmark") == ["abc.json"]


def test_raw_replies_are_kept_per_client(tmp_path):
    cache = ResponseCache(str(tmp_path))
    assert cache.load_raw_replies("SOW-1") == {}
    saved = cache.save_raw_replies("SOW-1", {"step0_declaration": {"raw": '{"a": 1}', "ok": True},
                                             "call1_markets": {"raw": None, "ok": False}})
    assert saved == 1
    assert cache.load_raw_replies("SOW-1") == {"step0_declaration": '{"a": 1}'}
    assert cache.load_raw_replies("SOW-2") == {}


def test_saving_more_raw_replies_keeps_the_earlier_ones(tmp_path):
    cache = ResponseCache(str(tmp_path))
    cache.save_raw_replies("SOW-1", {"step0_declaration": {"raw": "one"}})
    cache.save_raw_replies("SOW-1", {"call1_markets": {"raw": "two"}})
    assert cache.load_raw_replies("SOW-1") == {"step0_declaration": "one", "call1_markets": "two"}


def test_damaged_raw_replies_load_as_none_saved(tmp_path):
    (tmp_path / "forecasting").mkdir()
    (tmp_path / "forecasting" / "SOW-1.json").write_text("[1, 2", encoding="utf-8")
    assert ResponseCache(str(tmp_path)).load_raw_replies("SOW-1") == {}


def test_raw_replies_that_are_not_a_dict_are_not_saved(tmp_path):
    assert ResponseCache(str(tmp_path)).save_raw_replies("SOW-1", ["not", "a", "dict"]) == 0
