"""ClientRecord: the whole client, and the checks only the whole record can make."""

import json
import os

import pytest

from app.model.client_record import ClientRecord
from app.model.verdict import Verdict

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sample", "case_001.json")
POLICY = {"asset_categories": {"property": ["property", "condo"], "listed_equities": ["equit"],
                               "private_business": ["business", "stake"]}}


def _sample() -> dict:
    with open(SAMPLE, encoding="utf-8") as handle:
        return json.load(handle)


def _record() -> ClientRecord:
    record = ClientRecord("SOW-1", "Daniel Tan", "Malaysian", "2026-09-24", "Singapore", 51)
    record.add_job({"start_year": 1998, "end_year": 2016, "occupation": "Planner", "seniority": "Junior",
                    "industry": "Shipping", "employer_name": "Pacific Crest", "employer_size": "5,000+",
                    "country": "Singapore"})
    record.add_job({"start_year": 2017, "end_year": None, "occupation": "COO", "seniority": "C-suite",
                    "industry": "Shipping", "employer_name": "Straits Harbour", "employer_size": "1,000-5,000",
                    "country": "Singapore"})
    record.add_investment({"asset_type": "Condo property", "country": "Singapore", "year_acquired": 2009,
                           "price_paid": 1000000, "current_declared_value": 2000000,
                           "payment_method": "loan", "income_produced": 0})
    record.set_claims({"declared_net_worth": 4000000, "expected_aum": 1000000, "pep_status": "None",
                       "asset_composition": {"property": 0.5, "cash": 0.3, "listed_equities": 0.2},
                       "wealth_countries": ["Singapore"], "declared_counterparties": ["DBS"]})
    record.sow_declaration = "Salary savings over a long career in shipping."
    return record


def test_a_saved_record_survives_a_round_trip():
    saved = _sample()
    expected = {**saved, "supporting_documents": [],
                "claims": {**saved["claims"], "biggest_wealth_jump": None, "wealth_jump_years": None,
                           "declared_counterparties": []}}
    rebuilt = ClientRecord.from_dict(saved).to_dict()
    assert rebuilt == expected
    assert ClientRecord.from_dict(rebuilt).to_dict() == rebuilt


def test_round_trip_keeps_every_declared_figure():
    saved = _sample()
    claims = ClientRecord.from_dict(saved).to_dict()["claims"]
    for key, value in saved["claims"].items():
        assert claims[key] == value


def test_the_record_builds_and_owns_its_parts():
    record = _record()
    assert [job.occupation for job in record.jobs()] == ["Planner", "COO"]
    assert record.current_job().occupation == "COO"
    assert record.career_start_year() == 1998
    assert record.claims.liquid_share() == pytest.approx(0.5)
    assert record.profile.age == 51


def test_parts_validate_their_own_values_when_added():
    record = _record()
    with pytest.raises(ValueError):
        record.add_investment({"asset_type": "Flat", "country": "Singapore", "year_acquired": 2010,
                               "price_paid": -5, "current_declared_value": 1, "payment_method": "cash",
                               "income_produced": 0})
    with pytest.raises(ValueError):
        record.set_claims({"declared_net_worth": -1})


def test_career_in_the_saved_layout_is_the_current_job_plus_the_profile():
    career = _record().to_dict()["career"]
    assert career == {"occupation": "COO", "seniority": "C-suite", "industry": "Shipping",
                      "employer_name": "Straits Harbour", "employer_size": "1,000-5,000",
                      "career_start_year": 1998, "country_of_residence": "Singapore", "age": 51}


def test_a_current_job_kept_only_in_career_survives_a_round_trip():
    """The command line's New Client form keeps the current job in "career" and lists only the
    earlier, ended jobs in career_history. Loading and saving must not replace it with the last old job."""
    career = {"occupation": "COO", "seniority": "C-suite", "industry": "Shipping",
              "employer_name": "Straits Harbour", "employer_size": "2500", "country_of_residence": "Singapore",
              "age": 51, "career_start_year": 1996}
    saved = {"client_ref": "CL-1", "name": "Daniel Tan", "nationality": "Malaysian", "current_date": "2026-09-24",
             "career": career,
             "career_history": [{"start_year": 1998, "end_year": 2016, "occupation": "Planner",
                                 "seniority": "Junior", "industry": "Shipping", "employer_name": "Pacific Crest",
                                 "employer_size": "5000", "country": "Singapore"}]}
    assert ClientRecord.from_dict(saved).to_dict()["career"] == career


def test_a_clean_record_has_no_problems_or_warnings():
    record = _record()
    assert record.problems() == []
    assert record.warnings(POLICY) == []


def test_two_open_jobs_and_a_job_in_the_future_are_problems():
    record = _record()
    record.add_job({"start_year": 2030, "end_year": None, "occupation": "Advisor", "seniority": "Senior",
                    "industry": "Shipping", "employer_name": "X", "employer_size": "1-10", "country": "Singapore"})
    problems = record.problems()
    assert "Job 3 starts in the future (2030)." in problems
    assert "2 jobs have no end year; only one should be the current job." in problems


def test_a_job_that_ends_before_it_starts_is_reported_with_its_number():
    record = ClientRecord("SOW-1", "Daniel Tan", "Malaysian", "2026-09-24")
    record.add_job({"start_year": 2004, "end_year": 2001, "occupation": "Planner", "seniority": "Junior",
                    "industry": "Shipping", "employer_name": "X", "employer_size": "1-10", "country": "Singapore"})
    assert record.problems() == ["Job 1 ends (2001) before it starts (2004)."]


def test_an_asset_bought_before_the_career_started_is_a_problem():
    record = _record()
    record.add_investment({"asset_type": "Shares", "country": "Singapore", "year_acquired": 1990,
                           "price_paid": 1, "current_declared_value": 1, "payment_method": "cash",
                           "income_produced": 0})
    assert any("Asset 2 was bought in 1990" in problem for problem in record.problems())


def test_a_missing_name_is_a_problem():
    assert ClientRecord("SOW-1", "", "Malaysian", "2026-09-24").problems() == ["The record has no name."]


def test_starting_work_before_fourteen_is_a_warning():
    record = ClientRecord("SOW-1", "Daniel Tan", "Malaysian", "2026-09-24", "Singapore", 30)
    record.add_job({"start_year": 2000, "end_year": None, "occupation": "COO", "seniority": "C-suite",
                    "industry": "Shipping", "employer_name": "X", "employer_size": "1-10", "country": "Singapore"})
    assert record.warnings(POLICY) == ["Career start year 2000 means the client started work before age 14."]


def test_assets_worth_far_more_than_the_net_worth_are_a_warning():
    record = _record()
    record.claims.declared_net_worth = 1000000
    assert any("well above the declared net worth" in warning for warning in record.warnings(POLICY))


def test_a_split_that_disagrees_with_the_assets_listed_is_a_warning():
    record = _record()
    record.claims.asset_composition = {"property": 0.1, "cash": 0.5, "listed_equities": 0.4}
    assert any("property assets listed" in warning for warning in record.warnings(POLICY))


def test_crime_scan_input_holds_only_what_the_crime_scan_may_see():
    data = _record().crime_scan_input()
    assert data == {"client_ref": "SOW-1", "occupation": "COO", "industry": "Shipping", "age": 51,
                    "career_start_year": 1998, "country": "Singapore", "country_of_residence": "Singapore",
                    "declaration_text": "Salary savings over a long career in shipping."}
    assert "declared_net_worth" not in data


def test_benchmark_input_gives_the_split_in_whole_percents():
    data = _record().benchmark_input()
    assert (data["property"], data["cash"], data["listed_equities"]) == (50, 30, 20)
    assert data["private_business"] is None
    assert data["declared_net_worth"] == 4000000
    assert data["declared_counterparties"] == ["DBS"]


def test_record_assessment_updates_the_review_status():
    record = _record()
    verdict = Verdict("a1", "SOW-1", "2026-09-24", "RISKY", "Escalate to compliance", "2027-03-24")
    record.record_assessment(verdict, {"client_ref": "SOW-1"})
    assert record.review_status.outcome == "RISKY"
    saved = record.to_dict()
    assert saved["routing"] == "Escalate to compliance"
    assert saved["next_review_date"] == "2027-03-24"
    assert ClientRecord.from_dict(saved).review_status.last_assessed_on == "2026-09-24"


def test_documents_are_kept_in_the_order_they_were_added():
    record = _record()
    record.add_document({"file_id": "f1", "file_name": "tax.pdf"})
    assert record.documents() == [{"file_id": "f1", "file_name": "tax.pdf"}]
    with pytest.raises(ValueError):
        record.add_document("tax.pdf")
