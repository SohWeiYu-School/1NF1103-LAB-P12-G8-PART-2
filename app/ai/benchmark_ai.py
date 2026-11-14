"""BenchmarkAI: what a typical person with this career would be worth."""

import json
from typing import Callable

from app.ai.ai_service import AIService
from app.ai.response_cache import ResponseCache


class BenchmarkAI(AIService):
    """Asks for the expected wealth of peers with the same career.

    The AI never sees the client's declared figures: only the fields in ALLOWED_FIELDS,
    plus the economy the forecast found (market % changes and country listings).
    """

    ALLOWED_FIELDS: list[str] = ["occupation", "industry", "age", "career_start_year", "country"]
    PROMPT_NAME: str = "benchmark"
    SCHEMA_NAME: str = "benchmark"

    def __init__(self, provider: str = "", ai_caller: Callable | None = None, model: str = "", temperature: float = 0.0,
                 response_cache: ResponseCache | None = None) -> None:
        super().__init__(provider, ai_caller, model, temperature, response_cache)

    def _payload(self, source: dict) -> dict:
        """Only the allowlisted career fields. source is {"client": {...}, "economy": {...} or None}."""
        client = source.get("client") or {}
        return {field: client[field] for field in BenchmarkAI.ALLOWED_FIELDS if field in client}

    def _fill_prompt(self, template: str, source: dict, payload: dict) -> str:
        economy = source.get("economy")
        economy_text = json.dumps(economy, indent=1, ensure_ascii=False) if economy else "not available"
        return (self._without_notes(template)
                .replace("{client_data}", str(payload)).replace("{economy}", economy_text))

    def _cache_payload(self, source: dict, payload: dict) -> dict:
        # The same career in a different economy is a different question.
        return {**payload, "economy": source.get("economy")}
