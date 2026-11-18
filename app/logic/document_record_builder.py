"""DocumentRecordBuilder: a client record pre-filled from what the AI read in his documents."""

import copy
import datetime
import re
from typing import Any

from app.logic.case_reader import CaseReader
from app.model.client_record import ClientRecord
from app.model.config import Config


class DocumentRecordBuilder:
    """Builds a client record from the AI's reading of uploaded documents, lists what is
    still missing, checks the record for values that cannot be right, and summarises it
    for the officer to review. Nothing is saved here: the officer confirms every value.

    The record it gives and takes is a ClientRecord; inside, it works on the record's saved
    layout, where every field has a path (["career_history", 0, "start_year"]).
    It stores the Config (asset names from the policy) and today's date.
    """

    SUMMARY_SECTIONS: dict[str, str] = {"name": "Client", "nationality": "Client", "career": "Client",
                        "career_history": "Career history", "investments": "Assets",
                        "claims": "Financial claims", "sow_declaration": "Source of wealth declaration"}

    def __init__(self, config: Config | None = None, today: str = "") -> None:
        if config is not None and not isinstance(config, Config):
            raise ValueError(f"the config must be a Config (or None), not {type(config).__name__}")
        if not isinstance(today, str) or (today and not CaseReader.is_iso_date(today)):
            raise ValueError(f"today must be empty or a real date written YYYY-MM-DD, not {today!r}")
        self.__config: Config = config or Config({}, {})
        self.__policy: dict = self.__config.policy
        self.__today: str = today

    def __age_from_birth(self, date_of_birth: str | None) -> int | None:
        """Whole years between date_of_birth and today, or None if either can't be read."""
        today = self.__today
        try:
            born = datetime.date.fromisoformat(str(date_of_birth))
            day = datetime.date.fromisoformat(today)
        except (TypeError, ValueError):
            return None
        age = day.year - born.year - ((day.month, day.day) < (born.month, born.day))
        return age if 0 < age < 130 else None

    def _blank(self, value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip()) or value == []

    def build(self, extracted: dict, client_ref: str) -> tuple[ClientRecord, list[str], list[dict]]:
        """Build a client record (the same layout the New Client form saves) from the AI's
        reading of the documents. Returns (record, paths of the fields that came from the documents,
        one entry for each field that was dropped: {"path", "message", "optional_field"}; the message
        is plain text, and optional_field is the field to ask for when the form does not insist on
        it, else None).

        Every job, including the current one (end_year None), goes into career_history, and
        the current job is copied into "career". The AI only helps and the officer checks everything:
        a value no client record can have (an age of 12, a negative price) is left empty, so it is
        asked for like any missing detail, and is named in the dropped messages; every good field
        is kept. Raises ValueError, saying what is wrong, only if the reading as a whole cannot be
        a record even with those fields left empty.
        """
        today = self.__today
        client = extracted.get("client") or {}
        claims = extracted.get("claims") or {}
        composition = extracted.get("composition") or {}

        jobs = [{key: job.get(key) for key in ("start_year", "end_year", "occupation", "seniority", "industry",
                                               "employer_name", "employer_size", "country")}
                for job in extracted.get("jobs") or []]
        # oldest first, current job (no end year) last - the order the forecasting checks
        jobs.sort(key=lambda job: (job["start_year"] if isinstance(job["start_year"], int) else 9999,
                                   job["end_year"] if isinstance(job["end_year"], int) else 9999))
        if not jobs:   # always at least one (current) job, so its details get asked for
            jobs = [{"start_year": None, "end_year": None, "occupation": None, "seniority": None,
                     "industry": None, "employer_name": None, "employer_size": None,
                     "country": client.get("country_of_residence")}]

        investments = []
        for asset in extracted.get("assets") or []:
            investments.append({
                "asset_type": asset.get("asset_type"),
                "country": asset.get("country"), "year_acquired": asset.get("year_acquired"),
                "price_paid": asset.get("price_paid_sgd"),
                "current_declared_value": asset.get("current_declared_value_sgd"),
                "payment_method": asset.get("payment_method"),
                "income_produced": asset.get("income_produced_sgd"),   # the AI gives every amount in SGD
            })

        # The AI gives percentages; a share it did not give stays empty and is asked for.
        split = {key: composition.get(key) / 100 if self.__is_number(composition.get(key)) else None
                 for key in CaseReader.COMPOSITION_KEYS}

        age = client.get("age") or self.__age_from_birth(client.get("date_of_birth"))
        record = {
            "client_ref": client_ref,
            "name": client.get("name"),
            "nationality": client.get("nationality"),
            "current_date": today,
            "career": {"country_of_residence": client.get("country_of_residence"), "age": age},
            "career_history": jobs,
            "investments": investments,
            "claims": {
                "declared_net_worth": claims.get("declared_net_worth_sgd"),
                "expected_aum": claims.get("expected_aum_sgd"),
                "pep_status": claims.get("pep_status"),
                "wealth_countries": claims.get("wealth_countries") or [],
                "asset_composition": split,
                "biggest_wealth_jump": claims.get("biggest_wealth_jump_sgd"),
                "wealth_jump_years": claims.get("wealth_jump_years"),
                "declared_counterparties": claims.get("declared_counterparties") or [],
            },
            "sow_declaration": extracted.get("sow_declaration"),
            "supporting_documents": [],
        }
        dropped: list[dict] = []
        try:
            client = ClientRecord.from_dict(self.__finish_layout(record))
        except (ValueError, TypeError):
            record, dropped = self.__without_impossible_fields(record)
            client = ClientRecord.from_dict(self.__finish_layout(record))      # still impossible: the whole reading
        found = [".".join(str(part) for part in item["path"])
                 for item in self._required_fields(record) if not self._missing(record, item)]
        return client, found, dropped

    def __leaf_paths(self, record: dict) -> list[list[str | int]]:
        """The path of every single value in a record that the AI's reading fills in."""
        paths: list[list[str | int]] = [["name"], ["nationality"], ["career", "country_of_residence"], ["career", "age"]]
        for section in ("career_history", "investments"):
            for index, row in enumerate(record.get(section) or []):
                paths += [[section, index, key] for key in row]
        paths += [["claims", key] for key in record["claims"] if key != "asset_composition"]
        paths += [["claims", "asset_composition", key] for key in record["claims"]["asset_composition"]]
        return paths + [["sow_declaration"]]

    def __without_impossible_fields(self, record: dict) -> tuple[dict, list[dict]]:
        """The record with each impossible value left empty, and one entry for each: {"path", "message",
        "optional_field"}. optional_field is the field (path, label, kind) when the form does not insist on
        it, so it will not be asked for with the missing details and the caller has to ask for it; it is
        None for a required field. A value is impossible when a record holding only that value
        (everything else empty) is rejected."""
        empty = copy.deepcopy(record)
        paths = self.__leaf_paths(record)
        for path in paths:
            self.__set(empty, path, [] if isinstance(self.get_path(record, path), list) else None)
        ClientRecord.from_dict(self.__finish_layout(empty))      # an empty record must be possible; else raise
        cleaned, found = copy.deepcopy(record), []
        for path in paths:
            value = self.get_path(record, path)
            if self._blank(value):
                continue
            trial = copy.deepcopy(empty)
            self.__set(trial, path, value)
            try:
                ClientRecord.from_dict(self.__finish_layout(trial))
            except (ValueError, TypeError) as error:
                self.__set(cleaned, path, [] if isinstance(value, list) else None)
                found.append((path, value, error))
        # the labels come from the cleaned record, so a job is named without its impossible value
        required = {tuple(field["path"]): field for field in self._required_fields(cleaned)}
        optional = {tuple(field["path"]): field for field in self._optional_fields(cleaned)}
        dropped = []
        for path, value, error in found:
            field = required.get(tuple(path)) or optional.get(tuple(path))
            if path[:2] == ["claims", "asset_composition"]:
                label = f"Asset composition: {path[2].replace('_', ' ')}"
                value = f"{value * 100:g}%" if isinstance(value, (int, float)) else value
            elif field:
                short = re.sub(r" \(blank[^)]*\)$", "", field["short"])
                label = (f"{field['group']}: " if field["group"] else "") + short
            else:
                label = " ".join(str(part) for part in path[-1:]).replace("_", " ")
            label = label[:1].upper() + label[1:]
            optional_field = None if tuple(path) in required else optional.get(tuple(path))
            ask = "You can enter it, or leave it empty." if optional_field else "Please enter it."
            dropped.append({"path": list(path), "optional_field": optional_field,
                            "message": f"{label}: the value read from the documents ({value}) is not possible "
                                       f"({error}), so it was left empty. {ask}"})
        return cleaned, dropped

    @staticmethod
    def __set(record: dict, path: list[str | int], value: Any) -> None:
        target = record
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value

    def get_path(self, record: dict, path: list[str | int]) -> Any:
        """The value at path (e.g. ["career_history", 0, "start_year"]), or None if it isn't there."""
        value = record
        for part in path:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and isinstance(part, int) and 0 <= part < len(value):
                value = value[part]
            else:
                return None
        return value

    def set_path(self, record: ClientRecord, path: list[str | int], value: Any) -> ClientRecord:
        """Return a copy of record with the value at path replaced. Raises ValueError, saying
        what is wrong, if the value is not possible there."""
        new = record.to_dict()
        target = new
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        return ClientRecord.from_dict(self.__finish_layout(new))

    def _field(self, path: list, short: str, kind: str, group: str = "", label: str = "") -> dict:
        """One form field. label is the full question (when asking); short + group are for the summary."""
        return {"path": path, "short": short, "kind": kind, "group": group,
                "label": label or (f"{group}: {short}" if group else short)}

    def _job_group(self, i: int, job: dict) -> str:
        years = f"{job.get('start_year') or '?'}-{job.get('end_year') or 'present'}"
        return f"Job {i + 1}: {job.get('occupation') or 'job'} at {job.get('employer_name') or 'unknown employer'} ({years})"

    def _asset_group(self, i: int, asset: dict) -> str:
        return f"Asset {i + 1}: {asset.get('asset_type') or 'asset'}"

    def _required_fields(self, record: dict) -> list[dict]:
        """Every field the New Client form insists on, with how it should be asked for."""
        fields = [
            self._field(["name"], "Full name", "words"),
            self._field(["nationality"], "Nationality", "words"),
            self._field(["career", "country_of_residence"], "Country of residence", "words"),
            self._field(["career", "age"], "Age", "age"),
        ]
        for i, job in enumerate(record.get("career_history", [])):
            group = self._job_group(i, job)
            fields += [
                self._field(["career_history", i, "start_year"], "start year", "year", group),
                self._field(["career_history", i, "occupation"], "job title", "label", group),
                self._field(["career_history", i, "seniority"], "seniority", "label", group),
                self._field(["career_history", i, "industry"], "industry", "label", group),
                self._field(["career_history", i, "employer_name"], "employer", "label", group),
                self._field(["career_history", i, "employer_size"], "employer size", "text", group,
                       f"{group}: employer size (e.g. 1,000-5,000 employees)"),
                self._field(["career_history", i, "country"], "country", "words", group),
            ]
        for i, asset in enumerate(record.get("investments", [])):
            group = self._asset_group(i, asset)
            fields += [
                self._field(["investments", i, "country"], "country", "words", group),
                self._field(["investments", i, "year_acquired"], "year acquired", "year", group),
                self._field(["investments", i, "price_paid"], "price paid (SGD)", "money_positive", group),
                self._field(["investments", i, "payment_method"], "how it was paid for", "payment", group),
                self._field(["investments", i, "current_declared_value"], "current value (SGD)", "money", group),
                self._field(["investments", i, "income_produced"], "yearly income (SGD)", "money", group,
                       f"{group}: yearly income (SGD, 0 if none)"),
            ]
        fields += [
            self._field(["claims", "declared_net_worth"], "Declared net worth (SGD)", "money_positive"),
            self._field(["claims", "expected_aum"], "Expected assets to be managed by the bank (SGD)", "money_positive"),
            self._field(["claims", "pep_status"], "PEP status", "pep"),
            self._field(["claims", "wealth_countries"], "Countries where wealth was generated", "countries",
                   label="Countries where wealth was generated (comma-separated)"),
            self._field(["claims", "asset_composition"], "Asset composition", "composition",
                   label="Asset composition (must add up to 100%)"),
            self._field(["sow_declaration"], "Source of wealth declaration", "sow"),
        ]
        return fields

    def _missing(self, record: dict, field: dict) -> bool:
        value = self.get_path(record, field["path"])
        kind = field["kind"]
        if kind == "composition":
            split = value or {}
            values = [split.get(key) for key in CaseReader.COMPOSITION_KEYS]
            return any(not isinstance(v, (int, float)) for v in values) or abs(sum(values) - 1.0) > 0.005
        if kind == "sow":
            return self._blank(value) or len(str(value).strip()) < 50
        if kind == "payment":
            return value not in ("cash", "loan", "asset_sale")
        if kind == "pep":
            return self._blank(value)
        return self._blank(value)

    def missing_fields(self, record: ClientRecord) -> list[dict]:
        """The required fields still empty (or unusable) after reading the documents, in form order."""
        data = record.to_dict()
        return [field for field in self._required_fields(data) if self._missing(data, field)]

    def finish(self, record: ClientRecord) -> ClientRecord:
        """The record with its current job (the one with no end year, else the last one listed)
        copied into "career" again - after the officer has edited the jobs."""
        return ClientRecord.from_dict(self.__finish_layout(record.to_dict()))

    def __finish_layout(self, record: dict) -> dict:
        """Copy the current job (the one with no end year) into "career", and the first job's start year
        into career_start_year - the same layout the New Client form saves."""
        record = copy.deepcopy(record)
        jobs = record.get("career_history", [])     # kept in document order so the summary lines up
        current = next((job for job in reversed(jobs) if job.get("end_year") in (None, "")), jobs[-1] if jobs else {})
        career = record.setdefault("career", {})
        for key in ("occupation", "seniority", "industry", "employer_name", "employer_size"):
            career[key] = current.get(key)
        starts = [job.get("start_year") for job in jobs if isinstance(job.get("start_year"), int)]
        career["career_start_year"] = min(starts) if starts else None
        return record

    def check(self, client: ClientRecord) -> list[str]:
        """Things worth a second look in a record filled from documents. Empty list = nothing spotted."""
        record = client.to_dict()
        today = self.__today
        if not today:
            raise ValueError("today's date is needed to check a record: make the DocumentRecordBuilder with it")
        warnings = []
        this_year = int(today[:4])
        age = record.get("career", {}).get("age")
        start = record.get("career", {}).get("career_start_year")
        if isinstance(age, int) and isinstance(start, int) and start < this_year - age + 14:
            warnings.append(f"Career start year {start} means the client started work before age 14.")
        for i, job in enumerate(record.get("career_history", []), start=1):
            s, e = job.get("start_year"), job.get("end_year")
            if isinstance(s, int) and isinstance(e, int) and e < s:
                warnings.append(f"Job {i} ends ({e}) before it starts ({s}).")
            if isinstance(s, int) and s > this_year:
                warnings.append(f"Job {i} starts in the future ({s}).")
        open_jobs = [job for job in record.get("career_history", []) if job.get("end_year") in (None, "")]
        if len(open_jobs) > 1:
            warnings.append(f"{len(open_jobs)} jobs have no end year; only one should be the current job.")
        for i, asset in enumerate(record.get("investments", []), start=1):
            year = asset.get("year_acquired")
            if isinstance(year, int) and isinstance(start, int) and year < start:
                warnings.append(f"Asset {i} was bought in {year}, before the client's career started ({start}).")
        claims = record.get("claims", {})
        worth, aum = claims.get("declared_net_worth"), claims.get("expected_aum")
        if isinstance(worth, (int, float)) and isinstance(aum, (int, float)) and aum > worth:
            warnings.append("Expected assets with the bank are more than the declared net worth.")
        held = sum(a.get("current_declared_value") or 0 for a in record.get("investments", [])
                   if isinstance(a.get("current_declared_value"), (int, float)))
        if isinstance(worth, (int, float)) and held > worth * 1.2:
            warnings.append(f"The listed assets are worth {held:,.0f}, well above the declared net worth {worth:,.0f}.")
        warnings += self._split_against_assets(record)
        return warnings

    def _split_against_assets(self, record: dict) -> list[str]:
        """Does the declared wealth split agree with the assets listed? Catches a value or a percentage
        read wrongly from the documents (or typed wrongly). Only checks kinds of asset that are listed."""
        policy = self.__policy
        claims = record.get("claims", {})
        worth = claims.get("declared_net_worth")
        split = claims.get("asset_composition") or {}
        if not isinstance(worth, (int, float)) or worth <= 0:
            return []
        totals = {}
        for asset in record.get("investments", []):
            kind = str(asset.get("asset_type") or "")
            value = asset.get("current_declared_value")
            key = self.__config.asset_category(kind) if policy.get("asset_categories") else None
            if key and key != "other" and isinstance(value, (int, float)):
                totals[key] = totals.get(key, 0) + value
        warnings = []
        for key, listed in totals.items():
            share = split.get(key)
            if not isinstance(share, (int, float)):
                continue
            declared = share * worth
            if abs(listed - declared) > 0.15 * max(declared, listed):
                label = key.replace("_", " ")
                warnings.append(f"The {label} assets listed are worth {listed:,.0f}, but the declared split puts "
                                f"{share:.0%} ({declared:,.0f}) of the net worth in {label}.")
        return warnings

    def _optional_fields(self, record: dict) -> list[dict]:
        """Fields shown in the summary that the form doesn't insist on."""
        fields = [self._field(["career_history", i, "end_year"], "end year (blank = current job)", "year", self._job_group(i, job))
                  for i, job in enumerate(record.get("career_history", []))]
        return fields + [
            self._field(["claims", "biggest_wealth_jump"], "Biggest single-period wealth increase (SGD)", "money"),
            self._field(["claims", "wealth_jump_years"], "Biggest wealth increase: over how many years", "money"),
            self._field(["claims", "declared_counterparties"], "Known counterparties", "countries"),
        ]

    def summarise(self, client: ClientRecord, doc_client: ClientRecord) -> list[dict]:
        """One row per field for the officer to check: its value and where it came from.

        source: "documents" (read from the documents, unchanged), "edited" (read from the documents,
        then changed by the officer), "entered" (typed by the officer) or "blank".
        """
        record, doc_record = client.to_dict(), doc_client.to_dict()
        rows = []
        fields = self._required_fields(record) + self._optional_fields(record)
        order = {name: i for i, name in enumerate(DocumentRecordBuilder.SUMMARY_SECTIONS.values())}
        for field in fields:
            value = self.get_path(record, field["path"])
            from_docs = self.get_path(doc_record, field["path"])
            if self._blank(value) or (field["kind"] == "composition" and self._missing(record, field)):
                source = "blank"
            elif self._blank(from_docs) or (field["kind"] == "composition" and self._missing(doc_record, field)):
                source = "entered"
            elif from_docs == value:
                source = "documents"
            else:
                source = "edited"
            rows.append({"section": DocumentRecordBuilder.SUMMARY_SECTIONS.get(field["path"][0], "Other"), "group": field["group"],
                         "label": field["short"], "kind": field["kind"], "value": value, "source": source,
                         "path": field["path"]})
        rows.sort(key=lambda row: (order.get(row["section"], 99),
                                  row["path"][1] if len(row["path"]) > 2 and isinstance(row["path"][1], int) else -1))
        return rows

    @staticmethod
    def __is_number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
