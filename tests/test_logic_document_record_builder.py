"""DocumentRecordBuilder: a record pre-filled from the AI's reading of the documents."""

import json
import os

import pytest

from app.logic.document_record_builder import DocumentRecordBuilder
from app.model.client_record import ClientRecord
from tests.logic_fixtures import CONFIG

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(TESTS_DIR, "documents", "marcus_lim_expected_extract.json"), encoding="utf-8") as _handle:
    READING = json.load(_handle)


def _builder():
    return DocumentRecordBuilder(CONFIG, "2026-10-14")


# A possible answer for each kind of field the officer is asked for.
ANSWERS = {"words": "Singapore", "label": "Director", "text": "1,000 employees", "age": 45, "year": 2020,
           "money_positive": 100000, "money": 0, "payment": "cash", "pep": "None", "countries": ["Singapore"],
           "composition": {"property": 0.5, "listed_equities": 0.2, "private_business": 0.1, "cash": 0.2},
           "sow": "Salary and bonuses saved over twenty years in banking, and one property sale."}


def test_build_fills_the_record_and_lists_what_the_documents_did_not_say():
    record, found, _ = _builder().build(READING, "SOW-DOC-1")
    assert isinstance(record, ClientRecord)
    assert record.client_ref == "SOW-DOC-1"
    assert record.current_date == "2026-10-14"
    assert record.jobs()
    assert isinstance(found, list) and "name" in found


def test_filling_the_gaps_leaves_nothing_missing():
    builder = _builder()
    record, _, _ = builder.build({"client": {"name": "A B"}}, "SOW-DOC-1")       # almost nothing was read
    for field in builder.missing_fields(record):
        record = builder.set_path(record, field["path"], ANSWERS[field["kind"]])
    assert builder.missing_fields(record) == []


def test_get_path_reaches_into_lists_and_dicts():
    builder = _builder()
    record = {"career_history": [{"occupation": "Planner"}], "claims": {}}
    assert builder.get_path(record, ["career_history", 0, "occupation"]) == "Planner"
    assert builder.get_path(record, ["career_history", 3, "occupation"]) is None


def test_set_path_gives_a_changed_copy_and_leaves_the_original_alone():
    builder = _builder()
    record, _, _ = builder.build(READING, "SOW-DOC-1")
    changed = builder.set_path(record, ["claims", "declared_net_worth"], 5)
    assert changed.claims.declared_net_worth == 5
    assert record.claims.declared_net_worth == READING["claims"]["declared_net_worth_sgd"]


def test_set_path_rejects_a_value_no_record_can_have():
    builder = _builder()
    record, _, _ = builder.build(READING, "SOW-DOC-1")
    with pytest.raises(ValueError, match="age must be between 18 and 120"):
        builder.set_path(record, ["career", "age"], 12)


def test_an_impossible_value_is_left_empty_and_named_while_every_good_field_is_kept():
    reading = {**READING, "client": {**READING["client"], "age": 12, "date_of_birth": None}}
    builder = _builder()
    record, found, dropped = builder.build(reading, "SOW-DOC-1")
    assert record.profile.age is None
    assert record.profile.name == READING["client"]["name"]
    assert len(dropped) == 1
    assert dropped[0].startswith("Age: the value read from the documents (12) is not possible (age must be between 18 and 120)")
    assert dropped[0].endswith("so it was left empty. Please enter it.")
    assert "career.age" not in found
    assert ["career", "age"] in [field["path"] for field in builder.missing_fields(record)]


def test_several_impossible_values_in_jobs_assets_and_claims_are_each_dropped_on_their_own():
    reading = {**READING, "jobs": [{**READING["jobs"][0], "start_year": 1800}],
               "assets": [{**READING["assets"][0], "price_paid_sgd": -5}],
               "claims": {**READING["claims"], "declared_net_worth_sgd": 0}}
    record, _, dropped = _builder().build(reading, "SOW-DOC-1")
    saved = record.to_dict()
    assert saved["career_history"][0]["start_year"] is None
    assert saved["career_history"][0]["occupation"] == READING["jobs"][0]["occupation"]
    assert saved["investments"][0]["price_paid"] is None
    assert saved["investments"][0]["country"] == READING["assets"][0]["country"]
    assert saved["claims"]["declared_net_worth"] is None
    assert saved["claims"]["expected_aum"] == READING["claims"]["expected_aum_sgd"]
    assert len(dropped) == 3
    assert any("price paid" in message and "(-5)" in message for message in dropped)


def test_a_reading_with_nothing_impossible_drops_nothing():
    _, _, dropped = _builder().build(READING, "SOW-DOC-1")
    assert dropped == []


def test_a_split_read_only_in_part_is_kept_as_fractions_and_asked_for():
    builder = _builder()
    record, _, _ = builder.build({"composition": {"property": 60, "cash": None}}, "SOW-DOC-1")
    assert record.claims.asset_composition["property"] == 0.6
    assert ["claims", "asset_composition"] in [field["path"] for field in builder.missing_fields(record)]


def test_check_warns_about_a_job_that_ends_before_it_starts():
    builder = _builder()
    record, _, _ = builder.build(READING, "SOW-DOC-1")
    record = builder.set_path(record, ["career_history", 0, "start_year"], 2015)
    record = builder.set_path(record, ["career_history", 0, "end_year"], 2010)
    assert "Job 1 ends (2010) before it starts (2015)." in builder.check(record)


def test_the_current_job_is_the_career_block():
    record, _, _ = _builder().build(READING, "SOW-DOC-1")
    saved = record.to_dict()
    assert saved["career"]["occupation"] == saved["career_history"][-1]["occupation"]


def test_the_same_reading_always_builds_the_same_record():
    first, found, _ = _builder().build(READING, "SOW-DOC-1")
    second, found_again, _ = _builder().build(READING, "SOW-DOC-1")
    assert first.to_dict() == second.to_dict() and found == found_again


# ---------------------------------------------------------------------------
# Menu option 2: a record from one AI reading (moved from test_document_autofill.py)
# ---------------------------------------------------------------------------

AI_REPLY = {
    "client": {"name": "Daniel Tan", "nationality": "Singaporean", "country_of_residence": "Singapore",
               "date_of_birth": "1980-03-15", "age": None},
    "jobs": [
        {"start_year": 2004, "end_year": 2012, "occupation": "Analyst", "seniority": "Analyst",
         "industry": "Banking", "employer_name": "DBS Bank", "employer_size": "30000",
         "country": "Singapore", "source_file": "cv.pdf"},
        {"start_year": 2012, "end_year": None, "occupation": "Portfolio Manager", "seniority": "Director",
         "industry": "Asset Management", "employer_name": "Temasek", "employer_size": None,
         "country": "Singapore", "source_file": "cv.pdf"},
    ],
    "assets": [
        {"asset_type": "Property - Condo", "country": "Singapore", "year_acquired": 2015,
         "price_paid_sgd": 1800000, "current_declared_value_sgd": 2400000, "payment_method": "loan",
         "income_produced_sgd": 60000, "source_file": "deed.pdf"},
    ],
    "composition": {"property": 50, "listed_equities": 30, "private_business": 0, "cash": 20},
    "claims": {"declared_net_worth_sgd": 4800000, "expected_aum_sgd": 2000000, "pep_status": "None",
               "wealth_countries": ["Singapore"], "biggest_wealth_jump_sgd": None,
               "wealth_jump_years": None, "declared_counterparties": ["DBS Bank", "UOB Kay Hian"]},
    "sow_declaration": None,
    "notes": ["2019 bonus is in USD (payslip.pdf) - convert to SGD"],
}


def _doc_builder():
    return DocumentRecordBuilder(CONFIG, "2026-10-13")


def doc_record():
    record, found, _ = _doc_builder().build(AI_REPLY, "CL-TEST")
    return record, found


def test_record_from_documents_uses_the_new_client_form_layout():
    record, found = doc_record()

    saved = record.to_dict()
    assert saved["career"]["age"] == 46                                  # from the date of birth
    assert saved["claims"]["asset_composition"]["property"] == 0.5       # stored as fractions
    assert saved["investments"][0]["current_declared_value"] == 2400000    # same name as the web form
    assert saved["investments"][0]["income_produced"] == 60000
    assert "name" in found and "claims.declared_net_worth" in found


def test_only_missing_required_fields_are_asked_for():
    record, _ = doc_record()
    missing = [".".join(map(str, f["path"])) for f in _doc_builder().missing_fields(record)]

    # the only gaps in AI_REPLY: Temasek's employer size and the source of wealth declaration
    assert missing == ["career_history.1.employer_size", "sow_declaration"]


def test_no_jobs_in_documents_still_asks_for_the_current_job():
    record, _, _ = _doc_builder().build({"client": {"name": "A B"}}, "CL-X")
    missing = {".".join(map(str, f["path"])) for f in _doc_builder().missing_fields(record)}

    assert "career_history.0.occupation" in missing
    assert "claims.asset_composition" in missing


def test_the_current_job_is_copied_into_career():
    record, _ = doc_record()
    career = _doc_builder().finish(record).to_dict()["career"]

    assert career["employer_name"] == "Temasek"
    assert career["career_start_year"] == 2004


def test_summary_marks_where_each_value_came_from():
    original, _ = doc_record()
    record = _doc_builder().set_path(original, ["name"], "Daniel K. Tan")
    record = _doc_builder().set_path(record, ["career_history", 1, "employer_size"], "12000")
    rows = {".".join(map(str, r["path"])): r["source"]
            for r in _doc_builder().summarise(record, original)}

    assert rows["nationality"] == "documents"
    assert rows["name"] == "edited"
    assert rows["career_history.1.employer_size"] == "entered"
    assert rows["sow_declaration"] == "blank"


def test_finish_after_an_edit_copies_the_last_job_when_every_job_has_ended():
    """When the documents list no open job, the last job is the one shown in "career"; after the
    officer edits that job, finish shows the edited job there again."""
    reply = {**AI_REPLY, "jobs": [dict(AI_REPLY["jobs"][0]), {**AI_REPLY["jobs"][1], "end_year": 2025}]}
    record, _, _ = _doc_builder().build(reply, "CL-TEST")
    saved = record.to_dict()
    saved["career_history"][1]["employer_name"] = "Temasek Holdings"           # as the edit screen would
    finished = _doc_builder().finish(ClientRecord.from_dict(saved)).to_dict()

    assert finished["career"]["employer_name"] == "Temasek Holdings"


def test_checks_flag_impossible_dates():
    record, _ = doc_record()
    record = _doc_builder().set_path(record, ["career_history", 0, "end_year"], 2001)

    assert any("ends (2001) before it starts (2004)" in w for w in _doc_builder().check(record))
