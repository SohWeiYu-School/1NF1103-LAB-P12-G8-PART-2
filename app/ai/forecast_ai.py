"""ForecastAI: the five-step forecast (declaration, markets, earnings, person types, events)."""

import json
import logging
import re
import time
from typing import Any, Callable

import jsonschema

from app.ai.ai_service import AIService
from app.ai.response_cache import ResponseCache
from app.model.claimed_source import ClaimedSource
from app.model.declaration import Declaration

logger = logging.getLogger(__name__)


class ForecastAI(AIService):
    """Runs the forecast as many small questions and checks every reply with its own rules.

    The steps run in order: Step 0 reads the declaration, Call 1 the markets, Call 2 the
    earnings and assets, Call 3 the person types, Call 4 the future events. Each reply is
    checked by its check method; what the code can fix by itself is fixed by a _repair_*
    method first. A reply that fails its checks is sent back with the reasons and asked
    again. The run stops at the first step that cannot be completed, and what finished
    is kept so the next run resumes there.

    The AI never sees the client's name or declared figures: _client_facts strips them.
    With no ai_caller (no API key) only saved replies are used.

    settings is the "forecasting" block of the policy; vocabulary is the name lists.
    """

    STAGES: tuple[str, ...] = ("step0_declaration", "call1_markets", "call2_earnings", "call3_types", "call4_events")
    SCENARIOS: tuple[str, ...] = ("steady", "boom", "downturn")
    RANGE_KEYS: tuple[str, ...] = ("low", "typical", "high")   # every AI figure comes as a range
    BASELINE_TYPE: str = "T1"                                  # T1 is always "exactly as declared"
    REPORTING_CURRENCY: str = "SGD"

    def __init__(self, provider: str = "", ai_caller: Callable | None = None, model: str = "", temperature: float = 0.0,
                 response_cache: ResponseCache | None = None, forecast_years: int = 4,
                 settings: dict | None = None, vocabulary: dict | None = None) -> None:
        super().__init__(provider, ai_caller, model, temperature, response_cache)
        self.__forecast_years: int = forecast_years
        self.__settings: dict = settings or {}
        self.__vocabulary: dict = vocabulary or {}
        self.__schemas: dict = {}

    def run(self, source: dict) -> dict | None:
        """Run Step 0 and Calls 1-4. source is {"record", "cache", "typologies", "on_step"}:
        cache is {piece name: raw reply} of saved replies; typologies are the crime scan's
        verified typologies; on_step is told each stage in STAGES as it starts.
        Returns {"ok", "failed_step", "failed_piece", "failed_error", "results", "forecast", "partial"}."""
        return self._run_forecast(source["record"], source.get("cache"), source.get("typologies"),
                                  source.get("on_step"))

    def read_declaration(self, record: dict) -> Declaration | None:
        """Step 0 on its own: asks the AI to read the free-text declaration and gives it as a
        Declaration of claimed sources, or None if the AI gave no usable reading.
        (run() is what reuses saved replies; this always asks.)"""
        return self._read_declaration(record, {}, {})

    def _payload(self, source: dict) -> dict:
        """The facts the AI may see about the client (no name, no declared figures)."""
        return self._client_facts(source["record"], include_declaration=True)

    def _post_process(self, data: dict, options: dict | None = None) -> dict:
        """Put every {low, typical, high} range in order."""
        return self._sort_ranges(data)

    # ----- settings and the client's timeline -------------------------------------

    def _settings(self) -> dict:
        return self.__settings

    def _vocabulary(self) -> dict:
        return self.__vocabulary

    def _can_ask(self) -> bool:
        """False when there is no AI caller: then only saved replies can be used."""
        return self._ai_caller is not None

    def _career_positions(self, record: dict) -> list[dict]:
        """His jobs, oldest first. Falls back to the current job if no history was given."""
        history = record.get("career_history") or []
        if history:
            return history
        career = record.get("career", {})
        return [{**career, "start_year": career.get("career_start_year"), "end_year": None}]

    def _current_year(self, record: dict) -> int:
        """The year of the assessment date, e.g. 2026 from '2026-09-24'."""
        return int(str(record.get("current_date", ""))[:4])

    def _career_years(self, record: dict) -> tuple[int, int]:
        """(first year he worked, current year)."""
        this_year = self._current_year(record)
        start_years = [p["start_year"] for p in self._career_positions(record) if p.get("start_year")]
        first = min(start_years) if start_years else this_year
        return int(first), this_year

    def _position_end(self, position: dict, this_year: int) -> int:
        """Last year a job was held. The current job runs to this year."""
        return int(position.get("end_year") or this_year)

    def _future_years(self, record: dict) -> list[int]:
        """The forecast years, e.g. [2027, 2028, 2029, 2030]."""
        this_year = self._current_year(record)
        return list(range(this_year + 1, this_year + self.__forecast_years + 1))

    # ----- prompts and schemas --------------------------------------------------------

    def _load_forecast_prompt(self, name: str) -> tuple[str, str]:
        """Read app/prompts/<name>.txt. Returns (version, text without the # note lines)."""
        template = self._load_prompt(name)
        return self._prompt_version(template), self._without_notes(template)

    def _fill_placeholders(self, text: str, values: dict) -> str:
        """Replace each {name} in the text. Fails loudly if a placeholder is left unfilled."""
        for key, value in values.items():
            text = text.replace("{" + key + "}", str(value))
        leftover = re.findall(r"\{[a-z_]+\}", text)
        if leftover:
            raise ValueError(f"prompt placeholders not filled: {sorted(set(leftover))}")
        return text

    def _build_instructions(self, prompt_name: str, values: dict, web_search: bool = False) -> tuple[str, str]:
        """System rules + the task prompt, filled in. Returns (prompt_version, instructions)."""
        declaration_open, declaration_close = self.__settings["declaration_markers"]
        shared = {"currency": ForecastAI.REPORTING_CURRENCY,
                  "declaration_open": declaration_open, "declaration_close": declaration_close}
        _, system_text = self._load_forecast_prompt("system")
        version, task_text = self._load_forecast_prompt(prompt_name)
        parts = [self._fill_placeholders(system_text, shared),
                 self._fill_placeholders(task_text, {**shared, **values})]
        if prompt_name in ("markets_list", "market_series") and not web_search:
            parts.append(self._load_forecast_prompt("no_web_search")[1])
        return version, "\n\n".join(parts)

    def _add_vocabulary(self, node: Any) -> Any:
        """Turn {"x-vocab": "signal_codes"} markers into a real list of allowed codes."""
        if isinstance(node, dict):
            if "x-vocab" in node:
                return {"type": "string", "enum": list(self.__vocabulary.get(node["x-vocab"], {}))}
            return {key: self._add_vocabulary(value) for key, value in node.items()}
        if isinstance(node, list):
            return [self._add_vocabulary(item) for item in node]
        return node

    def _load_forecast_schema(self, name: str) -> dict:
        """Read app/schemas/<name>.schema.json with the vocabulary codes filled in."""
        if name not in self.__schemas:
            self.__schemas[name] = self._add_vocabulary(self._load_schema(name))
        return self.__schemas[name]

    def _follows_schema(self, data: dict, schema: dict) -> tuple[bool, str | None]:
        """Check a reply against a JSON schema. Returns (True, None) or (False, error)."""
        try:
            jsonschema.validate(instance=data, schema=schema)
            return True, None
        except jsonschema.ValidationError as error:
            return False, error.message
        except Exception as error:
            return False, repr(error)

    def _extract_json(self, text: str) -> str:
        """The JSON object inside text that may be wrapped in a ``` block."""
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines[-1].strip() == "```":
                return "\n".join(lines[1:-1]).strip()
        start, end = stripped.find("{"), stripped.rfind("}")
        if start != -1 and end > start:
            return stripped[start:end + 1]
        return stripped

    # ---- Cleaning the input before it goes to the AI ----

    def _strip_keys(self, value: Any, keys: set) -> Any:
        """Remove the given keys from every dict inside value."""
        if isinstance(value, dict):
            return {k: self._strip_keys(v, keys) for k, v in value.items() if k.lower() not in keys}
        if isinstance(value, list):
            return [self._strip_keys(item, keys) for item in value]
        return value


    def _wrap_free_text(self, text: str, open_tag: str, close_tag: str) -> str:
        """Put free text between markers, removing any copies of the markers inside it."""
        cleaned = (text or "").replace(open_tag, "").replace(close_tag, "")
        return f"{open_tag}\n{cleaned.strip()}\n{close_tag}"


    def _client_facts(self, record: dict, include_declaration: bool = False) -> dict:
        """The facts the AI may see: jobs, assets (no claimed values), named countries, PEP status."""
        claims = record.get("claims", {})
        facts = {
            "current_date": record.get("current_date"),
            "career": record.get("career", {}),
            "career_history": [{"position_index": i, **job}
                               for i, job in enumerate(self._career_positions(record))],
            "assets": [{"asset_index": i, **asset} for i, asset in enumerate(record.get("investments", []))],
            "countries_named_by_client": claims.get("wealth_countries", []),
            "pep_status": claims.get("pep_status"),
        }
        settings = self._settings()
        if include_declaration:
            names = [str(record[key]) for key in settings["personal_keys"] if record.get(key)]
            text = self._redact_names(record.get("sow_declaration", ""), names, settings["honorifics"])
            facts["sow_declaration"] = self._wrap_free_text(text, *settings["declaration_markers"])
        facts = self._strip_keys(facts, set(settings["personal_keys"]))
        return self._strip_keys(facts, set(settings["claimed_figure_keys"]))


    # ---- Checking the AI's reply: general checks ----

    def _range_errors(self, value: Any, where: str = "") -> list[str]:
        """Every {low, typical, high} range must be in order."""
        errors = []
        if isinstance(value, dict):
            if set(value) == set(ForecastAI.RANGE_KEYS):
                if not value["low"] <= value["typical"] <= value["high"]:
                    errors.append(f"{where or '<root>'}: range out of order {value}")
                return errors
            for key, item in value.items():
                errors += self._range_errors(item, f"{where}/{key}" if where else key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                errors += self._range_errors(item, f"{where}/{index}")
        return errors


    def _sort_ranges(self, value: Any) -> Any:
        """Put every {low, typical, high} range in order (e.g. -1/-2/-3 for a fall becomes -3/-2/-1).
        The model sometimes labels a negative range back to front; the three numbers are kept,
        only relabelled, so nothing is invented. Same reply in, same result out."""
        if isinstance(value, dict):
            if set(value) == set(ForecastAI.RANGE_KEYS):
                numbers = [value[k] for k in ForecastAI.RANGE_KEYS]
                if all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in numbers):
                    value["low"], value["typical"], value["high"] = sorted(numbers)
                return value
            for item in value.values():
                self._sort_ranges(item)
        elif isinstance(value, list):
            for item in value:
                self._sort_ranges(item)
        return value


    def _parse_reply(self, raw: str | None) -> tuple[dict | None, str | None]:
        """Pull the JSON object out of the model's reply. Returns (data, error)."""
        if not raw or not raw.strip():
            return None, "empty reply (possible refusal or cut-off)"
        try:
            return json.loads(self._extract_json(raw)), None
        except json.JSONDecodeError as error:
            return None, f"invalid JSON: {error}"


    def _top_level_keys(self, schema: dict) -> list[str]:
        """The keys the answer must have at the top level."""
        return list(schema.get("required") or schema.get("properties", {}).keys())


    def _looks_like_schema(self, data: object) -> bool:
        """The model sometimes sends the schema back instead of filling it in."""
        return isinstance(data, dict) and ("$schema" in data or {"type", "properties"} <= set(data))


    def _validate_reply(self, raw: str | None, schema: dict,
                       check: Callable[[dict], list[str]] | None = None) -> tuple[dict | None, list[str]]:
        """Parse, then check the schema, then the ranges, then the piece's own rules."""
        data, error = self._parse_reply(raw)
        if error:
            return None, [error]
        if self._looks_like_schema(data) and not self._looks_like_schema(schema.get("properties", {})):
            keys = ", ".join(f'"{k}"' for k in self._top_level_keys(schema))
            return None, [f"you returned the JSON schema itself instead of an answer. Return the ANSWER: "
                          f"one JSON object whose top-level keys are {keys}, filled in with real values."]
        valid, error = self._follows_schema(data, schema)
        errors = [] if valid else [f"does not follow the schema: {error}"]
        if not errors:
            errors = self._range_errors(self._sort_ranges(data))
        if not errors and check is not None:
            errors = check(data)
        return (data if not errors else None), errors


    def _years_errors(self, label: str, found: list[int], expected: list[int]) -> list[str]:
        """The years must be exactly the expected ones, once each."""
        errors = []
        missing = [year for year in expected if year not in found]
        repeated = sorted({year for year in found if found.count(year) > 1})
        unexpected = sorted({year for year in found if year not in expected})
        if missing:
            errors.append(f"{label}: missing years {missing}")
        if repeated:
            errors.append(f"{label}: repeated years {repeated}")
        if unexpected:
            errors.append(f"{label}: unexpected years {unexpected}")
        return errors


    def _unknown_ids(self, label: str, used: list, known: set) -> list[str]:
        """An error if any id was used that is not in the known set."""
        unknown = sorted(set(used) - known)
        return [f"{label} uses unknown ids {unknown}"] if unknown else []


    # ---- Checking the AI's reply: one check per kind of piece ----
    # Each check_* returns a list of problems (empty = fine); the problems are sent back to
    # the AI on the retry. Each repair_* first fixes what the code can work out by itself.

    def __check_declaration(self, data: dict, job_count: int, asset_count: int) -> list[str]:
        """Step 0: sources have unique ids, link to real jobs/assets, and years are in order."""
        errors = []
        ids = [s["source_id"] for s in data["claimed_sources"]]
        if not ids:
            errors.append("at least one claimed source is required")
        if len(ids) != len(set(ids)):
            errors.append("source_id values must be unique")
        for source in data["claimed_sources"]:
            job, asset = source["linked_position_index"], source["linked_asset_index"]
            if job is not None and not 0 <= job < job_count:
                errors.append(f"{source['source_id']}: linked_position_index {job} doesn't exist")
            if asset is not None and not 0 <= asset < asset_count:
                errors.append(f"{source['source_id']}: linked_asset_index {asset} doesn't exist")
            if source["start_year"] and source["end_year"] and source["start_year"] > source["end_year"]:
                errors.append(f"{source['source_id']}: start_year is after end_year")
            if source["amount"] is not None and source["amount"] < 0:
                errors.append(f"{source['source_id']}: amount cannot be negative (use null if not stated)")
        return errors


    def __check_markets(self, data: dict, forecast_years: list[int]) -> list[str]:
        """Call 1 list: market ids are unique and simple; yearly chances add up to 100."""
        ids = [m["market_id"] for m in data["relevant_markets"]]
        errors = [] if ids else ["at least one market is required"]
        if len(ids) != len(set(ids)):
            errors.append("market_id values must be unique")
        errors += [f"market_id '{i}' may only use letters, digits and _" for i in ids
                   if not re.fullmatch(r"[A-Za-z0-9_]+", i)]
        # One steady/boom/downturn split per forecast year (the range allows for rounding)
        lowest, highest = self._settings()["scenario_chance_total_range"]
        chances = data["scenario_chances"]
        errors += self._years_errors("scenario_chances", [c["year"] for c in chances], forecast_years)
        for c in chances:
            total = c["steady"] + c["boom"] + c["downturn"]
            if not lowest <= total <= highest or min(c["steady"], c["boom"], c["downturn"]) < 0:
                errors.append(f"scenario_chances {c['year']}: chances must be 0-100 and add up to 100")
        return errors


    def _check_market_series(self, data: dict, market_id: str, history_years: list[int],
                            forecast_years: list[int]) -> list[str]:
        """Call 1 series: every year is there once, and the yearly changes are believable."""
        errors = [] if data["market_id"] == market_id else [f"market_id must be '{market_id}'"]
        errors += self._years_errors(f"{market_id} history", [h["year"] for h in data["history"]], history_years)
        errors += self._years_errors(f"{market_id} outlook", [o["year"] for o in data["outlook"]], forecast_years)
        # All zeros means the model didn't know and filled in 0
        settings = self._settings()
        known = [h["change_pct"] for h in data["history"] if h["change_pct"] is not None]
        if len(known) >= settings["all_zero_history_min_years"] and all(change == 0 for change in known):
            errors.append(f"{market_id} history: every year is 0. Use null for years you don't know; "
                          "0 means the market really didn't move")
        # A change far outside the range is usually an index level, not a % change
        low, high = settings["market_change_range"]
        errors += [f"{market_id} {h['year']}: {h['change_pct']}% is not a believable one-year change "
                   f"(give the % change from the year before, not an index level)"
                   for h in data["history"] if h["change_pct"] is not None and not low <= h["change_pct"] <= high]
        return errors


    def _check_position_pay(self, data: dict, index: int, years: list[int]) -> list[str]:
        """Call 2 job pay: right job, and one row for every year the job was held."""
        errors = [] if data["position_index"] == index else [f"position_index must be {index}"]
        errors += self._years_errors(f"job {index}", [row["year"] for row in data["yearly"]], years)
        return errors


    def __check_pay(self, data: dict, forecast_years: list[int]) -> list[str]:
        """Call 2 future pay: one row for every forecast year."""
        return self._years_errors("future pay", [row["year"] for row in data["yearly"]], forecast_years)

    def __check_asset_model(self, data: dict, index: int, years: list[int], market_ids: set) -> list[str]:
        """Call 2 asset: follows known markets, and its numbers sit inside the sense limits."""
        settings = self._settings()
        errors = [] if data["asset_index"] == index else [f"asset_index must be {index}"]
        if not data["exposures"]:
            errors.append("at least one market exposure is required")
        errors += self._unknown_ids("exposures", [e["market_id"] for e in data["exposures"]], market_ids)
        if len(data["exposures"]) > settings["max_asset_exposures"]:
            errors.append(f"at most {settings['max_asset_exposures']} market exposures: only the markets that really drive "
                          f"this asset's value (e.g. a property follows its property market and currency)")
        low, high = settings["sensitivity_range"]
        for exposure in data["exposures"]:
            values = exposure["sensitivity"].values()
            if not all(low <= v <= high for v in values):
                errors.append(f"{exposure['market_id']}: sensitivity {exposure['sensitivity']} must be between "
                              f"{low} and {high} (1.0 = the asset moves 1% when the market moves 1%)")
        low, high = settings["own_growth_range"]
        if not all(low <= v <= high for v in data["own_growth_pct"].values()):
            errors.append(f"own_growth_pct {data['own_growth_pct']} must be between {low} and {high} (% a year)")
        errors += self._years_errors(f"asset {index} income_yield_by_year",
                                [row["year"] for row in data["income_yield_by_year"]], years)
        return errors


    def _repair_asset_model(self, data: dict, market_ids: set) -> dict:
        """Fix an asset's reply where the code can, before it is checked: drop markets that aren't in
        the list, keep only the strongest links (by typical sensitivity) up to the limit, and bring
        sensitivities and own growth inside the sense limits. Missing years are NOT invented, so those
        still go back to the AI. Same reply in, same repair out."""
        if not isinstance(data, dict):
            return data
        settings = self._settings()
        low, high = settings["sensitivity_range"]
        exposures = [e for e in data.get("exposures") or []
                     if isinstance(e, dict) and e.get("market_id") in market_ids and isinstance(e.get("sensitivity"), dict)]
        exposures.sort(key=lambda e: -abs(float(e["sensitivity"].get("typical") or 0)))
        for exposure in exposures:
            exposure["sensitivity"] = {k: min(max(float(v), low), high) if isinstance(v, (int, float)) else v
                                       for k, v in exposure["sensitivity"].items()}
        if exposures:
            data["exposures"] = exposures[:settings["max_asset_exposures"]]
        growth_low, growth_high = settings["own_growth_range"]
        if isinstance(data.get("own_growth_pct"), dict):
            data["own_growth_pct"] = {k: min(max(float(v), growth_low), growth_high) if isinstance(v, (int, float)) else v
                                      for k, v in data["own_growth_pct"].items()}
        return data


    def _fallback_asset_model(self, index: int, bought: int, end: int) -> dict:
        """Used only when the AI can't describe an asset even after repairs: the asset is valued at
        its purchase price with no income, so it can't make his wealth look better explained than it
        is. The report says the asset couldn't be modelled."""
        flat = {"low": 0.0, "typical": 0.0, "high": 0.0}
        return {"asset_index": index, "exposures": [], "own_growth_pct": dict(flat),
                "income_yield_by_year": [{"year": y, "yield_pct": dict(flat)} for y in range(bought, end + 1)],
                "future_income_yield_pct": {s: dict(flat) for s in ForecastAI.SCENARIOS},
                "valuation_basis": "Not modelled: the AI's answers failed the sense checks, so it is held at its purchase price.",
                "fallback": True}


    def _link_typologies(self, data: dict, researched: list[dict]) -> dict:
        """Tie each crime type to the researched typology it was built from, before the reply is checked.

        A typology_id that isn't one of the researched typologies is cleared. A type with no
        typology_id whose category matches a researched typology's crime_category is linked to it
        (older saved replies have no typology_id at all). A linked type takes its typology's
        category, unless another type already uses that category. Same reply in, same result out.
        """
        by_id = {t["typology_id"]: t for t in researched}
        types = data.get("person_types") if isinstance(data, dict) else None
        if not isinstance(types, list):
            return data
        used_categories = {t.get("category") for t in types if isinstance(t, dict)}
        linked = set()
        for person_type in types:
            if not isinstance(person_type, dict):
                continue
            if person_type.get("type_id") == ForecastAI.BASELINE_TYPE:
                person_type["typology_id"] = None
                continue
            typology_id = person_type.get("typology_id")
            if typology_id not in by_id or typology_id in linked:
                typology_id = next((t["typology_id"] for t in researched
                                    if t.get("crime_category") == person_type.get("category")
                                    and t["typology_id"] not in linked), None)
            person_type["typology_id"] = typology_id
            if typology_id is None:
                continue
            linked.add(typology_id)
            category = by_id[typology_id].get("crime_category")
            if category and category != person_type.get("category") and category not in used_categories:
                used_categories.discard(person_type.get("category"))
                person_type["category"] = category
                used_categories.add(category)
        return data


    def _repair_person_types(self, data: dict, record: dict, source_records: list[ClaimedSource]) -> dict:
        """Fix the years the code can work out itself, before the reply is checked.

        T1 (honest) always covers his whole career and every forecast year. A crime type's
        years are moved inside the window of the job / asset / source that enables it
        (e.g. open from 2008 through a job held 2015-2019 becomes 2015). Only a type whose
        years can't overlap its enabler at all is left for check_person_types to reject.
        Same reply in, same repair out, so saved replies give identical results.
        """
        start, end = self._career_years(record)
        last_forecast_year = self._future_years(record)[-1]
        jobs = self._career_positions(record)
        assets = record.get("investments", [])
        sources = {s.source_id: s for s in source_records}
        for person_type in data.get("person_types", []):
            if person_type.get("type_id") == ForecastAI.BASELINE_TYPE:
                person_type["open_from"], person_type["open_to"] = start, last_forecast_year
                if not person_type.get("rule_out_documents"):
                    # the documents that test the declared story as a whole (policy: NET_WORTH)
                    codes = self._settings().get("net_worth_documents") \
                        or ["DOC_TAX_RETURNS", "DOC_BANK_STATEMENTS"]
                    person_type["rule_out_documents"] = [{"document_code": c, "also_rules_out": []} for c in codes]
                continue

            # A crime type: collect the years each enabler (job, asset, source) existed
            windows = []
            job_index = person_type.get("enabled_by_position_index")
            if isinstance(job_index, int) and 0 <= job_index < len(jobs):
                job = jobs[job_index]
                job_last = last_forecast_year if not job.get("end_year") else self._position_end(job, end)
                windows.append((int(job["start_year"]), job_last))
            asset_index = person_type.get("enabled_by_asset_index")
            if isinstance(asset_index, int) and 0 <= asset_index < len(assets):
                windows.append((int(assets[asset_index]["year_acquired"]), last_forecast_year))
            source = sources.get(person_type.get("enabled_by_source_id"))
            if source is not None:
                windows.append((int(source.start_year or start), last_forecast_year))
            if not windows:
                continue

            # Move the type's years inside those windows, if they overlap at all
            first = max([start, min(w[0] for w in windows)])
            last = min([last_forecast_year, max(w[1] for w in windows)])
            open_from, open_to = person_type.get("open_from"), person_type.get("open_to")
            if not isinstance(open_from, int) or not isinstance(open_to, int):
                continue
            new_from, new_to = max(open_from, first), min(open_to, last)
            if new_from <= new_to and (new_from, new_to) != (open_from, open_to):
                logger.info("%s: years %d-%d moved to %d-%d to fit what enables it",
                            person_type.get("type_id"), open_from, open_to, new_from, new_to)
                person_type["open_from"], person_type["open_to"] = new_from, new_to
        return data


    def __check_person_types(self, data: dict, record: dict, source_records: list[ClaimedSource]) -> list[str]:
        """Call 3 list: T1 is the honest person, the rest are crime types.

        Each crime type is ONE standard category from the vocabulary, tied to the job, asset
        or declared source that makes it possible for him, and open only in the years that
        job/asset/source existed.
        """
        types = data["person_types"]
        ids = [t["type_id"] for t in types]
        start, end = self._career_years(record)
        last_forecast_year = self._future_years(record)[-1]
        jobs = self._career_positions(record)
        sources = {s.source_id: s for s in source_records}
        assets = record.get("investments", [])
        errors = []

        if not ids or ids[0] != ForecastAI.BASELINE_TYPE:
            errors.append(f"the first type must be {ForecastAI.BASELINE_TYPE} (wealth exactly as declared)")
        if len(ids) < 2:
            errors.append("at least one crime type besides the honest one is required")
        settings = self._settings()
        max_crime_types = settings["max_crime_types"]
        if len(ids) - 1 > max_crime_types:
            errors.append(f"at most {max_crime_types} crime types, ranked most relevant first; got {len(ids) - 1}")
        if len(ids) != len(set(ids)):
            errors.append("type_id values must be unique")

        honest_category = settings["honest_category"]
        categories = [t["category"] for t in types]
        if types and categories[0] != honest_category:
            errors.append(f"{ForecastAI.BASELINE_TYPE} must use category {honest_category}")
        if honest_category in categories[1:]:
            errors.append(f"only {ForecastAI.BASELINE_TYPE} may use category {honest_category}")
        crime_categories = categories[1:]
        if len(crime_categories) != len(set(crime_categories)):
            errors.append("each crime category may appear only once")

        for person_type in types:
            type_id = person_type["type_id"]
            first, last = person_type["open_from"], person_type["open_to"]
            if not start <= first <= last <= last_forecast_year:
                errors.append(f"{type_id}: open years must sit inside {start}-{last_forecast_year}, "
                              f"open_from <= open_to (got {first}-{last})")
            for document in person_type["rule_out_documents"]:
                errors += self._unknown_ids(f"{type_id} also_rules_out", document["also_rules_out"], set(ids))
            if type_id != ForecastAI.BASELINE_TYPE and not person_type["rule_out_documents"]:
                errors.append(f"{type_id}: list at least one document that would prove this type wrong")
            if type_id == ForecastAI.BASELINE_TYPE:
                # The honest type covers his whole career and every forecast year.
                if (first, last) != (start, last_forecast_year):
                    errors.append(f"{type_id}: open_from/open_to must be {start}-{last_forecast_year}")
                continue

            # What makes this crime possible for HIM. At least one link, and the years must fit it.
            job_index = person_type["enabled_by_position_index"]
            asset_index = person_type["enabled_by_asset_index"]
            source_id = person_type["enabled_by_source_id"]
            if job_index is None and asset_index is None and source_id is None:
                errors.append(f"{type_id}: must name the job, asset or declared source that makes it possible")
            if job_index is not None:
                if not 0 <= job_index < len(jobs):
                    errors.append(f"{type_id}: enabled_by_position_index {job_index} doesn't exist")
                else:
                    job = jobs[job_index]
                    job_first = int(job["start_year"])
                    # A job he still holds can carry the crime into the forecast years; a past job can't.
                    job_last = last_forecast_year if not job.get("end_year") else self._position_end(job, end)
                    if not job_first <= first <= job_last:
                        errors.append(f"{type_id}: open_from {first} must fall while job {job_index} was held "
                                      f"({job_first}-{job_last})")
                    elif asset_index is None and source_id is None and last > job_last:
                        errors.append(f"{type_id}: open_to {last} is after job {job_index} ended ({job_last}); "
                                      f"a crime that only this job enables must stop when the job does")
            if asset_index is not None:
                if not 0 <= asset_index < len(assets):
                    errors.append(f"{type_id}: enabled_by_asset_index {asset_index} doesn't exist")
                elif first < int(assets[asset_index]["year_acquired"]):
                    errors.append(f"{type_id}: open_from {first} is before asset {asset_index} was bought "
                                  f"({assets[asset_index]['year_acquired']})")
            if source_id is not None:
                if source_id not in sources:
                    errors.append(f"{type_id}: enabled_by_source_id '{source_id}' is not a declared source")
                elif sources[source_id].start_year and first < int(sources[source_id].start_year):
                    errors.append(f"{type_id}: open_from {first} is before declared source {source_id} "
                                  f"started ({sources[source_id].start_year})")
        return errors


    def _repair_type_behaviour(self, data: dict, type_id: str, end: int, forecast_years: list[int],
                              open_years: tuple[int, int] | None, market_ids: set) -> dict:
        """Fix what the code can work out itself, before the reply is checked.

        The type id and route years come from the type list. Years outside the route (or
        repeated) are dropped, and so are unknown market ids. Missing years are NOT invented,
        so those still go back to the AI.
        """
        data["type_id"] = type_id
        if open_years is not None:
            data["route_open_from"], data["route_open_to"] = open_years
        first, last = data.get("route_open_from"), data.get("route_open_to")
        if isinstance(first, int) and isinstance(last, int):
            history_years = set(range(first, min(last, end) + 1))
            for key, allowed in (("extra_money_history", history_years), ("extra_money_forecast", set(forecast_years))):
                rows, seen = [], set()
                for row in data.get(key) or []:
                    year = row.get("year") if isinstance(row, dict) else None
                    if year in allowed and year not in seen:
                        seen.add(year)
                        rows.append(row)
                data[key] = rows
        if isinstance(data.get("linked_market_ids"), list):
            data["linked_market_ids"] = [m for m in data["linked_market_ids"] if m in market_ids]
        return data


    def _repair_type_reactions(self, data: dict, type_id: str, event_ids: list[str]) -> dict:
        """Keep one reaction per known event (extras and repeats dropped). Missing ones still go back to the AI."""
        data["type_id"] = type_id
        kept, seen = [], set()
        for reaction in data.get("reactions") or []:
            event_id = reaction.get("event_id") if isinstance(reaction, dict) else None
            if event_id in event_ids and event_id not in seen:
                seen.add(event_id)
                kept.append(reaction)
        data["reactions"] = kept
        return data


    def _check_type_behaviour(self, data: dict, type_id: str, start: int, end: int,
                             forecast_years: list[int], market_ids: set,
                             open_years: tuple[int, int] | None = None) -> list[str]:
        """Call 3 behaviour: route years match the type list, every year is there, signals make sense."""
        errors = [] if data["type_id"] == type_id else [f"type_id must be '{type_id}'"]
        first, last = data["route_open_from"], data["route_open_to"]
        if not start <= first <= last <= forecast_years[-1]:
            errors.append(f"route years must sit inside {start}-{forecast_years[-1]}, first <= last")
        if open_years is not None and (first, last) != tuple(open_years):
            errors.append(f"route years must be {open_years[0]}-{open_years[1]}, the years given in the type list")
        history_years = list(range(first, min(last, end) + 1)) if first <= end else []
        errors += self._years_errors("extra_money_history", [h["year"] for h in data["extra_money_history"]],
                                history_years)
        errors += self._years_errors("extra_money_forecast", [f["year"] for f in data["extra_money_forecast"]],
                                forecast_years)
        errors += self._unknown_ids("linked_market_ids", data["linked_market_ids"], market_ids)
        if not data["signals"]:
            errors.append("at least one signal is required")
        for signal in data["signals"]:
            if signal["first_year"] > signal["last_year"]:
                errors.append(f"{signal['signal_code']}: first_year is after last_year")
            if signal["amount_per_year"]["high"] <= 0:
                errors.append(f"{signal['signal_code']}: amount_per_year is 0; give the money this activity "
                              f"would really show in his account each year (in SGD)")
        salary_signal = self._settings()["honest_required_signal"]
        if type_id == ForecastAI.BASELINE_TYPE and salary_signal not in {s["signal_code"] for s in data["signals"]}:
            errors.append(f"the honest type must include his regular salary ({salary_signal}) among its signals")
        return errors


    def __check_events(self, data: dict, forecast_years: list[int], market_ids: set) -> list[str]:
        """Call 4 list: the right number of events, each in a forecast year and hitting a known market."""
        events = data["events"]
        ids = [e["event_id"] for e in events]
        settings = self._settings()
        errors = []
        if not settings["min_events"] <= len(events) <= settings["max_events"]:
            errors.append(f"expected {settings['min_events']}-{settings['max_events']} events, got {len(events)}")
        if len(ids) != len(set(ids)):
            errors.append("event_id values must be unique")
        for event in events:
            if event["year"] not in forecast_years:
                errors.append(f"{event['event_id']}: year must be one of {forecast_years}")
            if not event["shocks"]:
                errors.append(f"{event['event_id']}: needs at least one market shock")
            errors += self._unknown_ids(event["event_id"], [s["market_id"] for s in event["shocks"]], market_ids)
        return errors


    def _check_type_reactions(self, data: dict, type_id: str, event_ids: list[str]) -> list[str]:
        """Call 4 reactions: exactly one reaction per event."""
        errors = [] if data["type_id"] == type_id else [f"type_id must be '{type_id}'"]
        found = sorted(r["event_id"] for r in data["reactions"])
        if found != sorted(event_ids):
            errors.append(f"reactions need exactly one entry per event {event_ids}, got {found}")
        return errors


    # ---- Sending one request: retry, validate, log, never crash ----

    def _empty_result(self, call_name: str, prompt_version: str) -> dict:
        """The result dict every call returns, filled in as 'not done yet'."""
        return {"call": call_name, "ok": False, "data": None, "raw": None, "attempts": 0,
                "from_cache": False, "error": None, "prompt_version": prompt_version}


    def _ask(self, call_name: str, prompt_name: str, values: dict, user_data: dict,
                        schema_name: str, check: Callable[[dict], list[str]] | None = None,
                        cached_raw: str | None = None, web_search: bool = False) -> dict:
        """Send one forecasting request and return a checked result. Never raises.

        call_name    name of this piece (also its key in the saved replies)
        prompt_name  prompt file to use; values fill its {placeholders}
        user_data    the facts sent to the AI
        schema_name  schema the reply must follow; check adds the piece's own rules
        cached_raw   a saved reply to reuse instead of asking again
        Returns {"call", "ok", "data", "raw", "attempts", "from_cache", "error", "prompt_version"}.
        """
        try:
            settings = self._settings()
            version, instructions = self._build_instructions(prompt_name, values, web_search)
            schema = self._load_forecast_schema(schema_name)
        except (OSError, ValueError, KeyError) as error:  # a missing or broken prompt/schema/policy file
            result = self._empty_result(call_name, prompt_name)
            result["error"] = f"could not prepare the request: {error}"
            logger.error("%s: %s", call_name, result["error"])
            return result
        result = self._empty_result(call_name, version)

        # A saved reply for this request: reuse it so reruns are identical and free
        if cached_raw:
            data, errors = self._validate_reply(cached_raw, schema, check)
            if not errors:
                result.update(ok=True, data=data, raw=cached_raw, from_cache=True)
                logger.info("%s: using saved reply", call_name)
                return result
            logger.warning("%s: saved reply no longer valid (%s), asking again", call_name, errors[:2])

        if not self._can_ask():
            result["error"] = "no AI service is available: no API key (is OPENAI_API_KEY set?)"
            logger.error("%s: %s", call_name, result["error"])
            return result

        prompt = self._build_prompt(instructions, json.dumps(user_data, indent=2, ensure_ascii=False), schema)
        max_retries = settings["max_retries"]
        model_option = {"model": self._model} if self._model else {}
        last_errors: list[str] = []

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt
            message = prompt
            if last_errors:
                # The same prompt at temperature 0 would repeat the mistake, so say what to fix
                message += ("\n\nYOUR PREVIOUS ANSWER WAS REJECTED because:\n- " + "\n- ".join(last_errors[:settings["max_errors_sent_back"]])
                            + "\nReturn a complete, corrected JSON object.")
            if web_search:
                raw = self._ai_caller(message, schema, {"web_search": True, **model_option})
            else:
                raw = self._ai_caller(message, schema, dict(model_option))
            if raw is None:
                result["error"] = "the AI request failed (details in logs/app.log)"
                logger.warning("%s: attempt %d failed", call_name, attempt)
                if attempt < max_retries:
                    time.sleep(settings["retry_wait_seconds"] * attempt)
                continue

            data, errors = self._validate_reply(raw, schema, check)
            if not errors:
                result.update(ok=True, data=data, raw=raw, error=None)
                logger.info("%s: valid reply on attempt %d", call_name, attempt)
                return result
            result["raw"] = raw
            last_errors = errors
            result["error"] = "reply failed checks: " + "; ".join(errors[:5])
            logger.warning("%s: attempt %d rejected: %s", call_name, attempt, errors[:3])

        logger.error("%s: giving up after %d attempts (%s)", call_name, max_retries, result["error"])
        return result


    # ---- The pipeline: small helpers that shape data for the prompts ----

    def _years_text(self, years: list[int]) -> str:
        """[2026, 2027, 2028] -> "2026-2028"."""
        return f"{years[0]}-{years[-1]}" if years else "none"


    def _markets_brief(self, markets: dict) -> list[dict]:
        """Just the id, name and indicator of each market."""
        return [{k: m[k] for k in ("market_id", "name", "indicator")} for m in markets["relevant_markets"]]


    def _market_changes(self, markets: dict, first: int, last: int) -> dict:
        """{market_id: {year: change}} for the years a piece needs."""
        return {market_id: {h["year"]: h["change_pct"] for h in series["history"] if first <= h["year"] <= last}
                for market_id, series in markets["series"].items()}


    def _market_outlooks(self, markets: dict) -> dict:
        """{market_id: outlook} for the forecast years."""
        return {market_id: series["outlook"] for market_id, series in markets["series"].items()}


    def _types_brief(self, types: dict) -> list[dict]:
        """Just the id, category, name and route of each type."""
        return [{k: t[k] for k in ("type_id", "category", "name", "route")} for t in types["person_types"]]


    def _crime_categories(self) -> list[dict]:
        """The fixed list of crime categories the AI must choose from (config vocabulary)."""
        return [{"category": code, "description": text}
                for code, text in self._vocabulary().get("crime_categories", {}).items()]


    # ---- The pipeline: Step 0 + Calls 1-4 ----
    # Each step takes the saved replies (cache), adds its results to `results`,
    # and returns its data, or None as soon as one piece fails.

    def _read_declaration(self, record: dict, cache: dict, results: dict) -> Declaration | None:
        """Step 0: free-text declaration -> a Declaration of claimed sources (None if it failed)."""
        jobs, assets = len(self._career_positions(record)), len(record.get("investments", []))
        result = self._ask("step0_declaration", "declaration", {},
                                 self._client_facts(record, include_declaration=True), "declaration",
                                 lambda data: self.__check_declaration(data, jobs, assets), cache.get("step0_declaration"))
        results[result["call"]] = result
        if not result["ok"]:
            return None
        try:
            return Declaration.from_dict(result["data"])
        except ValueError as error:      # the checks above should make this impossible
            result.update(ok=False, error=f"the declaration reading could not be used: {error}")
            logger.error("step0_declaration: %s", result["error"])
            return None


    def __forecast_markets(self, record: dict, declaration: Declaration,
                           cache: dict, results: dict) -> dict | None:
        """Call 1: choose the markets, then recall and forecast each one."""
        start, end = self._career_years(record)
        years = self._future_years(record)
        values = {"start_year": start, "end_year": end, "forecast_years": self._years_text(years),
                  "last_forecast_year": years[-1]}
        web_search = self._settings()["web_search"]

        # 1a. Which markets matter for this client
        name = "call1_markets.list"
        listing = self._ask(name, "markets_list", values,
                                  {"client": self._client_facts(record),
                                   "claimed_sources": declaration.to_dict()["claimed_sources"]},
                                  "markets_list", lambda data: self.__check_markets(data, years),
                                  cache.get(name), web_search)
        results[name] = listing
        if not listing["ok"]:
            return None

        # 1b. History + outlook, one request per market
        markets = {**listing["data"], "series": {}}
        for market in listing["data"]["relevant_markets"]:
            market_id = market["market_id"]
            name = f"call1_markets.series.{market_id}"
            piece = self._ask(name, "market_series",
                                    {**values, "market_id": market_id, "market_name": market["name"],
                                     "indicator": market["indicator"]},
                                    {"market": market, "client": self._client_facts(record)}, "market_series",
                                    lambda data, m=market_id: self._check_market_series(data, m, list(range(start, end + 1)), years),
                                    cache.get(name), web_search)
            results[name] = piece
            if not piece["ok"]:
                return None
            markets["series"][market_id] = piece["data"]
        return markets


    def __forecast_earnings(self, record: dict, markets: dict,
                            cache: dict, results: dict) -> dict | None:
        """Call 2: expected pay for every job, future pay, and how each asset behaves."""
        _, end = self._career_years(record)
        years = self._future_years(record)
        market_ids = set(markets["series"])
        claimed_figure_keys = set(self._settings()["claimed_figure_keys"])
        earnings = {"positions": [], "assets": []}
        earlier_pay = []

        # 2a. Past pay, one request per job (each one sees the pay from the jobs before it)
        for index, job in enumerate(self._career_positions(record)):
            first, last = int(job["start_year"]), self._position_end(job, end)
            name = f"call2_earnings.position.{index}"
            piece = self._ask(name, "position_pay",
                                    {"position_index": index, "first_year": first, "last_year": last},
                                    {"job": {"position_index": index, **job}, "earlier_pay_typical": earlier_pay,
                                     "markets": self._markets_brief(markets),
                                     "market_changes": self._market_changes(markets, first, last)},
                                    "position_pay",
                                    lambda data, i=index, y=list(range(first, last + 1)): self._check_position_pay(data, i, y),
                                    cache.get(name))
            results[name] = piece
            if not piece["ok"]:
                return None
            earnings["positions"].append(piece["data"])
            earlier_pay += [{"year": row["year"], "base_pay": row["base_pay"]["typical"],
                             "bonus": row["bonus"]["typical"]} for row in piece["data"]["yearly"]]

        # 2b. Future pay, from his last 3 years of pay and the market outlooks
        name = "call2_earnings.future_pay"
        piece = self._ask(name, "future_pay", {"forecast_years": self._years_text(years)},
                                {"recent_pay_typical": earlier_pay[-3:], "client": self._client_facts(record),
                                 "markets": self._markets_brief(markets), "market_outlooks": self._market_outlooks(markets)},
                                "future_pay", lambda data: self.__check_pay(data, years), cache.get(name))
        results[name] = piece
        if not piece["ok"]:
            return None
        earnings["future_pay"] = piece["data"]

        # 2c. How each asset behaves, one request per asset (claimed values removed)
        for index, asset in enumerate(record.get("investments", [])):
            bought = int(asset["year_acquired"])
            name = f"call2_earnings.asset.{index}"
            piece = self._ask(name, "asset_model",
                                    {"asset_index": index, "bought_year": bought, "end_year": end,
                                     "forecast_years": self._years_text(years)},
                                    {"asset": self._strip_keys({"asset_index": index, **asset}, claimed_figure_keys),
                                     "markets": self._markets_brief(markets),
                                     "market_changes": self._market_changes(markets, bought, end)},
                                    "asset_model",
                                    lambda data, i=index, y=list(range(bought, end + 1)): self.__check_asset_model(
                                        self._repair_asset_model(data, market_ids), i, y, market_ids),
                                    cache.get(name))
            results[name] = piece
            if not piece["ok"]:
                # one asset the AI can't describe doesn't stop the whole forecast
                logger.warning("%s: left out of the market model (%s)", name, piece["error"])
                earnings.setdefault("fallback_assets", []).append({"asset_index": index, "error": piece["error"]})
                earnings["assets"].append(self._fallback_asset_model(index, bought, end))
                continue
            earnings["assets"].append(piece["data"])
        return earnings


    def _typologies_brief(self, typologies: list[dict] | None) -> list[dict]:
        """The crime scan's verified typologies, as the person-types request sees them (no quotes or URLs)."""
        return [{"typology_id": t.get("typology_id"), "name": t.get("name"),
                 "crime_category": t.get("crime_category"), "description": t.get("description", "")}
                for t in typologies or [] if t.get("typology_id")]


    def __forecast_types(self, record: dict, declaration: Declaration, markets: dict,
                         earnings: dict, cache: dict, results: dict,
                         typologies: list[dict] | None = None) -> dict | None:
        """Call 3: the person types, then one behaviour forecast per type.

        The types are T1 (honest) plus crime types. The crime types are built first from the crime
        scan's researched typologies (typologies: verified sector_typologies, each with a
        crime_category), then from any other standard crime category his jobs, assets and declared
        sources make possible. Each is tied to what enables it.
        """
        researched = self._typologies_brief(typologies)
        researched_by_id = {t["typology_id"]: t for t in researched}
        start, end = self._career_years(record)
        years = self._future_years(record)
        values = {"start_year": start, "end_year": end, "forecast_years": self._years_text(years),
                  "last_forecast_year": years[-1], "baseline_type": ForecastAI.BASELINE_TYPE,
                  "honest_category": self._settings()["honest_category"],
                  "max_crime_types": self._settings()["max_crime_types"]}
        claimed_sources = declaration.sources()
        reading = declaration.to_dict()["claimed_sources"]          # the reading, as the prompts show it

        # 3a. The list of types (years are repaired first, then checked)
        name = "call3_types.list"
        listing = self._ask(name, "person_types", values,
                                  {"client": self._client_facts(record, include_declaration=True),
                                   "claimed_sources": reading,
                                   "markets": self._markets_brief(markets),
                                   "career_outlook": earnings["future_pay"]["career_outlook"],
                                   "researched_typologies": researched,
                                   "crime_categories": self._crime_categories()},
                                  "person_types",
                                  lambda data: self.__check_person_types(
                                      self._repair_person_types(self._link_typologies(data, researched), record, claimed_sources),
                                      record, claimed_sources),
                                  cache.get(name))
        results[name] = listing
        if not listing["ok"]:
            return None

        # 3b. Behaviour (extra money + signals), one request per type
        types = {"person_types": listing["data"]["person_types"], "behaviour": {}}
        for person_type in types["person_types"]:
            type_id = person_type["type_id"]
            if type_id == ForecastAI.BASELINE_TYPE:
                baseline_note = "This is the as-declared type, so its extra money is 0 every year."
            else:
                baseline_note = ("Give only the money this crime ADDS on top of his declared sources, and "
                                 "only in the years it was open. It must come through the job, asset or "
                                 "source named in enabled_by, at the size that channel could realistically carry.")
            open_years = (person_type["open_from"], person_type["open_to"])
            name = f"call3_types.behaviour.{type_id}"
            behaviour_data = {"this_type": person_type, "all_types": self._types_brief(types),
                              "claimed_sources": reading,
                              "markets": self._markets_brief(markets), "client": self._client_facts(record)}
            if person_type.get("typology_id") in researched_by_id:
                behaviour_data["researched_pattern"] = researched_by_id[person_type["typology_id"]]
            piece = self._ask(name, "type_behaviour",
                                    {**values, "type_id": type_id, "type_name": person_type["name"],
                                     "baseline_note": baseline_note},
                                    behaviour_data,
                                    "type_behaviour",
                                    lambda data, t=type_id, o=open_years: self._check_type_behaviour(
                                        self._repair_type_behaviour(data, t, end, years, o, set(markets["series"])),
                                        t, start, end, years, set(markets["series"]), o),
                                    cache.get(name))
            results[name] = piece
            if not piece["ok"]:
                return None
            types["behaviour"][type_id] = piece["data"]
        return types


    def __forecast_events(self, record: dict, markets: dict, types: dict,
                          cache: dict, results: dict) -> dict | None:
        """Call 4: specific future events, then how each type would react to them."""
        years = self._future_years(record)
        settings = self._settings()

        # 4a. The list of future events
        name = "call4_events.list"
        listing = self._ask(name, "events",
                                  {"forecast_years": self._years_text(years), "min_events": settings["min_events"],
                                   "max_events": settings["max_events"]},
                                  {"markets": self._markets_brief(markets), "market_outlooks": self._market_outlooks(markets),
                                   "person_types": self._types_brief(types), "client": self._client_facts(record)},
                                  "events", lambda data: self.__check_events(data, years, set(markets["series"])),
                                  cache.get(name))
        results[name] = listing
        if not listing["ok"]:
            return None

        # 4b. How each type reacts to those events, one request per type
        events = {"events": listing["data"]["events"], "reactions": {}}
        event_ids = [e["event_id"] for e in events["events"]]
        for person_type in types["person_types"]:
            type_id = person_type["type_id"]
            name = f"call4_events.reactions.{type_id}"
            piece = self._ask(name, "type_reactions",
                                    {"type_id": type_id, "type_name": person_type["name"], "event_ids": ", ".join(event_ids)},
                                    {"this_type": person_type, "its_signals": types["behaviour"][type_id]["signals"],
                                     "events": events["events"]},
                                    "type_reactions",
                                    lambda data, t=type_id: self._check_type_reactions(self._repair_type_reactions(data, t, event_ids),
                                                                                 t, event_ids),
                                    cache.get(name))
            results[name] = piece
            if not piece["ok"]:
                return None
            events["reactions"][type_id] = piece["data"]
        return events


    # ---- The pipeline: entry points called by main.py ----

    def _stopped(self, run: dict, stage: str) -> dict:
        """Mark the run as stopped at a stage, naming the piece that failed and why."""
        failed = next((r for name, r in reversed(list(run["results"].items())) if not r["ok"]), None)
        run["failed_step"] = stage
        run["failed_piece"] = failed["call"] if failed else stage
        run["failed_error"] = (failed or {}).get("error") or "unknown error"
        return run


    # The stages of the forecast, in order (on_step is told each one as it starts)


    def _run_forecast(self, record: dict, cache: dict | None = None,
                                typologies: list[dict] | None = None,
                                on_step: Callable[[str], None] | None = None) -> dict:
        """Entry point. Run Step 0 and Calls 1-4 in order, stopping at the first failure.

        cache:      {piece_name: raw_text} of saved replies (from data_manager).
        typologies: the crime scan's verified sector typologies; Call 3 builds its crime types from them.
        on_step:    called with each stage name in STAGES as it starts (progress display).
        Returns {"ok", "failed_step", "results": {piece: result}, "forecast": {...}, "partial": {...}}.
        Finished pieces are in "results" even after a failure, so a rerun resumes there; "partial"
        holds the parts that finished (declaration, markets, ...) so the crime scan and the
        benchmark can still use them.
        """
        cache = cache or {}
        results: dict = {}
        partial: dict = {}
        run = {"ok": False, "failed_step": None, "failed_piece": None, "failed_error": None,
               "results": results, "forecast": {}, "partial": partial}

        def start(stage: str) -> None:
            if on_step is not None:
                on_step(stage)

        start("step0_declaration")
        declaration = self._read_declaration(record, cache, results)
        if declaration is None:
            return self._stopped(run, "step0_declaration")
        partial["declaration"] = declaration
        start("call1_markets")
        markets = self.__forecast_markets(record, declaration, cache, results)
        if markets is None:
            return self._stopped(run, "call1_markets")
        partial["markets"] = markets
        start("call2_earnings")
        earnings = self.__forecast_earnings(record, markets, cache, results)
        if earnings is None:
            return self._stopped(run, "call2_earnings")
        partial["earnings"] = earnings
        start("call3_types")
        types = self.__forecast_types(record, declaration, markets, earnings, cache, results, typologies)
        if types is None:
            return self._stopped(run, "call3_types")
        partial["types"] = types
        start("call4_events")
        events = self.__forecast_events(record, markets, types, cache, results)
        if events is None:
            return self._stopped(run, "call4_events")
        partial["events"] = events

        run["forecast"] = {
            "declaration": declaration,
            "markets": markets,
            "earnings": earnings,
            "types": types,
            "events": events,
            "prompt_versions": {name: result["prompt_version"] for name, result in results.items()},
        }
        run["ok"] = True
        return run
