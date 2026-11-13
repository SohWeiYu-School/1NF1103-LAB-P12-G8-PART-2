"""Typology: a known pattern of financial crime for a sector."""


class Typology:
    """A known pattern, the warning signs (indicators) that point to it and the reports it cites."""

    def __init__(self, typology_id: str, name: str, indicators: list[dict] | None = None,
                 source_ids: list[str] | None = None) -> None:
        self.__typology_id: str = typology_id
        self.__name: str = name
        self.__indicators: list[dict] = [dict(indicator) for indicator in indicators or []]
        self.__source_ids: list[str] = list(source_ids or [])

    @property
    def typology_id(self) -> str:
        return self.__typology_id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def indicators(self) -> list[dict]:
        return [dict(indicator) for indicator in self.__indicators]

    def core_indicators(self) -> list[str]:
        """The warning signs that must all fire for the pattern to be breached."""
        return self.__by_weight("core")

    def supporting_indicators(self) -> list[str]:
        return self.__by_weight("supporting")

    def cited_report_ids(self) -> list[str]:
        return list(self.__source_ids)

    def __by_weight(self, weight: str) -> list[str]:
        return [indicator["indicator"] for indicator in self.__indicators if indicator.get("weight") == weight]
