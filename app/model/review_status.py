"""ReviewStatus: where the client stands after the last assessment."""


class ReviewStatus:
    """The last outcome, what happens next and when the client is reviewed again.

    Empty until the first assessment. Only update() changes it, so the five values
    always come from the same assessment.
    """

    def __init__(self) -> None:
        self.__outcome: str = ""
        self.__routing: str = ""
        self.__next_review_date: str = ""
        self.__last_assessed_on: str = ""
        self.__forecasting_case: dict = {}

    @property
    def outcome(self) -> str:
        return self.__outcome

    @property
    def routing(self) -> str:
        return self.__routing

    @property
    def next_review_date(self) -> str:
        return self.__next_review_date

    @property
    def last_assessed_on(self) -> str:
        return self.__last_assessed_on

    @property
    def forecasting_case(self) -> dict:
        return self.__forecasting_case

    def update(self, outcome: str, routing: str, next_review_date: str, assessed_on: str, case: dict) -> None:
        """Record the result of an assessment."""
        if not outcome:
            raise ValueError("an assessment must have an outcome")
        self.__outcome = outcome
        self.__routing = routing or ""
        self.__next_review_date = next_review_date or ""
        self.__last_assessed_on = assessed_on or ""
        self.__forecasting_case = case or {}

    def to_dict(self) -> dict:
        """Only what has been set, so a client who was never assessed saves no empty fields."""
        if not self.__outcome:
            return {"forecasting_case": self.__forecasting_case} if self.__forecasting_case else {}
        return {"forecasting_case": self.__forecasting_case, "outcome": self.__outcome,
                "routing": self.__routing, "next_review_date": self.__next_review_date,
                "last_assessed_on": self.__last_assessed_on}
