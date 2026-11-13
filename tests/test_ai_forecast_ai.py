"""ForecastAI: the five-step forecast, run from hard-coded replies. No network."""

import json
import os

import pytest

from app.ai.forecast_ai import ForecastAI
from app.data.config_reader import ConfigReader
from tests import fake_ai

READER = ConfigReader()
SETTINGS = {**READER.read("policy")["forecasting"], "retry_wait_seconds": 0, "web_search": False}
VOCABULARY = READER.read("vocabulary")

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sample", "case_001.json")


@pytest.fixture(scope="module")
def case():
    with open(SAMPLE, encoding="utf-8") as handle:
        return json.load(handle)


class _Caller:
    """A made-up AI caller: answers each question from a table of hard-coded replies, in order."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt, schema, options):
        self.prompts.append(prompt)
        reply = self.replies.pop(0) if self.replies else None
        if isinstance(reply, Exception):
            raise reply
        return reply


def _service(caller=None, settings=SETTINGS):
    return ForecastAI("fake", caller, "gpt-test", 0.0, None, 4, settings, VOCABULARY)


def test_the_stages_run_in_order(case):
    seen = []
    run = _service().run({"record": case, "cache": fake_ai.forecast_replies(case), "on_step": seen.append})
    assert run["ok"]
    assert tuple(seen) == ForecastAI.STAGES
    assert set(run["forecast"]) == {"declaration", "markets", "earnings", "types", "events", "prompt_versions"}


def test_saved_replies_need_no_ai_caller(case):
    run = _service(caller=None).run({"record": case, "cache": fake_ai.forecast_replies(case)})
    assert run["ok"]
    assert all(result["from_cache"] for result in run["results"].values())


def test_no_saved_replies_and_no_caller_stops_at_the_first_step(case):
    run = _service(caller=None).run({"record": case, "cache": {}})
    assert run["ok"] is False
    assert run["failed_step"] == "step0_declaration"
    assert "API key" in run["failed_error"]
    assert run["forecast"] == {}


def test_a_connection_failure_stops_the_run_without_crashing(case):
    caller = _Caller([None] * SETTINGS["max_retries"])
    run = _service(caller).run({"record": case, "cache": {}})
    assert run["ok"] is False
    assert run["failed_piece"] == "step0_declaration"
    assert "the AI request failed" in run["failed_error"]
    assert len(caller.prompts) == SETTINGS["max_retries"]


def test_a_caller_that_answers_resumes_from_the_saved_pieces(case):
    replies = fake_ai.forecast_replies(case)
    declaration = replies.pop("step0_declaration")
    caller = _Caller([declaration])
    run = _service(caller).run({"record": case, "cache": replies})
    assert run["ok"]
    assert len(caller.prompts) == 1
    assert run["results"]["step0_declaration"]["from_cache"] is False
    assert run["results"]["step0_declaration"]["raw"] == declaration


def test_a_malformed_reply_is_sent_back_with_the_reason(case):
    replies = fake_ai.forecast_replies(case)
    declaration = replies.pop("step0_declaration")
    caller = _Caller(["This is not JSON at all.", declaration])
    run = _service(caller).run({"record": case, "cache": replies})
    assert run["ok"]
    assert run["results"]["step0_declaration"]["attempts"] == 2
    assert "YOUR PREVIOUS ANSWER WAS REJECTED" in caller.prompts[1]
    assert "invalid JSON" in caller.prompts[1]


def test_a_reply_that_breaks_the_schema_is_rejected(case):
    replies = fake_ai.forecast_replies(case)
    replies.pop("step0_declaration")
    bad = json.dumps({"claimed_sources": "none"})
    run = _service(_Caller([bad] * SETTINGS["max_retries"])).run({"record": case, "cache": replies})
    assert run["ok"] is False
    assert "reply failed checks" in run["failed_error"]


def test_a_saved_reply_that_is_no_longer_valid_is_asked_again(case):
    replies = fake_ai.forecast_replies(case)
    good = replies["step0_declaration"]
    replies["step0_declaration"] = json.dumps({"claimed_sources": "none"})
    caller = _Caller([good])
    run = _service(caller).run({"record": case, "cache": replies})
    assert run["ok"] and len(caller.prompts) == 1


def test_what_finished_is_kept_when_a_later_step_fails(case):
    replies = fake_ai.forecast_replies(case)
    replies["call3_types.list"] = json.dumps({"person_types": []})
    run = _service().run({"record": case, "cache": replies})
    assert run["ok"] is False
    assert run["failed_step"] == "call3_types"
    assert set(run["partial"]) == {"declaration", "markets", "earnings"}


def test_the_ai_never_sees_the_name_or_the_declared_figures(case):
    replies = fake_ai.forecast_replies(case)
    declaration = replies.pop("step0_declaration")
    caller = _Caller([declaration])
    _service(caller).run({"record": case, "cache": replies})
    sent = caller.prompts[0].split("DATA:")[1]
    assert "Tan" not in sent and "Daniel" not in sent
    assert "the client started as an operations planner" in sent     # "Mr Tan" became "the client"
    assert "16500000" not in sent and "3100000" not in sent
    assert "Chief Operating Officer" in sent


def test_read_declaration_gives_the_claimed_sources(case):
    declaration = _service().read_declaration(case, fake_ai.forecast_replies(case))
    assert [source["source_id"] for source in declaration["claimed_sources"]] == ["S1", "S2"]
    assert _service().read_declaration(case, {}) is None


def test_ranges_labelled_back_to_front_are_put_in_order():
    fixed = _service()._sort_ranges({"change_pct": {"low": -1, "typical": -2, "high": -3}})
    assert fixed == {"change_pct": {"low": -3, "typical": -2, "high": -1}}


def test_too_many_asset_exposures_are_repaired_not_rejected():
    markets = {"ECO_SG", "PROP_BISHAN", "PROP_SG", "FX_SGD", "IND_PARTS", "STOCK_SG"}
    reply = {"asset_index": 0, "exposures": [
        {"market_id": market, "sensitivity": {"low": 2, "typical": 5 - number * 0.5, "high": 10}}
        for number, market in enumerate(sorted(markets))],
        "own_growth_pct": {"low": 0, "typical": 1, "high": 2},
        "income_yield_by_year": [{"year": year, "yield_pct": {"low": 2, "typical": 3, "high": 4}}
                                 for year in range(2010, 2027)],
        "future_income_yield_pct": {scenario: {"low": 2, "typical": 3, "high": 4}
                                    for scenario in ForecastAI.SCENARIOS},
        "valuation_basis": "Bishan property index"}
    service = _service()
    repaired = service._repair_asset_model(reply, markets)
    assert len(repaired["exposures"]) == SETTINGS["max_asset_exposures"]
    assert service._check_asset_model(repaired, 0, list(range(2010, 2027)), markets) == []
