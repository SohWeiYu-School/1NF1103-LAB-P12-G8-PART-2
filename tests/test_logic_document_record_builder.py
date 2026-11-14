"""DocumentRecordBuilder: a record pre-filled from the AI's reading of the documents."""

import json
import os

from app.logic.document_record_builder import DocumentRecordBuilder
from tests.logic_fixtures import CONFIG

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(TESTS_DIR, "documents", "marcus_lim_expected_extract.json"), encoding="utf-8") as _handle:
    READING = json.load(_handle)


def _builder():
    return DocumentRecordBuilder(CONFIG, "2026-10-14")


def test_build_fills_the_record_and_lists_what_the_documents_did_not_say():
    record, missing = _builder().build(READING, "SOW-DOC-1")
    assert record["client_ref"] == "SOW-DOC-1"
    assert record["current_date"] == "2026-10-14"
    assert record["career_history"]
    assert isinstance(missing, list)


def test_filling_the_gaps_leaves_nothing_missing():
    builder = _builder()
    record, _ = builder.build(READING, "SOW-DOC-1")
    for field in builder.missing_fields(record):
        record = builder.set_path(record, field["path"], 0.25 if field["kind"] == "percent" else
                                  2020 if field["kind"] == "year" else 1 if field["kind"] == "number" else "filled")
    assert builder.missing_fields(record) == []


def test_get_and_set_path_reach_into_lists_and_dicts():
    builder = _builder()
    record = {"career_history": [{"occupation": "Planner"}], "claims": {}}
    assert builder.get_path(record, ["career_history", 0, "occupation"]) == "Planner"
    changed = builder.set_path(record, ["claims", "declared_net_worth"], 5)
    assert changed["claims"]["declared_net_worth"] == 5
    assert record["claims"] == {}                       # the original is left alone
    assert builder.get_path(record, ["career_history", 3, "occupation"]) is None


def test_check_warns_about_a_job_that_ends_before_it_starts():
    builder = _builder()
    record, _ = builder.build(READING, "SOW-DOC-1")
    record["career_history"][0]["start_year"], record["career_history"][0]["end_year"] = 2015, 2010
    assert "Job 1 ends (2010) before it starts (2015)." in builder.check(record)


def test_finish_makes_the_current_job_the_career_block():
    builder = _builder()
    record, _ = builder.build(READING, "SOW-DOC-1")
    finished = builder.finish(record)
    assert finished["career"]["occupation"] == finished["career_history"][-1]["occupation"]


def test_the_same_reading_always_builds_the_same_record():
    assert _builder().build(READING, "SOW-DOC-1") == _builder().build(READING, "SOW-DOC-1")
