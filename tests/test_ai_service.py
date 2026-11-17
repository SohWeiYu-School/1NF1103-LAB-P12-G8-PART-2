"""AIService: what every AI question shares. The AI replies are hard-coded; no network."""

import json

import pytest

from app.ai.ai_service import AIService

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


def _with(saved, source=SOURCE):
    return {**source, "saved_replies": saved}


class _QuestionV2(_Question):
    def _load_prompt(self, name: str) -> str:
        return "# prompt_version: v2\nAnswer about {payload_json}"


def test_a_good_answer_is_kept_in_the_saved_replies_and_reused_without_asking_again():
    saved = {}
    first = _Replies(GOOD)
    assert _Question("fake", first, "gpt-test").run(_with(saved)) == {"answer": "yes"}
    assert saved["test_question"]["reply"] == {"answer": "yes"}
    second = _Replies()
    assert _Question("fake", second, "gpt-test").run(_with(saved)) == {"answer": "yes"}
    assert second.prompts == []


def test_without_saved_replies_the_ai_is_always_asked():
    first, second = _Replies(GOOD), _Replies(GOOD)
    _Question("fake", first, "gpt-test").run(SOURCE)
    _Question("fake", second, "gpt-test").run(SOURCE)
    _Question("fake", _Replies(GOOD), "gpt-test").run(_with(None))
    assert len(first.prompts) == 1 and len(second.prompts) == 1


def test_a_reused_reply_is_a_copy_the_caller_cannot_change():
    saved = {}
    _Question("fake", _Replies(GOOD), "gpt-test").run(_with(saved))
    reused = _Question("fake", _Replies(), "gpt-test").run(_with(saved))
    reused["answer"] = "changed"
    assert saved["test_question"]["reply"] == {"answer": "yes"}


def test_a_different_payload_model_or_prompt_version_asks_again():
    for service_class, model, source in ((_Question, "gpt-test", {"industry": "Banking"}),
                                         (_Question, "other-model", SOURCE),
                                         (_QuestionV2, "gpt-test", SOURCE)):
        saved = {}
        _Question("fake", _Replies(GOOD), "gpt-test").run(_with(saved))
        caller = _Replies(json.dumps({"answer": "no"}))
        assert service_class("fake", caller, model).run(_with(saved, source)) == {"answer": "no"}
        assert len(caller.prompts) == 1
        assert saved["test_question"]["reply"] == {"answer": "no"}      # the new answer replaces the old one


def test_a_saved_reply_that_breaks_the_schema_is_asked_again(caplog):
    saved = {}
    _Question("fake", _Replies(GOOD), "gpt-test").run(_with(saved))
    saved["test_question"]["reply"] = {"wrong": "field"}
    caller = _Replies(GOOD)
    with caplog.at_level("WARNING"):
        assert _Question("fake", caller, "gpt-test").run(_with(saved)) == {"answer": "yes"}
    assert len(caller.prompts) == 1
    assert "no longer follows the schema" in caplog.text


def test_a_damaged_saved_entry_is_asked_again():
    for entry in ("text", {"question": "x"}, {"question": "x", "reply": "text"}, None):
        caller = _Replies(GOOD)
        assert _Question("fake", caller, "gpt-test").run(_with({"test_question": entry})) == {"answer": "yes"}
        assert len(caller.prompts) == 1


class _FallbackReplies(_Replies):
    """A made-up caller whose answers come from a fallback model, as with_fallback reports it."""

    def __call__(self, prompt, schema, options):
        options["answered_by"] = "fallback-model"
        return super().__call__(prompt, schema, options)


def test_an_answer_from_a_fallback_model_is_used_but_not_saved():
    saved = {}
    assert _Question("fake", _FallbackReplies(GOOD), "gpt-test").run(_with(saved)) == {"answer": "yes"}
    assert saved == {}
    later = _Replies(json.dumps({"answer": "from the main model"}))
    assert _Question("fake", later, "gpt-test").run(_with(saved)) == {"answer": "from the main model"}
    assert len(later.prompts) == 1                       # asked again: the fallback's answer was not kept


def test_an_answer_from_the_services_own_model_is_saved():
    class _OwnModel(_Replies):
        def __call__(self, prompt, schema, options):
            options["answered_by"] = "gpt-test"
            return super().__call__(prompt, schema, options)
    saved = {}
    _Question("fake", _OwnModel(GOOD), "gpt-test").run(_with(saved))
    later = _Replies()
    assert _Question("fake", later, "gpt-test").run(_with(saved))["answer"] == "yes"
    assert later.prompts == []                           # reused from the saved answer


def test_a_failed_run_saves_nothing():
    saved = {}
    _Question("fake", _Replies(None, None), "gpt-test").run(_with(saved))
    assert saved == {}
    assert _Question("fake", _Replies(GOOD), "gpt-test").run(_with(saved)) == {"answer": "yes"}


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
