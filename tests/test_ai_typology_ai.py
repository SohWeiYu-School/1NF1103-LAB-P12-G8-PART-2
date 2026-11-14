"""TypologyAI: career fields and reports go in (no links), checked typologies come out.
The AI replies are hard-coded; no network."""

import json

from app.ai.typology_ai import TypologyAI
from tests import fake_ai

CASE = {"client_ref": "ID-2233", "occupation": "COO", "industry": "Shipping", "age": 51,
        "career_start_year": 1998, "country": "SG", "declaration_text": "My secret story."}
CATEGORIES = {"TRADE_BASED_ML": "Trade-based money laundering", "TAX_EVASION": "Tax evasion"}


class _Caller:
    def __init__(self, *replies):
        self.replies, self.prompts, self.schemas = list(replies), [], []

    def __call__(self, prompt, schema, options):
        self.prompts.append(prompt)
        self.schemas.append(schema)
        return self.replies.pop(0)


def _reply(count=1, category="TRADE_BASED_ML"):
    data = fake_ai.typologies()
    first = data["sector_typologies"][0]
    data["sector_typologies"] = [{**first, "typology_id": f"typology_{number}", "crime_category": category}
                                 for number in range(count)]
    return json.dumps(data)


def _run(caller, research=None, **limits):
    service = TypologyAI("fake", caller, "gpt-test", 0.0, None, **limits)
    source = {"case": CASE, "research": fake_ai.research() if research is None else research,
              "categories": CATEGORIES}
    return service.run(source), service.warnings()


def test_good_typologies_are_returned_with_the_model_recorded():
    result, warnings = _run(_Caller(_reply()))
    assert len(result["sector_typologies"]) == 1
    assert result["model"] == "gpt-test"
    assert warnings == []


def test_the_prompt_holds_the_reports_but_not_their_links():
    caller = _Caller(_reply())
    _run(caller)
    prompt = caller.prompts[0]
    assert "FATF" in prompt and "Trade-Based Money Laundering" in prompt
    assert "fatf-gafi.org" not in prompt


def test_the_prompt_holds_the_career_but_not_the_declaration_or_reference():
    caller = _Caller(_reply())
    _run(caller)
    assert "Shipping" in caller.prompts[0]
    assert "secret story" not in caller.prompts[0]
    assert "ID-2233" not in caller.prompts[0]


def test_with_no_reports_the_prompt_gets_an_empty_list():
    caller = _Caller(_reply())
    _run(caller, research={"reports": []})
    assert "FATF" not in caller.prompts[0]


def test_the_crime_category_must_be_one_of_the_given_categories():
    caller = _Caller(_reply(category="MADE_UP_CATEGORY"), _reply())
    result, _ = _run(caller)
    item = caller.schemas[0]["properties"]["sector_typologies"]["items"]
    assert item["properties"]["crime_category"]["enum"] == ["TRADE_BASED_ML", "TAX_EVASION"]
    assert result is not None and len(caller.prompts) == 2


def test_six_typologies_are_cut_to_five_with_a_warning():
    result, warnings = _run(_Caller(_reply(count=6)))
    assert len(result["sector_typologies"]) == 5
    assert any("kept first 5" in warning for warning in warnings)


def test_the_limit_can_be_changed():
    result, _ = _run(_Caller(_reply(count=4)), max_patterns=2)
    assert len(result["sector_typologies"]) == 2


def test_one_malformed_reply_then_a_good_one_succeeds_with_no_warnings():
    result, warnings = _run(_Caller(json.dumps({"wrong": "field"}), _reply()))
    assert result is not None
    assert warnings == []


def test_two_malformed_replies_give_none():
    bad = json.dumps({"wrong": "field"})
    result, warnings = _run(_Caller(bad, bad))
    assert result is None
    assert warnings == []


def test_no_connection_gives_none():
    result, _ = _run(_Caller(None, None))
    assert result is None
