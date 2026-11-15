"""Verdict: the one result of an assessment."""

from app.model.check import Check


class Verdict:
    """The outcome of one assessment and the checks behind it.

    The checks are made by the features and handed in (aggregation): a Check can
    exist without a Verdict.

    The explanation holds what the VerdictEngine worked out to explain the outcome (the
    reasons, which checks agree, the documents to ask for, the evidence ...). details()
    puts it back together with the outcome and the checks in the layout saved under
    "verdict" in an assessment record.
    """

    OUTCOMES: tuple[str, ...] = ("PASSED", "MANUAL_REVIEW", "RISKY", "SERIOUS_RISK")
    # How serious each outcome is, so two outcomes can be compared.
    SEVERITY: dict[str, int] = {"PASSED": 0, "MANUAL_REVIEW": 1, "RISKY": 2, "SERIOUS_RISK": 3}
    # Where each feature's checks are saved in details(), in their saved order.
    CHECK_GROUPS: dict[str, str] = {"benchmark": "benchmark", "forecast": "forecast", "crime": "crime",
                                    "documents": "document_findings"}
    # What an explanation must hold, every one of them.
    EXPLANATION_KEYS: tuple[str, ...] = ("name", "assessed_on", "policy_version", "verdict_label", "summary",
                                         "reasons", "agreement", "types", "documents", "clean", "evidence")

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
        self.__explanation: dict = {}

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

    @property
    def explanation(self) -> dict:
        return dict(self.__explanation)

    @explanation.setter
    def explanation(self, explanation: dict) -> None:
        if not isinstance(explanation, dict):
            raise ValueError("a verdict explanation must be a dict")
        missing = [key for key in Verdict.EXPLANATION_KEYS if key not in explanation]
        unknown = [key for key in explanation if key not in Verdict.EXPLANATION_KEYS]
        if missing or unknown:
            raise ValueError("a verdict explanation must hold exactly " + ", ".join(Verdict.EXPLANATION_KEYS)
                             + (f"; missing: {', '.join(missing)}" if missing else "")
                             + (f"; not allowed: {', '.join(map(str, unknown))}" if unknown else ""))
        self.__explanation = dict(explanation)

    def add_check(self, check: Check) -> None:
        if not isinstance(check, Check):
            raise ValueError("only a Check can be added to a verdict")
        if check.feature not in Verdict.CHECK_GROUPS:
            raise ValueError(f"a check from '{check.feature}' cannot be added to a verdict; "
                             f"the features are {', '.join(Verdict.CHECK_GROUPS)}")
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

    def details(self) -> dict:
        """The verdict and everything that explains it, in the layout saved under "verdict"
        in an assessment record (the report is built from it too). Each feature's checks
        are listed under their own key, in the order they were added."""
        if not self.__explanation:
            raise ValueError("this verdict has no explanation yet, so it cannot be laid out")
        explanation = self.__explanation
        groups: dict[str, list[dict]] = {key: [] for key in Verdict.CHECK_GROUPS.values()}
        for check in self.__checks:
            groups[Verdict.CHECK_GROUPS[check.feature]].append(check.to_dict())
        return {
            "client_ref": self.__client_ref,
            "name": explanation["name"],
            "assessed_on": explanation["assessed_on"],
            "policy_version": explanation["policy_version"],
            "verdict": self.__outcome,
            "verdict_label": explanation["verdict_label"],
            "next_step": self.__next_step,
            "next_review_date": self.__next_review_date,
            "summary": explanation["summary"],
            "reasons": explanation["reasons"],
            "agreement": explanation["agreement"],
            **groups,
            "types": explanation["types"],
            "documents": explanation["documents"],
            "clean": explanation["clean"],
            "not_run": list(self.__not_run),
            "notes": list(self.__notes),
            "evidence": explanation["evidence"],
        }

    def __check_outcome(self, outcome: str) -> None:
        if outcome not in Verdict.OUTCOMES:
            raise ValueError(f"'{outcome}' is not an outcome; use one of {', '.join(Verdict.OUTCOMES)}")
