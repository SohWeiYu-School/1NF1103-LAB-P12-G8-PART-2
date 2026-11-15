"""MatchResult: how one typology matched one client."""

from app.model.typology import Typology


class MatchResult:
    """The warning signs of one typology that fired for the client, and how strong the match is.

    category is how strong the match is (the crime scan works it out): "critical", "high" or
    "medium" when every core sign fired, "partial" or "weak_signal" when only supporting signs did,
    "no_match" otherwise.
    """

    CATEGORIES: tuple[str, ...] = ("critical", "high", "medium", "partial", "weak_signal", "no_match")

    def __init__(self, typology: Typology | None = None, core_fired: list[str] | None = None,
                 supporting_fired: list[str] | None = None, category: str = "no_match") -> None:
        if typology is not None and not isinstance(typology, Typology):
            raise ValueError(f"a match result needs a Typology, not {type(typology).__name__}")
        self.__typology: Typology = typology or Typology()
        self.__core_fired: list[str] = MatchResult.__signs(
            "core", core_fired, self.__typology.core_indicators())
        self.__supporting_fired: list[str] = MatchResult.__signs(
            "supporting", supporting_fired, self.__typology.supporting_indicators())
        if category not in MatchResult.CATEGORIES:
            raise ValueError(f"a match category must be one of {list(MatchResult.CATEGORIES)}, not {category!r}")
        self.__category: str = category

    @property
    def typology(self) -> Typology:
        return self.__typology

    @property
    def core_fired(self) -> list[str]:
        return list(self.__core_fired)

    @property
    def supporting_fired(self) -> list[str]:
        return list(self.__supporting_fired)

    @property
    def category(self) -> str:
        return self.__category

    @property
    def breached(self) -> bool:
        """True when every core warning sign fired (and there is at least one)."""
        core = self.__typology.core_indicators()
        return len(core) > 0 and len(self.__core_fired) == len(core)

    def fired(self) -> list[str]:
        """Every warning sign that fired: the core ones, then the supporting ones."""
        return self.__core_fired + self.__supporting_fired

    def to_dict(self) -> dict:
        """The saved layout of one match (crime_result["match_results"])."""
        typology = self.__typology
        return {"typology_id": typology.typology_id, "name": typology.name,
                "source_ids": typology.cited_report_ids(), "breached": self.breached, "category": self.__category,
                "core_indicators": typology.core_indicators(), "core_fired": list(self.__core_fired),
                "supporting_indicators": typology.supporting_indicators(),
                "supporting_fired": list(self.__supporting_fired),
                "typical_documents": typology.typical_documents}

    @staticmethod
    def __signs(weight: str, fired: list[str] | None, allowed: list[str]) -> list[str]:
        fired = fired or []
        if not isinstance(fired, list):
            raise ValueError(f"the {weight} signs that fired must be a list, not {type(fired).__name__}")
        unknown = [sign for sign in fired if sign not in allowed]
        if unknown:
            raise ValueError(f"{unknown} fired as {weight} signs but the typology's {weight} signs are {allowed}")
        return list(fired)
