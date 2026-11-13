"""Feature: one part of the assessment that produces checks for the verdict."""

from abc import ABC, abstractmethod

from app.model.check import Check


class Feature(ABC):
    """The parent of the four parts of an assessment: the crime scan, the document evidence,
    the benchmark and the forecast.

    Every feature does the same two things. run() works out its results from the case and
    the AI's data. checks() turns those results into Checks in the one shape the verdict
    reads. The VerdictEngine is handed a list of features and treats them all alike, so a
    new feature can be added without changing the engine.
    """

    NAME: str = "feature"

    def __init__(self, policy: dict | None = None) -> None:
        self._policy: dict = policy or {}
        self._results: dict = {}

    @abstractmethod
    def run(self, case: dict, ai_data: dict) -> dict:
        """Work out this feature's results. They are also kept in self._results."""

    @abstractmethod
    def checks(self, context: dict) -> list[Check]:
        """This feature's findings, in the shape every feature shares."""

    def _check(self, check: str, label: str, theme: str, status: str, detail: str,
               explanation: str = "", group: str = "",
               sources: list[str] | None = None, supports: list[str] | None = None) -> Check:
        """One finding of this feature."""
        return Check(self.NAME, check, label, theme, status, detail, explanation, group, sources, supports)

    def _jump_years(self, case: dict) -> tuple[float | None, int | None]:
        """His biggest wealth jump and the number of years it took, as declared.
        (None, None) if he declared none."""
        claims = case.get("claims", {})
        jump, years = claims.get("biggest_wealth_jump"), claims.get("wealth_jump_years")
        if not isinstance(jump, (int, float)) or jump <= 0 or not isinstance(years, (int, float)) or years <= 0:
            return None, None
        return float(jump), max(1, round(years))
