"""CaseBuilder: turns a saved client record into a case, asking for whatever is missing."""

import datetime
from typing import Callable

from jsonschema import Draft202012Validator

from app.interface.client_form import ClientForm
from app.interface.console_ui import ConsoleUI

Ask = Callable[[str], str]


class CaseBuilder:
    """Reads a saved client record into the case the assessment needs. Where a value is
    missing or cannot be read, it asks the officer through the ConsoleUI instead of
    guessing, then checks the finished case against the case schema it was handed.
    """

    def __init__(self, ui: ConsoleUI, case_schema: dict | None = None) -> None:
        self.__ui: ConsoleUI = ui
        self.__case_schema: dict = case_schema or {}

    def validate_case(self, case: object) -> list[str]:
        """Everything wrong with a case (from a file or typed in). [] means it's fine."""
        if not isinstance(case, dict):
            return ["the case must be a JSON object"]
        schema = self.__case_schema
        errors = [f"{'/'.join(str(p) for p in e.path) or 'case'}: {e.message}"
                  for e in Draft202012Validator(schema).iter_errors(case)]
        if errors:
            return errors

        this_year = int(case["current_date"][:4])
        jobs = case["career_history"]
        for index, job in enumerate(jobs):
            end = job["end_year"] if job["end_year"] is not None else this_year
            if job["start_year"] > end:
                errors.append(f"job {index + 1}: starts after it ends")
            if end > this_year:
                errors.append(f"job {index + 1}: ends after the assessment date")
            if index > 0 and job["start_year"] < (jobs[index - 1]["end_year"] or this_year):
                errors.append(f"job {index + 1}: starts before job {index} ends")
        if [j for j in jobs[:-1] if j["end_year"] is None]:
            errors.append("only the last job can be the current one (no end year)")
        first_year = jobs[0]["start_year"]
        for index, asset in enumerate(case["investments"]):
            if not first_year <= asset["year_acquired"] <= this_year:
                errors.append(f"asset {index + 1}: bought outside the career years {first_year}-{this_year}")
        total = sum(case["claims"]["asset_composition"].values())
        if not 0.95 <= total <= 1.05:
            errors.append(f"asset composition adds up to {total:.0%}, it should be 100%")
        return errors

    def _payment_method(self, text: object) -> str | None:
        """Map what was typed ('Cash', 'mortgage', 'bank loan', 'sold my flat') to cash / loan / asset_sale."""
        words = str(text or "").lower()
        if any(w in words for w in ("loan", "mortgage", "financ", "borrow")):
            return "loan"
        if any(w in words for w in ("sale", "sold", "proceeds")):
            return "asset_sale"
        if "cash" in words or "savings" in words:
            return "cash"
        return None

    def _number_or_ask(self, value: object, question: str, ask: Ask, allow_zero: bool = True) -> float:
        number = self.__ui.read_number(value)
        if number is not None and number >= 0 and (allow_zero or number > 0):
            return number
        if str(value or "").strip():
            self.__ui.show_error(f"Couldn't read '{value}' as an amount.")
        return self.__ui.ask_money(question, ask, allow_zero=allow_zero)

    def _year_or_ask(self, value: object, question: str, ask: Ask, minimum: int | None = None,
                     maximum: int | None = None) -> int:
        year = self.__ui.read_year(value)
        if year is not None and (minimum is None or year >= minimum) and (maximum is None or year <= maximum):
            return year
        return self.__ui.ask_int(question, ask, minimum, maximum)

    def _text_or_ask(self, value: object, question: str, ask: Ask) -> str:
        text = str(value or "").strip()
        return text if text else self.__ui.ask_text(question, ask)

    def _jobs_from_record(self, record: dict, this_year: int, ask: Ask) -> list[dict]:
        """Career history entries plus the current job from career dict."""
        career = record.get("career", {})
        jobs = []
        for number, entry in enumerate(record.get("career_history", []), start=1):
            label = f"Job {number} ({entry.get('occupation') or 'no title'})"
            start = self._year_or_ask(entry.get("start_year"), f"{label}: start year", ask, 1900, this_year)
            end_text = str(entry.get("end_year") or "").strip().lower()
            end = None if end_text in ("", "present", "now", "current", "-", "none") else \
                self._year_or_ask(entry.get("end_year"), f"{label}: end year", ask, start, this_year)
            jobs.append({
                "start_year":    start, "end_year": end,
                "occupation":    self._text_or_ask(entry.get("occupation"),    f"{label}: job title", ask),
                "seniority":     self._text_or_ask(entry.get("seniority"),     f"{label}: seniority", ask),
                "industry":      self._text_or_ask(entry.get("industry"),      f"{label}: industry", ask),
                "employer_name": self._text_or_ask(entry.get("employer_name"), f"{label}: employer", ask),
                "employer_size": self._text_or_ask(entry.get("employer_size"), f"{label}: employer size", ask),
                "country":       self._text_or_ask(entry.get("country"),       f"{label}: country", ask),
            })
        jobs.sort(key=lambda job: job["start_year"])

        # Add current job from career dict if not already present as an open-ended entry
        if not jobs or jobs[-1]["end_year"] is not None:
            earliest = jobs[-1]["end_year"] if jobs else 1900
            self.__ui.show("\nCurrent job (from client profile)")
            jobs.append({
                "start_year": self.__ui.ask_int(
                    f"  Year started as {career.get('occupation') or 'current role'} "
                    f"at {career.get('employer_name') or 'current employer'}",
                    ask, earliest, this_year),
                "end_year":      None,
                "occupation":    self._text_or_ask(career.get("occupation"),           "  Current job title", ask),
                "seniority":     self._text_or_ask(career.get("seniority"),            "  Current seniority", ask),
                "industry":      self._text_or_ask(career.get("industry"),             "  Current industry", ask),
                "employer_name": self._text_or_ask(career.get("employer_name"),        "  Current employer", ask),
                "employer_size": self._text_or_ask(career.get("employer_size"),        "  Current employer size", ask),
                "country":       self._text_or_ask(career.get("country_of_residence"), "  Country of current job", ask),
            })
        return jobs

    def _first_filled(self, *values: object) -> object:
        """The first value that isn't None or blank text, else None."""
        for value in values:
            if value is not None and str(value).strip():
                return value
        return None

    def _assets_from_record(self, record: dict, first_year: int, this_year: int, ask: Ask) -> list[dict]:
        """Investments still held, amounts in SGD. Sold assets are excluded."""
        investments = []
        for number, entry in enumerate(record.get("investments", []), start=1):
            name = str(entry.get("asset_type") or "").strip() or f"Asset {number}"
            if str(entry.get("year_sold") or "").strip():
                self.__ui.show(f"  {name}: sold in {entry['year_sold']}, so it's left out of the forecast.")
                continue
            currency = str(entry.get("currency") or "SGD").strip().upper()
            in_sgd = currency in ("", "SGD", "S$")
            if not in_sgd:
                self.__ui.show(f"\n{name} is in {currency}. Please give its amounts in SGD.")
            # current_declared_value / income_produced, as the web form saves them; older command-line
            # records called them current_value / yearly_income (data_manager upgrades those on load).
            current_value = self._first_filled(entry.get("current_declared_value"), entry.get("current_value"))
            yearly_income = self._first_filled(entry.get("income_produced"), entry.get("yearly_income"))
            method = self._payment_method(entry.get("payment_method"))
            if method is None:
                method = ClientForm.PAYMENT_METHODS[self.__ui.ask_choice(f"{name}: how was it paid for?", ClientForm.PAYMENT_METHODS, ask)]
            investments.append({
                "asset_type":             name,
                "country":                self._text_or_ask(entry.get("country"), f"{name}: country", ask),
                "year_acquired":          self._year_or_ask(entry.get("year_acquired"), f"{name}: year bought", ask, first_year, this_year),
                "price_paid":             self._number_or_ask(entry.get("price_paid") if in_sgd else None,
                                                         f"{name}: price paid (SGD)", ask, allow_zero=False),
                "current_declared_value": self._number_or_ask(current_value if in_sgd else None,
                                                         f"{name}: current value (SGD)", ask),
                "payment_method":         method,
                "income_produced":        self._number_or_ask((yearly_income or "0") if in_sgd else None,
                                                         f"{name}: yearly income (SGD, 0 if none)", ask),
            })
        return investments

    def _composition_from_record(self, record: dict, ask: Ask) -> dict:
        """Asset composition as fractions (0.60 = 60%). Asks if missing or doesn't add up."""
        typed = record.get("claims", {}).get("asset_composition", {})
        split = {key: self.__ui.read_number(typed.get(key)) for key in ("property", "listed_equities", "private_business", "cash")}
        # Values may already be fractions (0-1) — check sum
        if all(v is not None for v in split.values()):
            total = sum(split.values())
            if 0.95 <= total <= 1.05:
                return split   # already fractions
            if 95 <= total <= 105:
                return {k: v / 100 for k, v in split.items()}  # were percentages
        self.__ui.show_error("The asset composition is missing or doesn't add up to 100%.")
        while True:
            self.__ui.show("\nHow the client says his wealth is split (percent)")
            split = {key: self.__ui.ask_money(f"  {label} %", ask) / 100
                     for key, label in [("property", "Property"), ("listed_equities", "Listed shares"),
                                        ("private_business", "Private business"), ("cash", "Cash")]}
            if 0.95 <= sum(split.values()) <= 1.05:
                return split
            self.__ui.show_error(f"That adds up to {sum(split.values()):.0%}. Please make it 100%.")

    def case_from_client_record(self, record: dict, ask: Ask | None = None) -> dict | None:
        """Build the forecasting case from a saved client record.

        Reads directly from the new flat structure. The officer is asked only for
        what's missing or unreadable.
        Returns None if the case fails validation.
        """
        ask = ask or self.__ui.read_answer
        if not record:
            return None
        career     = record.get("career", {})
        claims     = record.get("claims", {})
        self.__ui.show(ConsoleUI.LINE)
        self.__ui.show(f"Preparing {record.get('client_ref')} for the forecasting assessment")
        self.__ui.show(ConsoleUI.LINE)

        # The assessment is always dated today - the web app does the same (WebApp.assess_client).
        current_date = datetime.date.today().isoformat()
        self.__ui.show(f"Assessment date: {current_date} (today)")
        this_year = int(current_date[:4])

        age  = int(self._number_or_ask(career.get("age"), "Age", ask, allow_zero=False))
        jobs = self._jobs_from_record(record, this_year, ask)
        first_year = jobs[0]["start_year"]
        current    = jobs[-1]

        case = {
            "client_ref":   record["client_ref"],
            "current_date": current_date,
            "name":         self._text_or_ask(record.get("name"),        "Client name", ask),
            "nationality":  self._text_or_ask(record.get("nationality"), "Nationality", ask),
            "career": {
                "occupation":           current["occupation"],
                "seniority":            current["seniority"],
                "industry":             current["industry"],
                "employer_name":        current["employer_name"],
                "employer_size":        current["employer_size"],
                "country_of_residence": self._text_or_ask(career.get("country_of_residence"), "Country of residence", ask),
                "age":                  age,
                "career_start_year":    first_year,
            },
            "career_history": jobs,
            "investments":    self._assets_from_record(record, first_year, this_year, ask),
            "claims": {
                "declared_net_worth": self._number_or_ask(claims.get("declared_net_worth"),
                                                     "Declared net worth (SGD)", ask, allow_zero=False),
                "expected_aum":       self._number_or_ask(claims.get("expected_aum"),
                                                     "Expected AUM (SGD)", ask, allow_zero=False),
                "asset_composition":  self._composition_from_record(record, ask),
                "wealth_countries":   claims.get("wealth_countries")
                                      or [c.strip() for c in self.__ui.ask_text(
                                          "Countries his wealth came from (comma separated)", ask
                                      ).split(",") if c.strip()],
                "pep_status":         self._text_or_ask(claims.get("pep_status"), "PEP status (e.g. None)", ask),
                # not needed by the forecast, but the benchmark uses them (logic_manager.forecasting_case keeps them too)
                "biggest_wealth_jump":     self.__ui.read_number(claims.get("biggest_wealth_jump")),
                "wealth_jump_years":       self.__ui.read_number(claims.get("wealth_jump_years")),
                "declared_counterparties": list(claims.get("declared_counterparties") or []),
            },
            "sow_declaration": self._text_or_ask(record.get("sow_declaration"), "Source of wealth declaration", ask),
        }
        if len(case["sow_declaration"]) < 50:
            self.__ui.show_error("The source of wealth declaration is too short (50 characters minimum).")
            case["sow_declaration"] = self.__ui.ask_text("Source of wealth declaration (one paragraph)", ask, min_length=50)

        problems = self.validate_case(case)
        if problems:
            self.__ui.show_case_problems(case["client_ref"], problems)
            return None
        return case
