"""ResearchReport: one published report the research AI found."""

import re
from urllib.parse import urlparse


class ResearchReport:
    """A report (FATF, MAS, ...) with the excerpts taken from it.

    retrieved_at is when the research was done (the research reply's time, not the report's).
    The age of a source is measured from it.
    """

    def __init__(self, report_id: str = "", url: str = "", excerpts: list[str] | None = None,
                 organisation: str = "", title: str = "", year: int | None = None,
                 summary: list[str] | None = None, retrieved_at: str = "") -> None:
        self.__report_id: str = ResearchReport.__text("report_id", report_id)
        self.__url: str = ResearchReport.__text("url", url or "")
        self.__excerpts: list[str] = [str(excerpt) for excerpt in ResearchReport.__list("excerpts", excerpts)]
        self.__organisation: str = ResearchReport.__text("organisation", organisation or "")
        self.__title: str = ResearchReport.__text("title", title or "")
        # A year that is not a whole number is kept as "unknown": the crime scan warns about it.
        self.__year: int | None = year if isinstance(year, int) else None
        if isinstance(summary, str):
            summary = [summary]
        self.__summary: list[str] = [str(line) for line in ResearchReport.__list("summary", summary)]
        self.__retrieved_at: str = ResearchReport.__text("retrieved_at", retrieved_at or "")

    @classmethod
    def from_dict(cls, data: dict, retrieved_at: str = "") -> "ResearchReport":
        """One report of the research reply ({"report_id", "url", "excerpts", ...})."""
        if not isinstance(data, dict):
            raise ValueError(f"a research report must be a JSON object, not {type(data).__name__}")
        return cls(data.get("report_id", ""), data.get("url", ""), data.get("excerpts"),
                   data.get("organisation", ""), data.get("title", ""), data.get("year"),
                   data.get("summary"), retrieved_at)

    @property
    def report_id(self) -> str:
        return self.__report_id

    @property
    def url(self) -> str:
        return self.__url

    @property
    def excerpts(self) -> list[str]:
        return list(self.__excerpts)

    @property
    def organisation(self) -> str:
        return self.__organisation

    @property
    def title(self) -> str:
        return self.__title

    @property
    def year(self) -> int | None:
        return self.__year

    @property
    def summary(self) -> list[str]:
        return list(self.__summary)

    @property
    def retrieved_at(self) -> str:
        return self.__retrieved_at

    def retrieved_year(self) -> int:
        """The year the research was done; 0 if retrieved_at has no readable year."""
        try:
            return int(self.__retrieved_at[:4])
        except ValueError:
            return 0

    def domain(self) -> str:
        """'https://www.fatf-gafi.org/x' -> 'www.fatf-gafi.org'."""
        return urlparse(self.__url).netloc.lower()

    def contains_quote(self, quote: str) -> bool:
        """True if the quote appears in an excerpt, ignoring case, spacing and curly quote marks.
        An empty or blank quote proves nothing, so it is never found."""
        wanted = self.__normalise(quote)
        if not wanted:
            return False
        return any(wanted in self.__normalise(excerpt) for excerpt in self.__excerpts)

    def to_dict(self) -> dict:
        """The report as the research reply holds it (the AI's fields, then the id the code gave it)."""
        return {"organisation": self.__organisation, "title": self.__title, "year": self.__year,
                "url": self.__url, "excerpts": list(self.__excerpts), "summary": list(self.__summary),
                "report_id": self.__report_id}

    @staticmethod
    def __text(field: str, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError(f"a research report's {field} must be text, not {type(value).__name__}")
        return value

    @staticmethod
    def __list(field: str, value: object) -> list:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"a research report's {field} must be a list, not {type(value).__name__}")
        return value

    @staticmethod
    def __normalise(text: str) -> str:
        text = str(text or "").lower()
        for mark in "“”":
            text = text.replace(mark, '"')
        for mark in "‘’":
            text = text.replace(mark, "'")
        text = text.replace("–", "-").replace("—", "-")
        return re.sub(r"\s+", " ", text).strip()
