"""CaseReader: turns a saved client record into the case the features read."""


class CaseReader:
    """Reads a client record, whichever layout it was saved in, into one forecasting case:
    numbers as numbers, years as years, the career and the claims in one shape. It lists
    every problem that stops the case being used instead of guessing.

    today is the assessment date used when the record has none.
    """

    _PRESENT_WORDS = ("", "present", "now", "current", "-", "none")
    COMPOSITION_KEYS = ["property", "listed_equities", "private_business", "cash"]

    def __init__(self, today: str = "") -> None:
        self.__today: str = today

    @staticmethod
    def read_amount(text: str | int | float | None) -> float | None:
        """'1,650,000', 'S$1.65m', '410k', 30 -> a number; None if it can't be read."""
        if isinstance(text, bool):
            return None
        if isinstance(text, (int, float)):
            return float(text)
        cleaned = str(text or "").strip().lower().replace(",", "").replace(" ", "")
        for prefix in ("sgd", "s$", "$"):
            cleaned = cleaned.removeprefix(prefix)
        multiplier = 1.0
        for suffix, factor in (("million", 1e6), ("mil", 1e6), ("m", 1e6), ("k", 1e3), ("%", 1.0)):
            if cleaned.endswith(suffix):
                cleaned, multiplier = cleaned[: -len(suffix)], factor
                break
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None

    def read_year(self, text: str | int | float | None) -> int | None:
        value = CaseReader.read_amount(text)
        return int(value) if value is not None and 1900 <= value <= 2100 else None

    def _read_payment(self, text) -> str | None:
        """'Cash', 'mortgage', 'bank loan', 'sold my flat' -> cash / loan / asset_sale."""
        words = str(text or "").lower()
        if any(w in words for w in ("loan", "mortgage", "financ", "borrow")):
            return "loan"
        if any(w in words for w in ("sale", "sold", "proceeds")):
            return "asset_sale"
        if "cash" in words or "savings" in words:
            return "cash"
        return None

    def forecasting_case(self, record: dict) -> tuple[dict | None, list[str]]:
        """Turn a saved client record (from the web form, the command line or the documents
        auto-fill) into the case every part of the assessment uses, dated today.

        Returns (case, []) when everything can be read, otherwise (None, what's missing).
        The command line then asks the officer for what's missing (io_manager.case_from_client_record);
        the web app asks the officer to complete the record. Both assess the same case.
        """
        today = self.__today
        missing: list[str] = []
        career = record.get("career") or {}
        claims = record.get("claims") or {}
        this_year = int(today[:4])

        def text(value, label: str) -> str:
            found = str(value or "").strip()
            if not found:
                missing.append(label)
            return found

        age = CaseReader.read_amount(career.get("age"))
        if age is None or not 18 <= age <= 120:
            missing.append("age")

        jobs = []
        for number, entry in enumerate(record.get("career_history") or [], start=1):
            label = f"job {number}"
            start = self.read_year(entry.get("start_year"))
            if start is None or start > this_year:
                missing.append(f"{label} start year")
            end_text = "" if entry.get("end_year") is None else str(entry.get("end_year")).strip().lower()
            end = None if end_text in CaseReader._PRESENT_WORDS else self.read_year(entry.get("end_year"))
            if end_text not in CaseReader._PRESENT_WORDS and (end is None or end > this_year or (start and end < start)):
                missing.append(f"{label} end year")
            jobs.append({
                "start_year": start, "end_year": end,
                "occupation": text(entry.get("occupation"), f"{label} job title"),
                "seniority": text(entry.get("seniority"), f"{label} seniority"),
                "industry": text(entry.get("industry"), f"{label} industry"),
                "employer_name": text(entry.get("employer_name"), f"{label} employer"),
                "employer_size": text(entry.get("employer_size"), f"{label} employer size"),
                "country": text(entry.get("country"), f"{label} country"),
            })
        jobs.sort(key=lambda job: job["start_year"] or 0)

        # The command line keeps the current job in "career" only: it started when the last job
        # ended, or when his career started if there were no earlier jobs.
        if not jobs or jobs[-1]["end_year"] is not None:
            started = jobs[-1]["end_year"] if jobs else self.read_year(career.get("career_start_year"))
            if started is None:
                missing.append("current job start year")
            jobs.append({
                "start_year": started, "end_year": None,
                "occupation": text(career.get("occupation"), "current job title"),
                "seniority": text(career.get("seniority"), "current seniority"),
                "industry": text(career.get("industry"), "current industry"),
                "employer_name": text(career.get("employer_name"), "current employer"),
                "employer_size": text(career.get("employer_size"), "current employer size"),
                "country": text(career.get("country_of_residence"), "country of current job"),
            })

        investments = []
        for number, entry in enumerate(record.get("investments") or [], start=1):
            name = str(entry.get("asset_type") or "").strip() or f"Asset {number}"
            if str(entry.get("year_sold") or "").strip():
                continue                                   # sold assets are left out of the forecast
            currency = str(entry.get("currency") or "SGD").strip().upper()
            if currency not in ("", "SGD", "S$"):
                missing.append(f"{name}: amounts in SGD (recorded in {currency})")
            value = entry.get("current_declared_value")
            value = entry.get("current_value") if value in (None, "") else value
            income = entry.get("income_produced")
            income = entry.get("yearly_income") if income in (None, "") else income
            year = self.read_year(entry.get("year_acquired"))
            price = CaseReader.read_amount(entry.get("price_paid"))
            current = CaseReader.read_amount(value)
            produced = CaseReader.read_amount(income if income not in (None, "") else 0)
            method = self._read_payment(entry.get("payment_method"))
            for ok, label in ((year is not None and year <= this_year, "year bought"),
                              (price is not None and price > 0, "price paid"),
                              (current is not None and current >= 0, "current value"),
                              (produced is not None and produced >= 0, "yearly income"),
                              (method is not None, "how it was paid for")):
                if not ok:
                    missing.append(f"{name}: {label}")
            investments.append({"asset_type": name, "country": text(entry.get("country"), f"{name}: country"),
                                "year_acquired": year, "price_paid": price, "current_declared_value": current,
                                "payment_method": method, "income_produced": produced})

        typed = claims.get("asset_composition") or {}
        split = {key: CaseReader.read_amount(typed.get(key)) for key in CaseReader.COMPOSITION_KEYS}
        if all(v is not None for v in split.values()) and 95 <= sum(split.values()) <= 105:
            split = {k: v / 100 for k, v in split.items()}          # typed as percentages
        if any(v is None for v in split.values()) or not 0.95 <= sum(split.values()) <= 1.05:
            missing.append("asset composition adding up to 100%")

        worth = CaseReader.read_amount(claims.get("declared_net_worth"))
        aum = CaseReader.read_amount(claims.get("expected_aum"))
        if worth is None or worth <= 0:
            missing.append("declared net worth")
        if aum is None or aum <= 0:
            missing.append("expected assets with the bank")
        countries = [str(c).strip() for c in claims.get("wealth_countries") or [] if str(c).strip()]
        if not countries:
            missing.append("countries where the wealth came from")
        jump = CaseReader.read_amount(claims.get("biggest_wealth_jump"))
        jump_years = CaseReader.read_amount(claims.get("wealth_jump_years"))
        sow = text(record.get("sow_declaration"), "source of wealth declaration")
        if sow and len(sow) < 50:
            missing.append("source of wealth declaration of at least 50 characters")

        case = {
            "client_ref": record.get("client_ref"),
            "current_date": today,
            "name": text(record.get("name"), "name"),
            "nationality": text(record.get("nationality"), "nationality"),
            "career": {
                "occupation": jobs[-1]["occupation"], "seniority": jobs[-1]["seniority"],
                "industry": jobs[-1]["industry"], "employer_name": jobs[-1]["employer_name"],
                "employer_size": jobs[-1]["employer_size"],
                "country_of_residence": text(career.get("country_of_residence"), "country of residence"),
                "age": int(age) if age is not None else None,
                "career_start_year": jobs[0]["start_year"],
            },
            "career_history": jobs,
            "investments": investments,
            "claims": {
                "declared_net_worth": worth, "expected_aum": aum, "asset_composition": split,
                "wealth_countries": countries, "pep_status": text(claims.get("pep_status"), "PEP status"),
                # not needed by the forecast, but the benchmark uses them
                "biggest_wealth_jump": jump if jump and jump > 0 else None,
                "wealth_jump_years": jump_years if jump_years and jump_years > 0 else None,
                "declared_counterparties": [str(c).strip() for c in claims.get("declared_counterparties") or []
                                            if str(c).strip()],
            },
            "sow_declaration": sow,
        }
        missing = list(dict.fromkeys(missing))
        return (None, missing) if missing else (case, [])

    def crime_scan_input(self, record: dict) -> dict:
        """The crime scan input from a saved client record (used by both the CLI and the web app).
        Raises KeyError if the record has no career or no source of wealth declaration."""
        career = record["career"]
        sow = record["sow_declaration"]
        return {
            "client_ref":           record["client_ref"],
            "occupation":           career["occupation"],
            "industry":             career["industry"],
            "age":                  self._whole_number(career["age"]),
            "career_start_year":    self._whole_number(career["career_start_year"]),
            "country":              career["country_of_residence"],
            "country_of_residence": career["country_of_residence"],
            "declaration_text":     sow if isinstance(sow, str) else (sow or {}).get("declaration_text", ""),
        }

    def _whole_percent(self, value) -> int | None:
        """A share of wealth as a whole-number percent: 0.45 (stored fraction) or 45 -> 45."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return round(value * 100) if value <= 1.0 else round(value)

    def benchmark_input(self, record: dict, case_input: dict) -> tuple[dict, list[str]]:
        """The benchmark's input built from a saved client record - the CLI and the web app both use this,
        so the same client always gets the same benchmark. Composition is in whole percents (45 = 45%),
        the unit run_benchmark and the benchmark prompt expect.
        Returns (input, names of the required values that are missing)."""
        claims = record.get("claims") or {}
        split = claims.get("asset_composition") or {}
        worth = claims.get("declared_net_worth")
        jump = claims.get("biggest_wealth_jump")
        data = {
            **case_input,
            "declared_net_worth":      self._whole_number(worth),
            "listed_equities":         self._whole_percent(split.get("listed_equities")),
            "cash":                    self._whole_percent(split.get("cash")),
            "property":                self._whole_percent(split.get("property")),
            "private_business":        self._whole_percent(split.get("private_business")),
            "biggest_wealth_jump":     float(jump) if isinstance(jump, (int, float)) else None,
            "wealth_jump_years":       float(claims.get("wealth_jump_years") or 0.0),
            "declared_counterparties": list(claims.get("declared_counterparties") or []),
            "declared_countries":      list(claims.get("wealth_countries") or []),
        }
        missing = [key for key in ("declared_net_worth", "listed_equities", "cash", "property", "private_business")
                   if data[key] is None]
        return data, missing

    def _whole_number(self, value: object) -> int | None:
        """'16,500,000' / '30%' / 30 -> a whole number, or None if it can't be read."""
        try:
            return int(float(str(value).replace(",", "").replace("%", "").strip()))
        except (TypeError, ValueError):
            return None
