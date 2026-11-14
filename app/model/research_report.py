"""ResearchReport: one published report the research AI found."""

import re
from urllib.parse import urlparse


class ResearchReport:
    """A report (FATF, MAS, ...) with the excerpts taken from it."""

    def __init__(self, report_id: str = "", url: str = "", excerpts: list[str] | None = None) -> None:
        self.__report_id: str = report_id
        self.__url: str = url or ""
        self.__excerpts: list[str] = [str(excerpt) for excerpt in excerpts or []]

    @property
    def report_id(self) -> str:
        return self.__report_id

    @property
    def url(self) -> str:
        return self.__url

    @property
    def excerpts(self) -> list[str]:
        return list(self.__excerpts)

    def domain(self) -> str:
        """'https://www.fatf-gafi.org/x' -> 'www.fatf-gafi.org'."""
        return urlparse(self.__url).netloc.lower()

    def contains_quote(self, quote: str) -> bool:
        """True if the quote appears in an excerpt, ignoring case, spacing and curly quote marks."""
        wanted = self.__normalise(quote)
        return any(wanted in self.__normalise(excerpt) for excerpt in self.__excerpts)

    @staticmethod
    def __normalise(text: str) -> str:
        text = str(text or "").lower()
        for mark in "“”":
            text = text.replace(mark, '"')
        for mark in "‘’":
            text = text.replace(mark, "'")
        text = text.replace("–", "-").replace("—", "-")
        return re.sub(r"\s+", " ", text).strip()
