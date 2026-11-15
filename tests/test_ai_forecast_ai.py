"""ForecastAI: the five-step forecast, run from hard-coded replies. No network."""

import json
import os

import pytest

from app.ai.forecast_ai import ForecastAI
from app.model.claimed_source import ClaimedSource
from app.model.declaration import Declaration
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


def test_read_declaration_gives_a_declaration_of_the_claimed_sources(case):
    replies = fake_ai.forecast_replies(case)
    declaration = _service().read_declaration(case, replies)
    assert isinstance(declaration, Declaration)
    assert all(isinstance(source, ClaimedSource) for source in declaration.sources())
    assert [source.source_id for source in declaration.sources()] == ["S1", "S2"]
    assert json.dumps(declaration.to_dict()) == replies["step0_declaration"]      # nothing lost or reordered
    assert _service().read_declaration(case, {}) is None


def test_the_run_keeps_the_declaration_object_in_the_forecast(case):
    run = _service().run({"record": case, "cache": fake_ai.forecast_replies(case)})
    assert isinstance(run["forecast"]["declaration"], Declaration)
    assert run["partial"]["declaration"] is run["forecast"]["declaration"]


def test_the_prompts_show_the_claimed_sources_exactly_as_the_ai_read_them(case):
    replies = fake_ai.forecast_replies(case)
    reading = json.loads(replies["step0_declaration"])
    reading["claimed_sources"][1] = dict(sorted(reading["claimed_sources"][1].items()))  # keys in another order
    del reading["claimed_sources"][0]["counterparty"]                                    # an older reading
    replies["step0_declaration"] = json.dumps(reading)
    shown = json.dumps(reading["claimed_sources"], indent=2, ensure_ascii=False)
    for piece in ("call1_markets.list", "call3_types.list", "call3_types.behaviour.T1"):
        saved = dict(replies)
        caller = _Caller([saved.pop(piece)])
        assert _service(caller).run({"record": case, "cache": saved})["ok"]
        sent = caller.prompts[0].split("DATA:")[1]
        assert "\n".join("  " + line for line in shown.splitlines()).lstrip() in sent, piece


def test_a_declaration_reading_with_a_negative_amount_is_sent_back(case):
    replies = fake_ai.forecast_replies(case)
    reading = json.loads(replies.pop("step0_declaration"))
    good = json.dumps(reading)
    reading["claimed_sources"][1]["amount"] = -5
    caller = _Caller([json.dumps(reading), good])
    declaration = _service(caller).read_declaration(case, {})
    assert caller.prompts[1].count("S2: amount cannot be negative") == 1
    assert [source.amount for source in declaration.sources()] == [None, None]


def test_a_crime_type_must_be_enabled_by_a_declared_source_and_start_after_it(case):
    declaration = Declaration.from_dict(json.loads(fake_ai.forecast_replies(case)["step0_declaration"]))
    start, last = _service()._career_years(case)[0], _service()._future_years(case)[-1]
    honest = {"type_id": "T1", "category": SETTINGS["honest_category"], "open_from": start, "open_to": last,
              "rule_out_documents": [{"document_code": "DOC_TAX_RETURNS", "also_rules_out": []}],
              "enabled_by_position_index": None, "enabled_by_asset_index": None, "enabled_by_source_id": None}
    crime = {**honest, "type_id": "T2", "category": "TAX_EVASION", "open_from": 2010, "open_to": 2012,
             "enabled_by_source_id": "S2"}
    errors = _service()._check_person_types({"person_types": [honest, crime]}, case, declaration.sources())
    assert any("before declared source S2 started (2018)" in error for error in errors)
    unknown = {**crime, "enabled_by_source_id": "S9", "open_from": 2019}
    errors = _service()._check_person_types({"person_types": [honest, unknown]}, case, declaration.sources())
    assert any("'S9' is not a declared source" in error for error in errors)
    overlapping = {**crime, "open_to": last}
    repaired = _service()._repair_person_types({"person_types": [honest, overlapping]}, case, declaration.sources())
    assert repaired["person_types"][1]["open_from"] == 2018                 # moved to when S2 started


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
