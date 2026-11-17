"""BenchmarkAI: the allowlist, with a hard-coded AI reply. No network."""

import json

from app.ai.benchmark_ai import BenchmarkAI
from tests import fake_ai

CLIENT = {"client_ref": "SOW-1", "occupation": "Chief Operating Officer", "industry": "Shipping", "age": 51,
          "career_start_year": 1998, "country": "Singapore", "declared_net_worth": 16500000,
          "cash": 20, "declaration_text": "My wealth came from a secret source."}
ECONOMY = {"markets": [{"market_id": "ECO_SG", "changes": {"2024": 3.0}}]}


class _Caller:
    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def __call__(self, prompt, schema, options):
        self.prompts.append(prompt)
        return self.replies.pop(0)


def _service(caller):
    return BenchmarkAI("fake", caller, "gpt-test", 0.0)


def test_the_allowlist_is_the_five_career_fields():
    assert BenchmarkAI.ALLOWED_FIELDS == ["occupation", "industry", "age", "career_start_year", "country"]


def test_the_benchmark_reply_is_returned():
    caller = _Caller(json.dumps(fake_ai.benchmark()))
    assert _service(caller).run({"client": CLIENT, "economy": ECONOMY})["expected_wealth"] == 2_400_000


def test_declared_figures_never_reach_the_ai():
    caller = _Caller(json.dumps(fake_ai.benchmark()))
    _service(caller).run({"client": CLIENT, "economy": ECONOMY})
    prompt = caller.prompts[0]
    assert "Chief Operating Officer" in prompt and "ECO_SG" in prompt
    assert "16500000" not in prompt
    assert "secret source" not in prompt
    assert "SOW-1" not in prompt


def test_with_no_economy_the_prompt_says_so():
    caller = _Caller(json.dumps(fake_ai.benchmark()))
    _service(caller).run({"client": CLIENT, "economy": None})
    assert "not available" in caller.prompts[0]


def test_a_malformed_reply_then_a_good_one_succeeds():
    caller = _Caller(json.dumps({"expected_wealth": "a lot"}), json.dumps(fake_ai.benchmark()))
    assert _service(caller).run({"client": CLIENT, "economy": None}) is not None
    assert len(caller.prompts) == 2


def test_no_connection_gives_none():
    assert _service(_Caller(None, None)).run({"client": CLIENT, "economy": None}) is None


def test_the_same_career_in_a_different_economy_is_asked_again():
    saved = {}
    _service(_Caller(json.dumps(fake_ai.benchmark()))).run(
        {"client": CLIENT, "economy": ECONOMY, "saved_replies": saved})
    reused = _Caller()
    assert _service(reused).run(
        {"client": CLIENT, "economy": ECONOMY, "saved_replies": saved})["expected_wealth"] == 2_400_000
    assert reused.prompts == []
    again = _Caller(json.dumps(fake_ai.benchmark(expected_wealth=3_000_000)))
    assert _service(again).run(
        {"client": CLIENT, "economy": None, "saved_replies": saved})["expected_wealth"] == 3_000_000
    assert len(again.prompts) == 1
