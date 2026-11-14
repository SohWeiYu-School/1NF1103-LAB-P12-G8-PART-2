"""Verdict: the one result of an assessment."""

from app.model.check import Check


class Verdict:
    """The outcome of one assessment and the checks behind it.

    The checks are made by the features and handed in (aggregation): a Check can
    exist without a Verdict.
    """

    OUTCOMES: tuple[str, ...] = ("PASSED", "MANUAL_REVIEW", "RISKY", "SERIOUS_RISK")
    # How serious each outcome is, so two outcomes can be compared.
    SEVERITY: dict[str, int] = {"PASSED": 0, "MANUAL_REVIEW": 1, "RISKY": 2, "SERIOUS_RISK": 3}

    def __init__(self, assessment_id: str = "", client_ref: str = "", assessed_at: str = "", outcome: str = "MANUAL_REVIEW",
                 next_step: str = "", next_review_date: str = "",
                 notes: list[str] | None = None, not_run: list[str] | None = None) -> None:
        self.__check_outcome(outcome)
        self.__assessment_id: str = assessment_id
        self.__client_ref: str = client_ref
        self.__assessed_at: str = assessed_at
        self.__outcome: str = outcome
        self.__next_step: str = next_step
        self.__next_review_date: str = next_review_date
        self.__checks: list[Check] = []
        self.__notes: list[str] = list(notes or [])
        self.__not_run: list[str] = list(not_run or [])
        self.__report: dict = {}

    @property
    def assessment_id(self) -> str:
        return self.__assessment_id

    @property
    def client_ref(self) -> str:
        return self.__client_ref

    @property
    def assessed_at(self) -> str:
        return self.__assessed_at

    @property
    def outcome(self) -> str:
        return self.__outcome

    @property
    def next_step(self) -> str:
        return self.__next_step

    @property
    def next_review_date(self) -> str:
        return self.__next_review_date

    @property
    def notes(self) -> list[str]:
        return list(self.__notes)

    @property
    def not_run(self) -> list[str]:
        return list(self.__not_run)

    @property
    def report(self) -> dict:
        return self.__report

    @report.setter
    def report(self, report: dict) -> None:
        if not isinstance(report, dict):
            raise ValueError("a verdict report must be a dict")
        self.__report = report

    def add_check(self, check: Check) -> None:
        if not isinstance(check, Check):
            raise ValueError("only a Check can be added to a verdict")
        self.__checks.append(check)

    def checks(self) -> list[Check]:
        return list(self.__checks)

    def to_dict(self) -> dict:
        return {"assessment_id": self.__assessment_id, "client_ref": self.__client_ref,
                "assessed_at": self.__assessed_at, "outcome": self.__outcome,
                "next_step": self.__next_step, "next_review_date": self.__next_review_date,
                "checks": [check.to_dict() for check in self.__checks],
                "notes": list(self.__notes), "not_run": list(self.__not_run),
                "report": self.__report}

    def __check_outcome(self, outcome: str) -> None:
        if outcome not in Verdict.OUTCOMES:
            raise ValueError(f"'{outcome}' is not an outcome; use one of {', '.join(Verdict.OUTCOMES)}")
