"""CaseBuilder: a saved record read into a case, and the case checked against its schema."""

import json
import os

from app.interface.case_builder import CaseBuilder
from app.interface.console_ui import ConsoleUI
from app.model.client_record import ClientRecord
from tests.logic_fixtures import sample_case

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "app", "schemas", "case_input.schema.json")
with open(SCHEMA_PATH, encoding="utf-8") as _handle:
    SCHEMA = json.load(_handle)


def _builder():
    return CaseBuilder(ConsoleUI(), SCHEMA)


def _never_ask(question: str) -> str:
    raise AssertionError(f"the officer was asked: {question}")


def test_the_sample_case_is_valid():
    assert _builder().validate_case(sample_case()) == []


def test_something_that_is_not_a_case_is_rejected():
    assert _builder().validate_case(["not", "a", "case"]) == ["the case must be a JSON object"]


def test_a_case_with_a_field_missing_names_the_field():
    case = sample_case()
    del case["claims"]["declared_net_worth"]
    problems = _builder().validate_case(case)
    assert problems and any("declared_net_worth" in problem for problem in problems)


def test_a_job_that_ends_before_it_starts_is_a_problem():
    case = sample_case()
    case["career_history"][0]["end_year"] = case["career_history"][0]["start_year"] - 1
    assert _builder().validate_case(case) != []


def test_a_complete_record_becomes_a_case_without_asking_anything(capsys):
    case = _builder().case_from_client_record(ClientRecord.from_dict(sample_case()), _never_ask)
    assert case is not None
    assert case["client_ref"] == sample_case()["client_ref"]
    assert _builder().validate_case(case) == []


def test_a_current_job_kept_only_in_career_is_added_and_only_its_start_year_is_asked(capsys):
    """The command line's New Client form keeps the current job in "career" and only earlier jobs
    in career_history: the case gets the current job from "career"."""
    saved = sample_case()
    *earlier, current = saved["career_history"]
    saved["career_history"] = earlier
    asked = []

    def ask(question: str) -> str:
        asked.append(question)
        return str(current["start_year"])

    case = _builder().case_from_client_record(ClientRecord.from_dict(saved), ask)
    assert len(asked) == 1 and "Year started as" in asked[0]
    assert case["career_history"][-1]["occupation"] == saved["career"]["occupation"]
    assert case["career_history"][-1]["end_year"] is None
