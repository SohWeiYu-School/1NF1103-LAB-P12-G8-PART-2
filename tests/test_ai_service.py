"""AIService: what every AI question shares. The AI replies are hard-coded; no network."""

import json

import pytest

from app.ai.ai_service import AIService
from app.ai.response_cache import ResponseCache

SCHEMA = {"type": "object", "required": ["answer"], "additionalProperties": False,
          "properties": {"answer": {"type": "string"}}}


class _Question(AIService):
    """A small child for these tests: sends only "industry" and uses a fixed prompt and schema."""

    PROMPT_NAME = "test_question"

    def _payload(self, source: dict) -> dict:
        return {"industry": source["industry"]}

    def _load_prompt(self, name: str) -> str:
        return "# prompt_version: v1\nAnswer about {payload_json}"

    def _schema(self, source: dict) -> dict:
        return SCHEMA


class _Replies:
    """A made-up AI caller that gives the next hard-coded reply each time it is asked."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []
        self.options = []

    def __call__(self, prompt, schema, options):
        self.prompts.append(prompt)
        self.options.append(options)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


SOURCE = {"industry": "Shipping", "declared_net_worth": 16500000}
GOOD = json.dumps({"answer": "yes"})


def test_the_abstract_parent_cannot_be_created():
    with pytest.raises(TypeError):
        AIService()


def test_a_good_reply_is_returned_as_a_dict():
    caller = _Replies(GOOD)
    assert _Question("fake", caller).run(SOURCE) == {"answer": "yes"}


def test_only_the_payload_is_sent_to_the_ai():
    caller = _Replies(GOOD)
    _Question("fake", caller).run(SOURCE)
    assert "Shipping" in caller.prompts[0]
    assert "16500000" not in caller.prompts[0]


def test_the_services_model_is_passed_to_the_caller():
    caller = _Replies(GOOD)
    _Question("fake", caller, model="gpt-test").run(SOURCE)
    assert caller.options[0]["model"] == "gpt-test"


def test_a_reply_wrapped_in_a_code_block_is_still_read():
    caller = _Replies("```json\n" + GOOD + "\n```")
    assert _Question("fake", caller).run(SOURCE) == {"answer": "yes"}


def test_a_connection_failure_then_a_good_reply_succeeds_on_the_second_attempt():
    caller = _Replies(None, GOOD)
    assert _Question("fake", caller).run(SOURCE) == {"answer": "yes"}
    assert len(caller.prompts) == 2


def test_a_reply_that_is_not_json_is_rejected_and_asked_again():
    caller = _Replies("Sorry, I cannot help with that.", GOOD)
    assert _Question("fake", caller).run(SOURCE) == {"answer": "yes"}


def test_a_reply_that_breaks_the_schema_is_rejected_and_asked_again():
    caller = _Replies(json.dumps({"wrong": "field"}), GOOD)
    assert _Question("fake", caller).run(SOURCE) == {"answer": "yes"}


def test_no_usable_reply_after_every_attempt_gives_none():
    caller = _Replies(None, json.dumps({"wrong": "field"}))
    assert _Question("fake", caller).run(SOURCE) is None
    assert len(caller.prompts) == _Question.ATTEMPTS


def test_a_caller_that_raises_does_not_crash_the_service():
    caller = _Replies(ConnectionError("no network"), ConnectionError("no network"))
    assert _Question("fake", caller).run(SOURCE) is None


def test_a_service_with_no_caller_gives_none():
    assert _Question("fake", None).run(SOURCE) is None


def test_a_good_answer_is_saved_and_reused_without_asking_again(tmp_path):
    cache = ResponseCache(str(tmp_path))
    first = _Replies(GOOD)
    assert _Question("fake", first, "gpt-test", 0.0, cache).run(SOURCE) == {"answer": "yes"}
    second = _Replies()
    reused = _Question("fake", second, "gpt-test", 0.0, cache).run(SOURCE)
    assert reused["answer"] == "yes"
    assert second.prompts == []


def test_a_different_payload_is_not_answered_from_the_saved_answer(tmp_path):
    cache = ResponseCache(str(tmp_path))
    _Question("fake", _Replies(GOOD), "gpt-test", 0.0, cache).run(SOURCE)
    caller = _Replies(json.dumps({"answer": "no"}))
    assert _Question("fake", caller, "gpt-test", 0.0, cache).run({"industry": "Banking"}) == {"answer": "no"}


def test_a_failed_run_saves_nothing(tmp_path):
    cache = ResponseCache(str(tmp_path))
    _Question("fake", _Replies(None, None), "gpt-test", 0.0, cache).run(SOURCE)
    assert _Question("fake", _Replies(GOOD), "gpt-test", 0.0, cache).run(SOURCE) == {"answer": "yes"}


def test_redact_names_replaces_the_name_and_mr_style_references():
    service = _Question("fake", None)
    text = service._redact_names("Mr Tan and Daniel Tan Wei Ming met Tanya.", ["Daniel Tan Wei Ming"], ["Mr", "Mrs"])
    assert text == "the client and the client the client the client the client met Tanya."


def test_build_prompt_spells_out_the_schema_and_the_data():
    prompt = _Question("fake", None)._build_prompt("Follow the rules.", '{"a": 1}', SCHEMA)
    assert prompt.startswith("Follow the rules.")
    assert 'top-level keys are "answer"' in prompt
    assert 'DATA:\n{"a": 1}' in prompt


def test_prompt_version_is_read_from_the_prompt_file():
    service = _Question("fake", None)
    assert service._prompt_version("# prompt_version: research-v3\nText") == "research-v3"
    assert service._prompt_version("No version line") == "unknown"


def test_a_failed_question_prints_nothing(capsys):
    assert _Question("fake", _Replies(None, None)).run(SOURCE) is None
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
