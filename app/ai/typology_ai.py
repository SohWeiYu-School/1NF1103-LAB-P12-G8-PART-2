"""TypologyAI: the known patterns of financial crime for the client's sector."""

import json
import logging
from typing import Callable

from app.ai.ai_service import AIService

logger = logging.getLogger(__name__)


class TypologyAI(AIService):
    """Turns the research reports into sector typologies (known crime patterns).

    The AI sees only the allowlisted career fields and the reports, without their links.
    source is {"case": {...}, "research": {...} or None, "categories": {code: description}}.
    Each typology must belong to one of the given crime categories.
    """

    PROMPT_NAME: str = "typology"
    SCHEMA_NAME: str = "typology_response"
    ALLOWED_FIELDS: list[str] = ["occupation", "industry", "age", "career_start_year", "country"]
    REPORT_FIELDS: list[str] = ["report_id", "organisation", "title", "year", "summary", "excerpts"]

    def __init__(self, provider: str = "", ai_caller: Callable | None = None, model: str = "", temperature: float = 0.0,
                 max_patterns: int = 5) -> None:
        super().__init__(provider, ai_caller, model, temperature)
        self.__max_patterns: int = max_patterns

    def _payload(self, source: dict) -> dict:
        """The allowlisted career fields plus the reports (safe fields only, no links)."""
        case = source.get("case") or {}
        profile = {field: case[field] for field in TypologyAI.ALLOWED_FIELDS if field in case}
        if "country" not in profile:
            profile["country"] = case.get("country_of_residence", "Singapore")
        research = source.get("research")
        reports = self.__build_typology_reports(research) if research is not None else []
        return {**profile, "reports": reports}

    def _fill_prompt(self, template: str, source: dict, payload: dict) -> str:
        profile = {key: value for key, value in payload.items() if key != "reports"}
        categories = source.get("categories") or {}
        category_lines = "\n".join(f"        {code}: {text}" for code, text in categories.items())
        return (template
                .replace("{payload_json}", json.dumps(profile, indent=2))
                .replace("{reports_json}", json.dumps(payload["reports"], indent=2))
                .replace("{crime_categories_json}", category_lines))

    def _schema(self, source: dict) -> dict:
        """The typology schema, with crime_category limited to the given categories so the
        forecast's person types can be built from the typologies."""
        schema = super()._schema(source)
        item = schema["properties"]["sector_typologies"]["items"]
        item["properties"]["crime_category"] = {**item["properties"]["crime_category"],
                                                "enum": list(source.get("categories") or {})}
        return schema

    def _prepare(self, data: dict) -> dict:
        """Keep at most max_patterns typologies, so an over-long reply can still pass the schema."""
        typologies = data.get("sector_typologies", [])
        if not isinstance(typologies, list) or len(typologies) <= self.__max_patterns:
            return data
        warning = f"AI returned {len(typologies)} typologies; kept first {self.__max_patterns} per policy."
        logger.warning(warning)
        self._warnings.append(warning)
        return {**data, "sector_typologies": typologies[:self.__max_patterns]}

    def _post_process(self, data: dict, options: dict | None = None) -> dict:
        data["model"] = (options or {}).get("answered_by") or self._model
        return data

    def _reply_as_asked(self, data: dict) -> dict | None:
        """The saved reply without the "model" field that _post_process added. None if "model" is
        there but is not text."""
        if "model" in data and not isinstance(data["model"], str):
            return None
        return {key: value for key, value in data.items() if key != "model"}

    def __build_typology_reports(self, research: dict) -> list:
        """Only the safe fields of each report. The links stay behind."""
        return [{field: report[field] for field in TypologyAI.REPORT_FIELDS if field in report}
                for report in research.get("reports", [])]
