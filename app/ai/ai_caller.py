"""The AI caller functions: one way to ask a question, whichever AI brand answers it.

An AI caller is a function  caller(prompt, schema, options) -> reply text or None.
main.py picks the brand by building the caller it wants and hands it to App:

    caller = with_fallback(openai_caller(OpenAI()), gemini_caller(genai.Client()))

Every AIService only ever sees "a caller", so no AI class knows which brand it is using.

options (all optional):
    model         the model to use instead of the caller's own
    web_search    True to let the AI search the web (the reply must then follow the schema strictly)
    domains       sites the web search is limited to (OpenAI only; Gemini cannot filter)
    system        text sent as the system message (used with "parts")
    parts         message parts with documents attached (text, images, scanned PDFs)
    schema_name   the name the schema is sent under
On return the caller adds:
    options["raw_response"]   the brand's full response object (the web sources are read from it)
    options["answered_by"]    the model that actually answered
"""

import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)

AICaller = Callable[[str, dict, dict], "str | None"]

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_GEMINI_SEARCH_MODEL = "gemini-3.8-flash"
GEMINI_UNSUPPORTED_SCHEMA_KEYS = ("$schema", "$id", "title", "additionalProperties")


def openai_caller(client: object = None, model: str = "", search_model: str = "") -> AICaller:
    """An AI caller that asks OpenAI. client is an OpenAI() object; if none is given, one is
    created from OPENAI_API_KEY the first time a question is asked.
    A web search uses search_model (or OPENAI_RESEARCH_MODEL), so research can use a model that
    supports limiting a search to given sites; with neither set it uses the normal model."""
    state = {"client": client}

    def connect() -> object:
        if state["client"] is None:
            from openai import OpenAI
            state["client"] = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY"))
        return state["client"]

    def call(prompt: str, schema: dict | None = None, options: dict | None = None) -> str | None:
        options = options if options is not None else {}
        use_model = options.get("model") or model or os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        if options.get("web_search"):
            use_model = search_model or os.getenv("OPENAI_RESEARCH_MODEL") or use_model
        name = options.get("schema_name") or "response"
        try:
            api = connect()
            if options.get("web_search"):
                tool = {"type": "web_search"}
                if options.get("domains"):
                    tool["filters"] = {"allowed_domains": options["domains"]}
                response = api.responses.create(
                    model=use_model, input=prompt, tools=[tool], tool_choice="required",
                    include=["web_search_call.action.sources"],
                    text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}})
                text = response.output_text
            else:
                response_format = ({"type": "json_schema",
                                    "json_schema": {"name": name, "schema": schema, "strict": False}}
                                   if schema else {"type": "json_object"})
                if options.get("parts") is not None:
                    messages = [{"role": "system", "content": options.get("system") or prompt},
                                {"role": "user", "content": options["parts"]}]
                else:
                    messages = [{"role": "user", "content": prompt}]
                response = api.chat.completions.create(model=use_model, response_format=response_format,
                                                       messages=messages)
                text = response.choices[0].message.content
        except Exception as error:   # no key, no network, a refused request: all mean "no answer"
            logger.warning("openai_caller failed: %s", repr(error))
            return None
        options["raw_response"] = response
        options["answered_by"] = use_model
        return text

    # What the caller tells whoever holds it, without them knowing the brand:
    call.available = lambda: state["client"] is not None or bool(
        os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY"))
    call.model_name = lambda: model or os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    call.search_model_name = lambda: search_model or os.getenv("OPENAI_RESEARCH_MODEL") or call.model_name()
    return call


def gemini_schema(node: object, unsupported: tuple | set = GEMINI_UNSUPPORTED_SCHEMA_KEYS) -> object:
    """A JSON Schema in the form Gemini accepts: unsupported keys removed, and a nullable type
    list (["string", "null"]) turned into {type, nullable: true}."""
    if isinstance(node, list):
        return [gemini_schema(item, unsupported) for item in node]
    if not isinstance(node, dict):
        return node
    result = {}
    for key, value in node.items():
        if key in unsupported:
            continue
        if key == "type" and isinstance(value, list):
            non_null = [kind for kind in value if kind != "null"]
            if non_null:
                result["type"] = non_null[0]
                result["nullable"] = True
            continue
        # "properties" keys are field names (e.g. "title", "url"): never filter those
        if key == "properties" and isinstance(value, dict):
            result["properties"] = {name: gemini_schema(schema, unsupported) for name, schema in value.items()}
            continue
        result[key] = gemini_schema(value, unsupported)
    return result


def gemini_caller(client: object = None, model: str = "", search_model: str = "",
                  unsupported_schema_keys: tuple | set = GEMINI_UNSUPPORTED_SCHEMA_KEYS) -> AICaller:
    """An AI caller that asks Google Gemini. client is a genai.Client() object; if none is given,
    one is created from GEMINI_API_KEY the first time a question is asked."""
    state = {"client": client}

    def connect() -> object:
        if state["client"] is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set")
            from google import genai
            state["client"] = genai.Client(api_key=api_key)
        return state["client"]

    def call(prompt: str, schema: dict | None = None, options: dict | None = None) -> str | None:
        options = options if options is not None else {}
        if options.get("parts") is not None:
            logger.warning("gemini_caller: documents attached to a message are not supported")
            return None
        searching = bool(options.get("web_search"))
        if searching:
            use_model = search_model or os.getenv("GEMINI_SEARCH_MODEL") or DEFAULT_GEMINI_SEARCH_MODEL
            if options.get("domains"):
                logger.warning("gemini_caller: Gemini cannot limit a search to given sites; searching all sources")
        else:
            use_model = model or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        try:
            from google.genai import types
            tools = [types.Tool(google_search=types.GoogleSearch())] if searching else None
            config = types.GenerateContentConfig(
                tools=tools, response_mime_type="application/json",
                response_schema=gemini_schema(schema, unsupported_schema_keys) if schema else None)
            response = connect().models.generate_content(model=use_model, contents=prompt, config=config)
            text = response.text
        except Exception as error:
            logger.warning("gemini_caller failed: %s", repr(error))
            return None
        options["raw_response"] = response
        options["answered_by"] = use_model
        return text

    call.available = lambda: state["client"] is not None or bool(os.getenv("GEMINI_API_KEY"))
    call.model_name = lambda: model or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    call.search_model_name = lambda: search_model or os.getenv("GEMINI_SEARCH_MODEL") or DEFAULT_GEMINI_SEARCH_MODEL
    return call


def with_fallback(*callers: AICaller) -> AICaller:
    """One AI caller made of several: each is asked in turn until one gives an answer."""

    def call(prompt: str, schema: dict | None = None, options: dict | None = None) -> str | None:
        options = options if options is not None else {}
        for position, caller in enumerate(callers):
            text = caller(prompt, schema, options)
            if text is not None:
                return text
            if position < len(callers) - 1:
                logger.warning("with_fallback: AI caller %d gave no answer, trying the next one", position + 1)
        return None

    # The first caller is the main one: it decides whether AI can be used at all and which
    # model name saved answers are filed under.
    call.available = lambda: bool(callers) and getattr(callers[0], "available", lambda: True)()
    call.model_name = lambda: getattr(callers[0], "model_name", lambda: "")() if callers else ""
    call.search_model_name = lambda: (getattr(callers[0], "search_model_name", call.model_name)()
                                      if callers else "")
    return call
