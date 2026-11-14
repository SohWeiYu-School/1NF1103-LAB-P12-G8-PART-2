"""ResearchAI: searches trusted sites for published reports on financial crime in a sector."""

import logging
import os
from datetime import datetime, timezone
from typing import Callable

from app.ai.ai_service import AIService
from app.ai.response_cache import ResponseCache

logger = logging.getLogger(__name__)


class ResearchAI(AIService):
    """Finds published reports (FATF, MAS, ...) for the client's industry and country.

    The AI sees only the industry and the country. The search is asked once, not retried,
    because a web search is the expensive kind of question.
    source is {"case": {...}, "domains": [the trusted sites the search is limited to]}.
    """

    PROMPT_NAME: str = "research"
    SCHEMA_NAME: str = "research_response"
    ALLOWED_FIELDS: list[str] = ["industry", "country"]
    ATTEMPTS: int = 1

    def __init__(self, provider: str = "", ai_caller: Callable | None = None, model: str = "", temperature: float = 0.0,
                 response_cache: ResponseCache | None = None, max_reports: int = 8, max_excerpts: int = 5) -> None:
        super().__init__(provider, ai_caller, model, temperature, response_cache)
        self.__max_reports: int = max_reports
        self.__max_excerpts: int = max_excerpts

    def _payload(self, source: dict) -> dict:
        """Only the industry and the country. The country falls back to where the client lives."""
        case = source.get("case") or {}
        payload = {field: case[field] for field in ResearchAI.ALLOWED_FIELDS if field in case}
        if "country" not in payload:
            payload["country"] = case.get("country_of_residence", "Singapore")
        return payload

    def _fill_prompt(self, template: str, source: dict, payload: dict) -> str:
        return (super()._fill_prompt(template, source, payload)
                .replace("{trusted_sources}", ", ".join(source.get("domains") or []))
                .replace("{max_reports}", str(self.__max_reports))
                .replace("{max_excerpts}", str(self.__max_excerpts)))

    def _options(self, source: dict) -> dict:
        return {"web_search": True, "domains": source.get("domains") or [], "schema_name": self.SCHEMA_NAME}

    def _prepare(self, data: dict) -> dict:
        # Cut to the limits first, so an over-long reply can still pass the schema.
        return self.__trim_reports(data)

    def _post_process(self, data: dict, options: dict | None = None) -> dict:
        """Add the pages the search really opened, the report ids, clean excerpts, the time and the model."""
        response = (options or {}).get("raw_response")
        answered_by_openai = response is None or hasattr(response, "output")
        sources = self.__api_sources(response) if response is not None else []
        if not sources and not answered_by_openai:
            # Gemini often gives no search details with a structured reply. Use the report links
            # themselves, so the trusted-site rule can still be applied to them.
            sources = [{"url": report["url"], "title": report.get("title", report["url"])}
                       for report in data.get("reports", []) if report.get("url")]
        if not sources:
            self._warnings.append("Research: web search returned no sources — results may not be grounded.")
        data = self.__strip_excerpts(self.__add_report_ids(data))
        data["api_sources"] = sources
        data["retrieved_at"] = datetime.now(timezone.utc).isoformat()
        data["model"] = ((options or {}).get("answered_by")
                         or (self._model if answered_by_openai
                             else os.getenv("GEMINI_SEARCH_MODEL", "gemini-3.8-flash")))
        return data

    def __trim_reports(self, data: dict) -> dict:
        """Keep at most max_reports reports and max_excerpts excerpts each. Year text becomes a number."""
        reports = data.get("reports", [])
        if not isinstance(reports, list):
            return data
        if len(reports) > self.__max_reports:
            warning = f"AI returned {len(reports)} reports; kept first {self.__max_reports} per policy."
            logger.warning(warning)
            self._warnings.append(warning)
            reports = reports[:self.__max_reports]
        for report in reports:
            if not isinstance(report, dict):
                continue
            excerpts = report.get("excerpts", [])
            if len(excerpts) > self.__max_excerpts:
                report["excerpts"] = excerpts[:self.__max_excerpts]
            if isinstance(report.get("year"), str):
                try:
                    report["year"] = int(report["year"])
                except (ValueError, TypeError):
                    pass
        return {**data, "reports": reports}

    def __add_report_ids(self, data: dict) -> dict:
        """Number the reports R1, R2, ... This is done by code, not by the AI."""
        for number, report in enumerate(data.get("reports", []), 1):
            report["report_id"] = f"R{number}"
        return data

    def __strip_excerpts(self, data: dict) -> dict:
        """Remove the quote marks and spaces the AI puts around each excerpt."""
        quote_marks = '"“”‘’\''
        for report in data.get("reports", []):
            report["excerpts"] = [excerpt.strip(quote_marks).strip() for excerpt in report.get("excerpts", [])]
        return data

    def __api_sources(self, response: object) -> list[dict]:
        """The pages the web search really opened, as {url, title}, with no repeats."""
        seen: set[str] = set()
        sources: list[dict] = []

        def add(url: str | None, title: str | None) -> None:
            if url and url not in seen:
                seen.add(url)
                sources.append({"url": url, "title": title or url})

        if not hasattr(response, "output"):
            # A Gemini response: the pages are in the grounding details
            try:
                for candidate in getattr(response, "candidates", None) or []:
                    grounding = getattr(candidate, "grounding_metadata", None)
                    for chunk in getattr(grounding, "grounding_chunks", None) or []:
                        web = getattr(chunk, "web", None)
                        add(getattr(web, "uri", None), getattr(web, "title", None))
            except Exception as error:
                logger.warning("ResearchAI: could not read the Gemini search details: %s", repr(error))
            return sources

        for item in response.output:
            # First place to look: the sources of each search call
            if item.type == "web_search_call":
                action = getattr(item, "action", None)
                for source in getattr(action, "sources", None) or []:
                    add(getattr(source, "url", None), None)
            # Second place: the links cited inside the reply text
            if item.type == "message":
                for block in item.content:
                    if block.type != "output_text":
                        continue
                    for annotation in getattr(block, "annotations", []):
                        if annotation.type == "url_citation":
                            add(annotation.url, annotation.title)
        return sources
