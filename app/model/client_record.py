"""ClientRecord: everything the bank holds about one client."""

from app.model.claims import Claims
from app.model.client_profile import ClientProfile
from app.model.declaration import Declaration
from app.model.investment import Investment
from app.model.job import Job
from app.model.review_status import ReviewStatus
from app.model.verdict import Verdict


class ClientRecord:
    """One client: profile, career, assets, claims, declaration, documents and review status.

    The record creates and owns all of its parts (composition). It checks what only the
    whole record can see (job order, asset years against the career, the asset split
    against the assets listed); each part checks its own values.
    """

    REQUIRED: tuple[str, ...] = ("client_ref", "name", "nationality", "current_date")
    CAREER_JOB_KEYS: tuple[str, ...] = ("occupation", "seniority", "industry", "employer_name", "employer_size")
    MIN_WORKING_AGE: int = 14
    __OWN_KEYS: tuple[str, ...] = ("client_ref", "name", "nationality", "current_date", "career",
                                   "career_history", "investments", "claims", "sow_declaration",
                                   "supporting_documents", "forecasting_case", "outcome", "routing",
                                   "next_review_date", "last_assessed_on")

    def __init__(self, client_ref: str = "", name: str = "", nationality: str = "", current_date: str = "",
                 country_of_residence: str = "", age: int | None = None) -> None:
        self.__client_ref: str = client_ref
        self.__profile: ClientProfile = ClientProfile(name, nationality, country_of_residence, age)
        self.__current_date: str = current_date
        self.__sow_declaration: str = ""
        self.__career_history: list[Job] = []
        self.__investments: list[Investment] = []
        self.__claims: Claims | None = None
        self.__declaration: Declaration = Declaration()
        self.__supporting_documents: list[dict] = []
        self.__review_status: ReviewStatus = ReviewStatus()
        # Saved fields this class has no name for (old layouts, database ids); kept so nothing is lost.
        self.__extra: dict = {}
        self.__career_extra: dict = {}

    # ----- read-only values -------------------------------------------------

    @property
    def client_ref(self) -> str:
        return self.__client_ref

    @property
    def profile(self) -> ClientProfile:
        return self.__profile

    @property
    def current_date(self) -> str:
        return self.__current_date

    @property
    def review_status(self) -> ReviewStatus:
        return self.__review_status

    @property
    def claims(self) -> Claims | None:
        return self.__claims

    @property
    def declaration(self) -> Declaration:
        return self.__declaration

    @property
    def sow_declaration(self) -> str:
        return self.__sow_declaration

    @sow_declaration.setter
    def sow_declaration(self, text: str) -> None:
        if not isinstance(text, str):
            raise ValueError("the source of wealth declaration must be text")
        self.__sow_declaration = text.strip()

    # ----- the parts ----------------------------------------------------------

    def jobs(self) -> list[Job]:
        return list(self.__career_history)

    def investments(self) -> list[Investment]:
        return list(self.__investments)

    def add_job(self, details: dict) -> Job:
        known = {key: details.get(key) for key in Job.KEYS}
        extra = {key: value for key, value in details.items() if key not in Job.KEYS}
        job = Job(start_year=self.__whole(known["start_year"]), end_year=self.__whole(known["end_year"]),
                  occupation=known["occupation"], seniority=known["seniority"], industry=known["industry"],
                  employer_name=known["employer_name"], employer_size=known["employer_size"],
                  country=known["country"], extra=extra)
        self.__career_history.append(job)
        return job

    def add_investment(self, details: dict) -> Investment:
        names = ("asset_type", "country", "year_acquired", "price_paid", "current_declared_value",
                 "payment_method", "income_produced")
        extra = {key: value for key, value in details.items() if key not in names}
        investment = Investment(
            asset_type=details.get("asset_type"), country=details.get("country"),
            year_acquired=self.__whole(details.get("year_acquired")), price_paid=details.get("price_paid"),
            current_declared_value=details.get("current_declared_value"),
            payment_method=details.get("payment_method"), income_produced=details.get("income_produced"),
            extra=extra)
        self.__investments.append(investment)
        return investment

    def set_claims(self, details: dict) -> Claims:
        names = ("declared_net_worth", "expected_aum", "pep_status", "asset_composition", "wealth_countries",
                 "declared_counterparties", "biggest_wealth_jump", "wealth_jump_years")
        extra = {key: value for key, value in details.items() if key not in names}
        self.__claims = Claims(
            declared_net_worth=details.get("declared_net_worth"), expected_aum=details.get("expected_aum"),
            pep_status=details.get("pep_status"), asset_composition=details.get("asset_composition"),
            wealth_countries=details.get("wealth_countries"),
            declared_counterparties=details.get("declared_counterparties"),
            biggest_wealth_jump=details.get("biggest_wealth_jump"),
            wealth_jump_years=details.get("wealth_jump_years"), extra=extra)
        return self.__claims

    def current_job(self) -> Job | None:
        """The latest job with no end year.

        The command line's New Client form keeps the current job only in "career", so when no listed
        job is open and "career" names another job, that job is returned (its own start year is not
        known). When "career" only repeats the last listed job (the web form copies it there, even
        once it has ended), or names none, the last job listed is the best available answer.
        Accepted limit: a client back in an earlier job (same occupation and employer) gets that earlier
        listed job; the saved data cannot tell this apart from the web form's copy."""
        for job in reversed(self.__career_history):
            if job.is_current():
                return job
        last = self.__career_history[-1] if self.__career_history else None
        occupation = str(self.__career_extra.get("occupation") or "").strip()
        if last is not None and (occupation, str(self.__career_extra.get("employer_name") or "").strip()) == \
                (str(last.occupation or "").strip(), str(last.employer_name or "").strip()):
            return last                     # the web form copies the last listed job (even an ended one) into career
        if occupation:
            details = {key: self.__career_extra.get(key) for key in ClientRecord.CAREER_JOB_KEYS}
            return Job(occupation=str(details["occupation"] or ""), seniority=str(details["seniority"] or ""),
                       industry=str(details["industry"] or ""), employer_name=str(details["employer_name"] or ""),
                       employer_size=str(details["employer_size"] or ""),
                       country=str(self.__career_extra.get("country") or ""))
        return last

    def career_start_year(self) -> int | None:
        starts = [job.start_year for job in self.__career_history if job.start_year is not None]
        return min(starts) if starts else self.__whole(self.__career_extra.get("career_start_year"))

    def documents(self) -> list[dict]:
        return list(self.__supporting_documents)

    def add_document(self, entry: dict) -> None:
        if not isinstance(entry, dict):
            raise ValueError("a supporting document entry must be a dict")
        self.__supporting_documents.append(entry)

    def record_assessment(self, verdict: Verdict, case: dict) -> None:
        """Keep the result of an assessment on the record."""
        self.__review_status.update(verdict.outcome, verdict.next_step, verdict.next_review_date,
                                    verdict.assessed_at, case)

    # ----- checks only the whole record can make ------------------------------

    def problems(self) -> list[str]:
        """What is wrong with the record, claims included (a record with no claims has none to
        add). Empty list = nothing."""
        return (self.__check_schema() + self.__check_job_order()
                + self.__check_one_current_job() + self.__check_asset_years()
                + (self.__claims.problems() if self.__claims else []))

    def warnings(self, policy: dict) -> list[str]:
        """Things worth a second look. Empty list = nothing spotted."""
        return (self.__check_start_age() + (self.__claims.warnings() if self.__claims else [])
                + self.__check_assets_vs_worth() + self.__check_split_against_assets(policy))

    def __this_year(self) -> int | None:
        text = str(self.__current_date or "")[:4]
        return int(text) if text.isdigit() else None

    def __check_schema(self) -> list[str]:
        values = {"client_ref": self.__client_ref, "name": self.__profile.name,
                  "nationality": self.__profile.nationality, "current_date": self.__current_date}
        return [f"The record has no {key.replace('_', ' ')}." for key in ClientRecord.REQUIRED
                if not str(values[key] or "").strip()]

    def __check_job_order(self) -> list[str]:
        problems = []
        this_year = self.__this_year()
        for number, job in enumerate(self.__career_history, start=1):
            problems += [f"Job {number} {problem}." for problem in job.problems()]
            if this_year is not None and job.start_year is not None and job.start_year > this_year:
                problems.append(f"Job {number} starts in the future ({job.start_year}).")
        return problems

    def __check_one_current_job(self) -> list[str]:
        open_jobs = [job for job in self.__career_history if job.is_current()]
        if len(open_jobs) > 1:
            return [f"{len(open_jobs)} jobs have no end year; only one should be the current job."]
        return []

    def __check_asset_years(self) -> list[str]:
        start = self.career_start_year()
        problems = []
        for number, asset in enumerate(self.__investments, start=1):
            year = asset.year_acquired
            if year is not None and start is not None and year < start:
                problems.append(f"Asset {number} was bought in {year}, before the client's career "
                                f"started ({start}).")
        return problems

    def __check_start_age(self) -> list[str]:
        age, start, this_year = self.__profile.age, self.career_start_year(), self.__this_year()
        if age is None or start is None or this_year is None:
            return []
        if start < this_year - age + ClientRecord.MIN_WORKING_AGE:
            return [f"Career start year {start} means the client started work before age "
                    f"{ClientRecord.MIN_WORKING_AGE}."]
        return []

    def __check_assets_vs_worth(self) -> list[str]:
        worth = self.__claims.declared_net_worth if self.__claims else None
        held = sum(asset.current_declared_value or 0 for asset in self.__investments)
        if worth is not None and held > worth * 1.2:
            return [f"The listed assets are worth {held:,.0f}, well above the declared net worth {worth:,.0f}."]
        return []

    def __check_split_against_assets(self, policy: dict) -> list[str]:
        """Does the declared wealth split agree with the assets listed? Catches a value or a
        percentage read or typed wrongly. Only checks kinds of asset that are listed."""
        worth = self.__claims.declared_net_worth if self.__claims else None
        if not worth or not policy.get("asset_categories"):
            return []
        split = self.__claims.asset_composition
        totals: dict = {}
        for asset in self.__investments:
            key = asset.category(policy)
            if key != "other" and asset.current_declared_value is not None:
                totals[key] = totals.get(key, 0) + asset.current_declared_value
        warnings = []
        for key, listed in totals.items():
            share = split.get(key)
            if not isinstance(share, (int, float)):
                continue
            declared = share * worth
            if abs(listed - declared) > 0.15 * max(declared, listed):
                label = key.replace("_", " ")
                warnings.append(f"The {label} assets listed are worth {listed:,.0f}, but the declared split "
                                f"puts {share:.0%} ({declared:,.0f}) of the net worth in {label}.")
        return warnings

    # ----- what the features are given ----------------------------------------

    def crime_scan_input(self) -> dict:
        """What the crime scan may see. Raises KeyError if the record has no job."""
        job = self.current_job()
        if job is None:
            raise KeyError("career")
        residence = self.__profile.country_of_residence
        return {"client_ref": self.__client_ref, "occupation": job.occupation, "industry": job.industry,
                "age": self.__profile.age, "career_start_year": self.career_start_year(),
                "country": residence, "country_of_residence": residence,
                "declaration_text": self.__sow_declaration}

    def benchmark_input(self) -> dict:
        """The benchmark's input. The asset split is in whole percents (45 = 45%)."""
        claims = self.__claims
        split = claims.asset_composition if claims else {}
        worth = claims.declared_net_worth if claims else None
        jump = claims.biggest_wealth_jump if claims else None
        return {
            **self.crime_scan_input(),
            "declared_net_worth": int(worth) if worth is not None else None,
            "listed_equities": self.__whole_percent(split.get("listed_equities")),
            "cash": self.__whole_percent(split.get("cash")),
            "property": self.__whole_percent(split.get("property")),
            "private_business": self.__whole_percent(split.get("private_business")),
            "biggest_wealth_jump": float(jump) if jump is not None else None,
            "wealth_jump_years": float((claims.wealth_jump_years if claims else 0) or 0.0),
            "declared_counterparties": claims.declared_counterparties if claims else [],
            "declared_countries": claims.wealth_countries if claims else [],
        }

    # ----- saving and loading ---------------------------------------------------

    def to_dict(self) -> dict:
        """The saved layout every screen reads. "career" is the current job plus the profile.

        When career_history holds an open job (no end year), that job is copied into "career".
        When every listed job has ended, the current job is the one saved in "career" (the
        command line's New Client form keeps it there and lists only earlier jobs in
        career_history), so "career" is kept as it was saved. A saved career start year is kept."""
        career = dict(self.__career_extra)
        open_jobs = [job for job in self.__career_history if job.is_current()]
        if open_jobs:
            job_data = open_jobs[-1].to_dict()
            for key in ClientRecord.CAREER_JOB_KEYS:
                career[key] = job_data[key]
        if self.__career_history and career.get("career_start_year") is None:
            career["career_start_year"] = self.career_start_year()
        career["country_of_residence"] = self.__profile.country_of_residence
        career["age"] = self.__profile.age
        data = {**self.__extra,
                "client_ref": self.__client_ref, "name": self.__profile.name,
                "nationality": self.__profile.nationality, "current_date": self.__current_date,
                "career": career,
                "career_history": [job.to_dict() for job in self.__career_history],
                "investments": [asset.to_dict() for asset in self.__investments],
                "claims": self.__claims.to_dict() if self.__claims else {},
                "sow_declaration": self.__sow_declaration,
                "supporting_documents": list(self.__supporting_documents)}
        data.update(self.__review_status.to_dict())
        return data

    @staticmethod
    def why_unreadable(error: Exception) -> str:
        """Why from_dict could not make a record, in words safe to show: a ValueError says what is
        wrong; any other error is a record not laid out as expected (its details belong in the log)."""
        if isinstance(error, ValueError):
            return str(error)
        return "some of the details are not in the expected layout"

    @staticmethod
    def from_dict(data: dict) -> "ClientRecord":
        """Build a record from its saved layout. Raises ValueError if a value cannot be right."""
        career = dict(data.get("career") or {})
        record = ClientRecord(
            client_ref=data.get("client_ref") or "", name=data.get("name") or "",
            nationality=data.get("nationality") or "", current_date=data.get("current_date") or "",
            country_of_residence=career.get("country_of_residence") or "",
            age=ClientRecord.__whole(career.get("age")))
        record.__career_extra = career
        record.__extra = {key: value for key, value in data.items() if key not in ClientRecord.__OWN_KEYS}
        for job in data.get("career_history") or []:
            record.add_job(job)
        for asset in data.get("investments") or []:
            record.add_investment(asset)
        if data.get("claims"):
            record.set_claims(data["claims"])
        sow = data.get("sow_declaration")
        record.sow_declaration = sow if isinstance(sow, str) else (sow or {}).get("declaration_text", "")
        for entry in data.get("supporting_documents") or []:
            record.add_document(entry)
        if data.get("outcome"):
            record.__review_status.update(data["outcome"], data.get("routing"), data.get("next_review_date"),
                                          data.get("last_assessed_on"), data.get("forecasting_case"))
        return record

    @staticmethod
    def __whole(value: object) -> int | None:
        """'2,017' / '51' / 51.0 -> a whole number; anything empty -> None; other values unchanged."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            text = value.replace(",", "").strip()
            return int(text) if text.lstrip("-").isdigit() else value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    @staticmethod
    def __whole_percent(value: object) -> int | None:
        """A share of wealth as a whole-number percent: 0.45 -> 45."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return round(value * 100) if value <= 1.0 else round(value)
