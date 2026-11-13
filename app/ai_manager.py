import logging
import os
from typing import Callable

import jsonschema
from app import utilities
from app.ai import ai_caller
from app.ai.benchmark_ai import BenchmarkAI
from app.ai.document_ai import DocumentAI
from app.ai.forecast_ai import ForecastAI
from app.ai.research_ai import ResearchAI
from app.ai.typology_ai import TypologyAI
from app.ai.response_cache import ResponseCache
from app.utilities import cache_check, cache_dir, cache_write, client, forecast_settings, has_api_key, model


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared Functions
# ---------------------------------------------------------------------------
# Single entry point for all web search AI calls — tries OpenAI first, falls back to Gemini if OpenAI fails.
# Gemini grounding requires a paid API key; domain filtering is OpenAI-only.
def _ai_search_pipeline(
    prompt: str,
    schema: dict,
    domains: list | None = None,
) -> tuple[str | None, object | None]:
    text, response = _openai_search_response(prompt, model(), schema, domains)
    if text is not None:
        logger.info("_ai_search_pipeline: OpenAI search succeeded")
        return text, response
    logger.warning("_ai_search_pipeline: OpenAI search failed, falling back to Gemini")
    gemini_search_model = os.getenv("GEMINI_SEARCH_MODEL", "gemini-3.8-flash")
    # TODO: test Gemini search grounding end-to-end once Google grounding service is stable
    return _gemini_search_response(prompt, gemini_search_model, schema, domains)

# Single entry point for all chat completion AI calls — tries OpenAI first, falls back to Gemini if OpenAI fails
def _ai_chat_completion_pipeline(prompt: str, schema: dict | None = None) -> str | None:
    result = _openai_completion_response(prompt, model(), schema)
    if result is not None:
        logger.info("_ai_chat_completion_pipeline: OpenAI completion succeeded")
        return result
    logger.warning("_ai_chat_completion_pipeline: OpenAI failed, falling back to Gemini")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    return _gemini_completion_response(prompt, gemini_model, schema)

# ============================================================================
# 1. Shared helpers - used by every section below
# ============================================================================
# The calls to OpenAI and Gemini live in app/ai/ai_caller.py (openai_caller, gemini_caller).
# The functions below keep their old names and pass each call on to those callers.

def _openai() -> ai_caller.AICaller:
    try:
        return ai_caller.openai_caller(client())
    except Exception as exc:   # no API key: every question then gets "no answer"
        logger.warning("OpenAI is not available: %s", repr(exc))
        return lambda prompt, schema=None, options=None: None


def _gemini(model: str = "", search_model: str = "") -> ai_caller.AICaller:
    unsupported = set(utilities.policy().get("gemini_unsupported_schema_keys",
                                             ai_caller.GEMINI_UNSUPPORTED_SCHEMA_KEYS))
    return ai_caller.gemini_caller(None, model, search_model, unsupported)


def _openai_completion_response(prompt: str, model: str, schema: dict | None = None) -> str | None:
    """Plain chat call. Returns the reply text, or None if the call fails."""
    return _openai()(prompt, schema, {"model": model})


def _convert_schema_for_gemini(node, unsupported: set | None = None):
    """A JSON Schema in the form Gemini accepts."""
    if unsupported is None:
        unsupported = set(utilities.policy().get("gemini_unsupported_schema_keys",
                                                 ai_caller.GEMINI_UNSUPPORTED_SCHEMA_KEYS))
    return ai_caller.gemini_schema(node, unsupported)


def _gemini_completion_response(prompt: str, model: str, schema: dict | None = None) -> str | None:
    """Google Gemini chat call (no web search). Returns the reply text, or None if the call fails."""
    return _gemini(model=model)(prompt, schema, {})


def _openai_search_response(
    prompt: str,
    model: str,
    schema: dict,
    domains: list | None = None,
) -> tuple[str | None, object | None]:
    """Web-search call. Returns (reply text, raw response), or (None, None) if it fails."""
    options = {"model": model, "web_search": True, "domains": domains, "schema_name": "research_response"}
    text = _openai()(prompt, schema, options)
    return (text, options.get("raw_response")) if text is not None else (None, None)


def _gemini_search_response(
    prompt: str,
    model: str,
    schema: dict,
    domains: list | None = None,
) -> tuple[str | None, object | None]:
    """Google Gemini call with Google Search. Returns (reply text, raw response), or (None, None)."""
    options = {"web_search": True, "domains": domains}
    text = _gemini(search_model=model)(prompt, schema, options)
    return (text, options.get("raw_response")) if text is not None else (None, None)

# ---------------------------------------------------------------------------
# Adapters: the AIService classes in app/ai do the work. They are handed this
# caller and this cache, which pass each call on to the functions above, so the
# old function names in this file still work until App creates the services itself.
# ---------------------------------------------------------------------------

def _pipeline_caller(prompt: str, schema: dict | None = None, options: dict | None = None) -> str | None:
    """An ai_caller: OpenAI first, Gemini as the fallback."""
    options = options if options is not None else {}
    if options.get("web_search"):
        text, response = _ai_search_pipeline(prompt, schema=schema, domains=options.get("domains"))
        options["raw_response"] = response
        return text
    if options.get("parts") is not None:
        return _openai_document_response(options.get("system") or prompt, options["parts"],
                                         options.get("model"), schema)
    return _ai_chat_completion_pipeline(prompt, schema)


class _ModuleCache(ResponseCache):
    """The ResponseCache for the cache folder in use, reached through this file's cache functions."""

    def __init__(self) -> None:
        super().__init__(cache_dir())

    def key(self, kind: str, payload: dict, model: str, prompt_version: str = "") -> str:
        return cache_check(kind, payload, prompt_version, model)[0]

    def get(self, kind: str, payload: dict, model: str, prompt_version: str = "") -> dict | None:
        return cache_check(kind, payload, prompt_version, model)[1]

    def put(self, kind: str, key: str, data: dict) -> None:
        cache_write(key, data, kind)


#Shared function that accepts (AI reponse & Schema) checking if the AI output matches the actaul schema
def validate_ai_response(data: dict, schema: dict) -> tuple[bool, str | None]:
    """Check an AI reply against a JSON schema. Returns (True, None) or (False, error)."""
    try:
        jsonschema.validate(instance=data, schema=schema)
        return True, None
    except jsonschema.ValidationError as exc:
        return False, exc.message
    except Exception as exc:
        return False, repr(exc)


# ============================================================================
# 2. Benchmark - expected wealth figures for a client profile
# ============================================================================

def get_ai_benchmark(client_data: dict, economy: dict | None = None) -> dict | None:
    """Entry point. Returns the benchmark dict, or None if the call fails.

    economy: the markets the forecast's Call 1 found for this client (logic_manager.economy_brief):
    yearly % changes and country listings only - no figures about the client.
    """
    service = BenchmarkAI("openai", _pipeline_caller, model(), 0.0, _ModuleCache())
    return service.run({"client": client_data, "economy": economy})


def build_benchmark_payload(client_data: dict) -> dict:
    """Keep only the fields the benchmark AI may see (CLAUDE.md rule 6)."""
    return {k: client_data[k] for k in BenchmarkAI.ALLOWED_FIELDS if k in client_data}


# ============================================================================
# 3. Research - search trusted sites for published ML/TF reports
# ============================================================================

def get_ai_research(case_input: dict) -> tuple[dict | None, list[str]]:
    """Entry point. Returns (research dict or None, warnings).

    The AI sees only the industry and the country. The search is limited to the trusted
    sites in config/policy.json.
    """
    policy = utilities.policy()
    service = ResearchAI("openai", _pipeline_caller, model(), 0.0, _ModuleCache(),
                         max_reports=policy.get("research_max_reports"),
                         max_excerpts=policy.get("research_max_excerpts_per_report"))
    data = service.run({"case": case_input, "domains": policy.get("trusted_sources", [])})
    return data, service.warnings()


# Single entry point for typology AI — main.py calls only this
def get_typologies(case_input: dict, research: dict | None = None) -> tuple[dict | None, list[str]]:
    """Entry point. Returns (typologies dict or None, warnings).

    The AI sees only the allowlisted profile fields and the research reports (no URLs).
    """
    service = TypologyAI("openai", _pipeline_caller, model(), 0.0, _ModuleCache(),
                         max_patterns=utilities.policy().get("typology_max_patterns", 5))
    data = service.run({"case": case_input, "research": research, "categories": typology_crime_categories()})
    return data, service.warnings()


def typology_crime_categories() -> dict:
    """{code: description} of the crime categories a typology may belong to (every one but HONEST)."""
    honest = forecast_settings()["honest_category"]
    return {code: text for code, text in utilities.vocabulary().get("crime_categories", {}).items()
            if code != honest}


# ============================================================================
# 5. Document auto-fill - reads uploaded client documents into form details
# ============================================================================

MAX_EXTRACT_DOCUMENTS = DocumentAI.MAX_DOCUMENTS


def _openai_document_response(prompt: str, parts: list[dict], mdl: str, schema: dict) -> str | None:
    """Chat call with documents attached (text, images, scanned PDFs). Returns the reply text or None."""
    return _openai()(prompt, schema, {"model": mdl, "parts": parts, "schema_name": "document_extract"})


def extract_client_details(documents: list[dict]) -> tuple[dict | None, list[str]]:
    """Entry point. Read uploaded documents and return (form details or None, warnings).

    The details follow app/schemas/document_extract.schema.json. Nothing is decided here:
    the officer reviews every pre-filled value before the client is saved.
    """
    service = DocumentAI("openai", _pipeline_caller, utilities.extract_model(), 0.0, _ModuleCache())
    readable = [d for d in documents if d.get("kind") in DocumentAI.READABLE_KINDS]
    if readable and not has_api_key():
        logger.warning("extract_client_details: no API key configured")
        service.run({"documents": [d for d in documents if d.get("kind") == "error"]})
        notes = service.warnings()
        if len(readable) > DocumentAI.MAX_DOCUMENTS:
            notes.append(f"Only the first {DocumentAI.MAX_DOCUMENTS} documents were read.")
        return None, notes
    data = service.run({"documents": documents})
    return data, service.warnings()


# ============================================================================
# 6. Forecasting - runs after the benchmark
# ============================================================================
# ForecastAI (app/ai/forecast_ai.py) runs Step 0 and Calls 1-4 and checks every reply.

FORECAST_STAGES = ForecastAI.STAGES


def _forecast_service() -> ForecastAI:
    """A ForecastAI with the forecasting settings from config/policy.json. Without an API key it
    is given no AI caller, so it can only use saved replies."""
    settings = {**forecast_settings(),
                "net_worth_documents": utilities.policy().get("breach_documents", {}).get("NET_WORTH")}
    caller = _pipeline_caller if has_api_key() else None
    return ForecastAI("openai", caller, model(), 0.0, _ModuleCache(), utilities.FORECAST_YEARS,
                      settings, utilities.vocabulary())


def run_onboarding_forecast(record: dict, cache: dict | None = None,
                            typologies: list[dict] | None = None,
                            on_step: Callable[[str], None] | None = None) -> dict:
    """Entry point. Run Step 0 and Calls 1-4 in order, stopping at the first failure.

    cache:      {piece_name: raw_text} of saved replies.
    typologies: the crime scan's verified sector typologies; Call 3 builds its crime types from them.
    on_step:    called with each stage name in FORECAST_STAGES as it starts (progress display).
    Returns {"ok", "failed_step", "results": {piece: result}, "forecast": {...}, "partial": {...}}.
    """
    return _forecast_service().run({"record": record, "cache": cache, "typologies": typologies,
                                    "on_step": on_step})
