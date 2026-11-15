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


def _builder(read=None):
    return CaseBuilder(ConsoleUI(read=read), SCHEMA)


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
    case = _builder(_never_ask).build(ClientRecord.from_dict(sample_case()))
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

    case = _builder(ask).build(ClientRecord.from_dict(saved))
    assert len(asked) == 1 and "Year started as" in asked[0]
    assert case["career_history"][-1]["occupation"] == saved["career"]["occupation"]
    assert case["career_history"][-1]["end_year"] is None


def test_an_empty_amount_and_year_are_asked_for_and_must_be_possible(capsys):
    """A saved asset with no price and no year: the officer is asked for both, and an impossible
    answer (zero price, a year before his career) is asked again."""
    saved = sample_case()
    saved["investments"][0]["price_paid"] = None
    saved["investments"][0]["year_acquired"] = None
    name = saved["investments"][0]["asset_type"]
    first_year = min(job["start_year"] for job in saved["career_history"])
    answers = {f"{name}: year bought": [str(first_year - 1), str(first_year + 1)],
               f"{name}: price paid (SGD)": ["0", "1,650,000"]}
    asked = []

    def ask(question: str) -> str:
        asked.append(question)
        return answers[question.rstrip(": ")].pop(0)

    case = _builder(ask).build(ClientRecord.from_dict(saved))
    assert case["investments"][0]["year_acquired"] == first_year + 1
    assert case["investments"][0]["price_paid"] == 1_650_000
    assert len(asked) == 4
    assert capsys.readouterr().out.count("[ERROR]") == 2


def test_show_case_problems_names_the_case_and_lists_every_problem(capsys):
    _builder().show_case_problems("CL-1", ["age is missing", "net worth must be above 0"])
    shown = capsys.readouterr().out
    assert "CL-1 can't be assessed yet:" in shown
    assert "    - age is missing" in shown and "    - net worth must be above 0" in shown
    assert "Fix the client record" in shown
