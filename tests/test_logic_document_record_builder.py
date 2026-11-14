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
    record, found = _doc_builder().build(AI_REPLY, "CL-TEST")
    return record, found


def test_record_from_documents_uses_the_new_client_form_layout():
    record, found = doc_record()

    assert record["career"]["age"] == 46                                  # from the date of birth
    assert record["claims"]["asset_composition"]["property"] == 0.5       # stored as fractions
    assert record["investments"][0]["current_declared_value"] == 2400000    # same name as the web form
    assert record["investments"][0]["income_produced"] == 60000
    assert "name" in found and "claims.declared_net_worth" in found


def test_only_missing_required_fields_are_asked_for():
    record, _ = doc_record()
    missing = [".".join(map(str, f["path"])) for f in _doc_builder().missing_fields(record)]

    # the only gaps in AI_REPLY: Temasek's employer size and the source of wealth declaration
    assert missing == ["career_history.1.employer_size", "sow_declaration"]


def test_no_jobs_in_documents_still_asks_for_the_current_job():
    record, _ = _doc_builder().build({"client": {"name": "A B"}}, "CL-X")
    missing = {".".join(map(str, f["path"])) for f in _doc_builder().missing_fields(record)}

    assert "career_history.0.occupation" in missing
    assert "claims.asset_composition" in missing


def test_finish_copies_the_current_job_into_career():
    record, _ = doc_record()
    record = _doc_builder().finish(record)

    assert record["career"]["employer_name"] == "Temasek"
    assert record["career"]["career_start_year"] == 2004


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


def test_profile_edit_reaches_the_current_job():
    before, _ = doc_record()
    before = _doc_builder().finish(before)
    after = _doc_builder().set_path(before, ["career", "employer_name"], "Temasek Holdings")

    synced = _doc_builder().sync_after_edit(before, after)

    assert synced["career_history"][1]["employer_name"] == "Temasek Holdings"


def test_checks_flag_impossible_dates():
    record, _ = doc_record()
    record = _doc_builder().set_path(record, ["career_history", 0, "end_year"], 2001)
    record = _doc_builder().finish(record)

    assert any("ends (2001) before it starts (2004)" in w for w in _doc_builder().check(record))
