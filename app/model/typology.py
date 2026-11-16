"""Typology: a known pattern of financial crime for a sector."""


class Typology:
    """A known pattern, the warning signs (indicators) that point to it and the reports it cites.

    A typology the crime scan has checked against its research reports is "verified": it then
    also knows whether two independent organisations back it (corroborated) and which of its
    reports are too old (outdated_source_ids).
    """

    WEIGHTS: tuple[str, ...] = ("core", "supporting")

    def __init__(self, typology_id: str = "", name: str = "", indicators: list[dict] | None = None,
                 source_ids: list[str] | None = None, crime_category: str = "", description: str = "",
                 source_quotes: list[dict] | None = None, typical_documents: list[str] | None = None) -> None:
        self.__typology_id: str = Typology.__text("typology_id", typology_id)
        self.__name: str = Typology.__text("name", name)
        self.__indicators: list[dict] = [Typology.__indicator(indicator)
                                         for indicator in Typology.__list("indicators", indicators)]
        self.__source_ids: list[str] = [Typology.__text("source id", source_id)
                                        for source_id in Typology.__list("source_ids", source_ids)]
        self.__crime_category: str = Typology.__text("crime_category", crime_category)
        self.__description: str = Typology.__text("description", description)
        self.__source_quotes: list[dict] = [Typology.__quote(quote)
                                            for quote in Typology.__list("source_quotes", source_quotes)]
        self.__typical_documents: list[str] = [Typology.__text("typical document", document) for document
                                               in Typology.__list("typical_documents", typical_documents)]
        self.__verified: bool = False
        self.__corroborated: bool = False
        self.__outdated_source_ids: list[str] = []

    @classmethod
    def from_dict(cls, data: dict) -> "Typology":
        """One typology of the typology reply (or one saved by to_dict)."""
        if not isinstance(data, dict):
            raise ValueError(f"a typology must be a JSON object, not {type(data).__name__}")
        typology = cls(data.get("typology_id", ""), data.get("name", ""), data.get("indicators"),
                       data.get("source_ids"), data.get("crime_category", ""), data.get("description", ""),
                       data.get("source_quotes"), data.get("typical_documents"))
        if "corroborated" in data or "outdated_source_ids" in data:
            typology = typology.with_verified_sources(typology.cited_report_ids(), typology.source_quotes,
                                                      data.get("corroborated", False),
                                                      data.get("outdated_source_ids"))
        return typology

    @property
    def typology_id(self) -> str:
        return self.__typology_id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def indicators(self) -> list[dict]:
        return [dict(indicator) for indicator in self.__indicators]

    @property
    def crime_category(self) -> str:
        return self.__crime_category

    @property
    def description(self) -> str:
        return self.__description

    @property
    def source_quotes(self) -> list[dict]:
        """The quotes ({"report_id", "quote"}) taken from the reports it cites."""
        return [dict(quote) for quote in self.__source_quotes]

    @property
    def typical_documents(self) -> list[str]:
        return list(self.__typical_documents)

    @property
    def verified(self) -> bool:
        """True once the crime scan has checked its sources against the research reports."""
        return self.__verified

    @property
    def corroborated(self) -> bool:
        return self.__corroborated

    @property
    def outdated_source_ids(self) -> list[str]:
        return list(self.__outdated_source_ids)

    def core_indicators(self) -> list[str]:
        """The warning signs that must all fire for the pattern to be breached."""
        return self.__by_weight("core")

    def supporting_indicators(self) -> list[str]:
        return self.__by_weight("supporting")

    def cited_report_ids(self) -> list[str]:
        return list(self.__source_ids)

    def with_verified_sources(self, source_ids: list[str], source_quotes: list[dict], corroborated: bool,
                              outdated_source_ids: list[str] | None) -> "Typology":
        """A copy keeping only the sources and quotes that were checked, marked as verified."""
        if not isinstance(corroborated, bool):
            raise ValueError(f"corroborated must be true or false, not {corroborated!r}")
        checked = Typology(self.__typology_id, self.__name, self.__indicators, source_ids, self.__crime_category,
                           self.__description, source_quotes, self.__typical_documents)
        outdated = [Typology.__text("outdated source id", source_id)
                    for source_id in Typology.__list("outdated_source_ids", outdated_source_ids)]
        unknown = [source_id for source_id in outdated if source_id not in checked.cited_report_ids()]
        if unknown:
            raise ValueError(f"outdated sources {unknown} are not among the typology's sources")
        checked.__verified = True
        checked.__corroborated = corroborated
        checked.__outdated_source_ids = outdated
        return checked

    def to_dict(self) -> dict:
        """The typology reply's layout; a verified typology adds corroborated and outdated_source_ids."""
        data = {"typology_id": self.__typology_id, "name": self.__name, "crime_category": self.__crime_category,
                "description": self.__description, "source_ids": list(self.__source_ids),
                "source_quotes": self.source_quotes, "indicators": self.indicators,
                "typical_documents": list(self.__typical_documents)}
        if self.__verified:
            data["corroborated"] = self.__corroborated
            data["outdated_source_ids"] = list(self.__outdated_source_ids)
        return data

    def __by_weight(self, weight: str) -> list[str]:
        return [indicator["indicator"] for indicator in self.__indicators if indicator["weight"] == weight]

    @staticmethod
    def __indicator(indicator: object) -> dict:
        if not isinstance(indicator, dict) or not isinstance(indicator.get("indicator"), str):
            raise ValueError(f"a typology indicator must be {{'indicator': name, 'weight': ...}}, not {indicator!r}")
        if indicator.get("weight") not in Typology.WEIGHTS:
            raise ValueError(f"a typology indicator's weight must be one of {list(Typology.WEIGHTS)}, "
                             f"not {indicator.get('weight')!r}")
        return dict(indicator)

    @staticmethod
    def __quote(quote: object) -> dict:
        if not isinstance(quote, dict):
            raise ValueError(f"a typology quote must be {{'report_id', 'quote'}}, not {quote!r}")
        return dict(quote)

    @staticmethod
    def __text(field: str, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError(f"a typology's {field} must be text, not {type(value).__name__}")
        return value

    @staticmethod
    def __list(field: str, value: object) -> list:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"a typology's {field} must be a list, not {type(value).__name__}")
        return value
