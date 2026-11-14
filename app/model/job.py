"""Job: one position in the client's career history."""


class Job:
    """One job the client held. The current job has no end year."""

    KEYS: tuple[str, ...] = ("start_year", "end_year", "occupation", "seniority", "industry",
                             "employer_name", "employer_size", "country")

    def __init__(self, start_year: int | None, end_year: int | None, occupation: str, seniority: str,
                 industry: str, employer_name: str, employer_size: str, country: str,
                 extra: dict | None = None) -> None:
        self.__check_years(start_year, end_year)
        self.__start_year: int | None = start_year
        self.__end_year: int | None = end_year
        self.__occupation: str = occupation
        self.__seniority: str = seniority
        self.__industry: str = industry
        self.__employer_name: str = employer_name
        self.__employer_size: str = employer_size
        self.__country: str = country
        # Details saved by an older screen that this class has no name for; kept so nothing is lost.
        self.__extra: dict = dict(extra or {})

    @property
    def start_year(self) -> int | None:
        return self.__start_year

    @start_year.setter
    def start_year(self, start_year: int | None) -> None:
        self.__check_years(start_year, self.__end_year)
        self.__start_year = start_year

    @property
    def end_year(self) -> int | None:
        return self.__end_year

    @end_year.setter
    def end_year(self, end_year: int | None) -> None:
        self.__check_years(self.__start_year, end_year)
        self.__end_year = end_year

    @property
    def occupation(self) -> str:
        return self.__occupation

    @property
    def seniority(self) -> str:
        return self.__seniority

    @property
    def industry(self) -> str:
        return self.__industry

    @property
    def employer_name(self) -> str:
        return self.__employer_name

    @property
    def employer_size(self) -> str:
        return self.__employer_size

    @property
    def country(self) -> str:
        return self.__country

    def is_current(self) -> bool:
        return self.__end_year is None

    def end_or(self, this_year: int) -> int:
        """Last year the job was held. The current job runs to this year."""
        return int(self.__end_year or this_year)

    def problems(self) -> list[str]:
        """What is wrong with this job on its own. Empty list = nothing."""
        problems = []
        start, end = self.__start_year, self.__end_year
        if start is not None and end is not None and end < start:
            problems.append(f"ends ({end}) before it starts ({start})")
        return problems

    def to_dict(self) -> dict:
        return {**self.__extra,
                "start_year": self.__start_year, "end_year": self.__end_year,
                "occupation": self.__occupation, "seniority": self.__seniority,
                "industry": self.__industry, "employer_name": self.__employer_name,
                "employer_size": self.__employer_size, "country": self.__country}

    def __check_years(self, start_year: int | None, end_year: int | None) -> None:
        for label, year in (("start year", start_year), ("end year", end_year)):
            if year is None:
                continue
            if isinstance(year, bool) or not isinstance(year, int):
                raise ValueError(f"a job's {label} must be a whole year or left empty")
            if not 1900 <= year <= 2100:
                raise ValueError(f"a job's {label} must be between 1900 and 2100")
