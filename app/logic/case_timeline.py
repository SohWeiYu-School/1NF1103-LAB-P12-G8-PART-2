"""CaseTimeline: the years that matter for one case."""


class CaseTimeline:
    """Reads a case's dates: his jobs in order, the year he started work, the assessment
    year and the forecast years. Every forecast class asks the same timeline, so they
    all agree on which years exist."""

    FORECAST_YEARS: int = 4      # how many years after the assessment year are forecast

    def __init__(self, record: dict | None = None, forecast_years: int = FORECAST_YEARS) -> None:
        if record is not None and not isinstance(record, dict):
            raise ValueError(f"a case timeline's record must be a dict (or None), not {type(record).__name__}")
        if isinstance(forecast_years, bool) or not isinstance(forecast_years, int) or forecast_years < 1:
            raise ValueError(f"the number of forecast years must be a whole number of 1 or more, not {forecast_years!r}")
        self.__record: dict = record or {}
        self.__forecast_years: int = forecast_years

    def positions(self) -> list[dict]:
        """His jobs, oldest first. Falls back to the current job if no history was given."""
        history = self.__record.get("career_history") or []
        if history:
            return history
        career = self.__record.get("career", {})
        return [{**career, "start_year": career.get("career_start_year"), "end_year": None}]

    def current_year(self) -> int:
        """The year of the assessment date, e.g. 2026 from '2026-09-24'."""
        return int(str(self.__record.get("current_date", ""))[:4])

    def career_years(self) -> tuple[int, int]:
        """(first year he worked, current year)."""
        this_year = self.current_year()
        start_years = [position["start_year"] for position in self.positions() if position.get("start_year")]
        return int(min(start_years) if start_years else this_year), this_year

    def position_end(self, position: dict) -> int:
        """Last year a job was held. The current job runs to this year."""
        return int(position.get("end_year") or self.current_year())

    def future_years(self) -> list[int]:
        """The forecast years, e.g. [2027, 2028, 2029, 2030]."""
        this_year = self.current_year()
        return list(range(this_year + 1, this_year + self.__forecast_years + 1))
