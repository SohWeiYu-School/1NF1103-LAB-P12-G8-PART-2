"""The AI caller functions, with made-up clients. No network."""

from types import SimpleNamespace

from app.ai.ai_caller import gemini_caller, gemini_schema, openai_caller, with_fallback

SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}}


class _FakeOpenAI:
    """Stands in for OpenAI(): records each request and returns a fixed reply."""

    def __init__(self, reply='{"answer": "yes"}', error=None, refuse_temperature=False):
        self.requests = []
        self.reply, self.error, self.refuse_temperature = reply, error, refuse_temperature
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.responses = SimpleNamespace(create=self._search)

    def _check(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        if self.refuse_temperature and "temperature" in request:
            raise ValueError("Unsupported value: 'temperature' does not support 0")

    def _chat(self, **request):
        self._check(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])

    def _search(self, **request):
        self._check(request)
        return SimpleNamespace(output_text=self.reply, output=[])


def test_openai_caller_returns_the_reply_text():
    client = _FakeOpenAI()
    options = {"model": "gpt-test"}
    assert openai_caller(client)("Question?", SCHEMA, options) == '{"answer": "yes"}'
    request = client.requests[0]
    assert request["model"] == "gpt-test"
    assert request["temperature"] == 0
    assert request["messages"] == [{"role": "user", "content": "Question?"}]
    assert request["response_format"]["json_schema"]["schema"] == SCHEMA
    assert options["answered_by"] == "gpt-test"


def test_openai_caller_without_a_schema_asks_for_any_json_object():
    client = _FakeOpenAI()
    openai_caller(client)("Question?", None, {})
    assert client.requests[0]["response_format"] == {"type": "json_object"}


def test_a_connection_failure_gives_none_not_a_crash():
    client = _FakeOpenAI(error=ConnectionError("no network"))
    assert openai_caller(client)("Question?", SCHEMA, {}) is None


def test_a_model_that_refuses_temperature_zero_is_asked_again_without_it():
    client = _FakeOpenAI(refuse_temperature=True)
    assert openai_caller(client)("Question?", SCHEMA, {}) == '{"answer": "yes"}'
    assert "temperature" in client.requests[0] and "temperature" not in client.requests[1]


def test_a_web_search_question_can_be_limited_to_given_sites():
    client = _FakeOpenAI()
    options = {"web_search": True, "domains": ["fatf-gafi.org"], "schema_name": "research_response"}
    openai_caller(client)("Find reports", SCHEMA, options)
    request = client.requests[0]
    assert request["tools"] == [{"type": "web_search", "filters": {"allowed_domains": ["fatf-gafi.org"]}}]
    assert request["text"]["format"]["strict"] is True
    assert request["text"]["format"]["name"] == "research_response"
    assert options["raw_response"].output == []


def test_documents_are_sent_as_message_parts_with_a_system_message():
    client = _FakeOpenAI()
    parts = [{"type": "text", "text": "<document>payslip</document>"}]
    openai_caller(client)("Read the documents", SCHEMA, {"parts": parts})
    assert client.requests[0]["messages"] == [{"role": "system", "content": "Read the documents"},
                                              {"role": "user", "content": parts}]


class _FakeGemini:
    def __init__(self, reply='{"answer": "yes"}', error=None):
        self.requests = []
        self.reply, self.error = reply, error
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.reply)


def test_gemini_caller_returns_the_reply_text():
    client = _FakeGemini()
    options = {}
    assert gemini_caller(client, model="gemini-test")("Question?", SCHEMA, options) == '{"answer": "yes"}'
    assert client.requests[0]["model"] == "gemini-test"
    assert options["answered_by"] == "gemini-test"


def test_gemini_caller_failure_gives_none():
    assert gemini_caller(_FakeGemini(error=RuntimeError("quota")))("Question?", SCHEMA, {}) is None


def test_gemini_caller_cannot_read_attached_documents():
    client = _FakeGemini()
    assert gemini_caller(client)("Read", SCHEMA, {"parts": []}) is None
    assert client.requests == []


def test_gemini_schema_drops_unsupported_keys_and_marks_nullable_types():
    schema = {"$schema": "x", "title": "T", "type": "object", "additionalProperties": False,
              "properties": {"title": {"type": ["string", "null"]}, "year": {"type": "integer"}}}
    assert gemini_schema(schema) == {"type": "object", "properties": {
        "title": {"type": "string", "nullable": True}, "year": {"type": "integer"}}}


def test_with_fallback_uses_the_first_caller_that_answers():
    asked = []

    def silent(prompt, schema, options):
        asked.append("first")
        return None

    def answers(prompt, schema, options):
        asked.append("second")
        return "reply"

    def never(prompt, schema, options):
        asked.append("third")
        return "unused"

    assert with_fallback(silent, answers, never)("Question?", SCHEMA, {}) == "reply"
    assert asked == ["first", "second"]


def test_with_fallback_gives_none_when_nobody_answers():
    assert with_fallback(lambda p, s, o: None, lambda p, s, o: None)("Question?", SCHEMA, {}) is None


def test_with_fallback_does_not_ask_the_second_caller_when_the_first_answers():
    asked = []
    with_fallback(lambda p, s, o: "reply", lambda p, s, o: asked.append("second"))("Question?", SCHEMA, {})
    assert asked == []


def test_a_caller_says_whether_it_can_be_used_and_which_model_it_uses(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert openai_caller().available() is False
    assert openai_caller(_FakeOpenAI()).available() is True
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert openai_caller().available() is True
    assert openai_caller(model="gpt-test").model_name() == "gpt-test"


def test_a_fallback_chain_answers_for_its_first_caller(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_AI_API_KEY", raising=False)
    chain = with_fallback(openai_caller(model="gpt-test"), gemini_caller(_FakeGemini()))
    assert chain.available() is False            # the main brand has no key
    assert chain.model_name() == "gpt-test"


def test_gemini_schema_keeps_field_names_that_look_like_unsupported_keys():
    schema = {"type": "object", "properties": {"title": {"type": "string", "title": "Report title"}}}
    assert gemini_schema(schema) == {"type": "object", "properties": {"title": {"type": "string"}}}


def test_gemini_schema_can_drop_required_at_every_level():
    schema = {"type": "object", "required": ["reports"], "properties": {"reports": {
        "type": "array", "items": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}}}}}}
    cleaned = gemini_schema(schema, {"required"})
    assert "required" not in cleaned
    assert "required" not in cleaned["properties"]["reports"]["items"]
