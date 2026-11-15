"""CrimeScan: is a crime story a known pattern for his industry, and did its warning signs fire?"""

import logging

from app.logic.risk_analysis import RiskAnalysis
from app.logic.indicator import (CounterpartyUnnamed, GiftOrInheritanceUnnamed, Indicator,
                                 RelatedPartyTransaction, SourceContradictsOccupation, UnvaluedSource)
from app.model.check import Check
from app.model.declaration import Declaration
from app.model.match_result import MatchResult
from app.model.research_report import ResearchReport
from app.model.typology import Typology

logger = logging.getLogger(__name__)


class CrimeScan(RiskAnalysis):
    """The crime scan feature. It trusts nothing the AI found until it has checked it: a
    research report must come from a trusted site, and a typology's quotes must really be
    in the reports it cites. It then runs its five Indicators (the warning signs) on the
    client's declaration and matches them against each typology.

    The crime scan creates and owns its Indicators (composition).
    """

    _COUNTRY_TO_ISO = {
        "singapore": "SG",
        "malaysia": "MY",
        "hong kong": "HK",
        "united arab emirates": "AE",
        "uae": "AE",
        "dubai": "AE",
        "abu dhabi": "AE",
        "australia": "AU",
        "united kingdom": "GB",
        "uk": "GB",
        "great britain": "GB",
        "england": "GB",
        "united states": "US",
        "usa": "US",
        "united states of america": "US",
        "indonesia": "ID",
        "thailand": "TH",
        "philippines": "PH",
        "china": "CN",
        "japan": "JP",
        "india": "IN",
        "south korea": "KR",
        "korea": "KR",
        "taiwan": "TW",
        "vietnam": "VN",
        "myanmar": "MM",
        "cambodia": "KH",
        "switzerland": "CH",
        "germany": "DE",
        "france": "FR",
        "netherlands": "NL",
        "luxembourg": "LU",
        "cayman islands": "KY",
        "british virgin islands": "VG",
        "bvi": "VG",
        "bermuda": "BM",
        "jersey": "JE",
        "guernsey": "GG",
        "isle of man": "IM",
        "panama": "PA",
        "seychelles": "SC",
        "mauritius": "MU",
        "liechtenstein": "LI",
        "monaco": "MC",
        "canada": "CA",
        "new zealand": "NZ",
        "ireland": "IE",
        "bahrain": "BH",
        "qatar": "QA",
        "saudi arabia": "SA",
        "oman": "OM",
        "kuwait": "KW",
        "nigeria": "NG",
        "south africa": "ZA",
        "kenya": "KE",
        "brazil": "BR",
        "mexico": "MX",
        "cyprus": "CY",
        "malta": "MT",
    }
    FULL_MATCH = ("critical", "high", "medium")
    WEAK_MATCH = ("partial", "weak_signal")
    MATCH_LABELS = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "partial": "PARTIAL",
                    "weak_signal": "WEAK", "no_match": "NO MATCH"}
    SIGN_THEMES = {"gift_or_inheritance_unnamed": "people", "counterparty_unnamed": "people",
                   "related_party_transaction": "people", "source_contradicts_occupation": "sources",
                   "unvalued_source_present": "sources"}
    SIGN_LABELS = {"gift_or_inheritance_unnamed": "gift or inheritance from someone unnamed",
                   "counterparty_unnamed": "money from unnamed people",
                   "related_party_transaction": "money from a related party",
                   "source_contradicts_occupation": "a source that doesn't fit his job",
                   "unvalued_source_present": "a source with no amount"}

    NAME: str = "crime"

    def __init__(self, policy: dict | None = None) -> None:
        super().__init__(policy)
        self.__indicators: list[Indicator] = [
            GiftOrInheritanceUnnamed(self._policy), CounterpartyUnnamed(self._policy),
            SourceContradictsOccupation(self._policy), UnvaluedSource(self._policy),
            RelatedPartyTransaction(self._policy)]
        self.__warnings: list[str] = []

    def run(self, case: dict, ai_data: dict) -> dict:
        """Match the typologies against the client. ai_data is {"typologies": list[Typology],
        "declaration": {"sources": [...]}}. A raw typology reply may be given as "typology_response"
        instead (the golden cases do); its typologies are read as they are, unverified."""
        typologies = ai_data.get("typologies")
        if typologies is None and ai_data.get("typology_response") is not None:
            typologies = self.read_typologies(ai_data["typology_response"].get("sector_typologies", []))
        self._results = self._assess(typologies, ai_data.get("declaration"))
        return self._results

    def checks(self, context: dict) -> list[Check]:
        """The crime scan's findings. context holds crime_result, reports (the trusted ResearchReports, or
        None if the research did not run), typologies, types, forecast_ran."""
        return self._crime_checks(
            context.get("crime_result"), context.get("reports"), context.get("typologies"),
            context.get("types") or [], context.get("forecast_ran", True))

    def flags(self, declaration: Declaration) -> list[str]:
        """The names of the warning signs that fire for this declaration."""
        return [indicator.NAME for indicator in self.__indicators if indicator.fires(declaration)]

    def warnings(self) -> list[str]:
        """What the last verify_research, verify_typology_sources or read_typologies call removed
        or could not read."""
        return list(self.__warnings)

    def verify_research(self, research: dict) -> list[ResearchReport]:
        """The research reports that can be trusted, as ResearchReport objects. Pure: no I/O.

        Rules applied in order per report:
        1. URL must be in research["api_sources"] (actually retrieved by web search).
        2. URL domain must be in policy["trusted_sources"].
        3. Duplicate URLs are dropped (first kept).
        Kept reports keep their ids (R1, R3, ... gaps are fine). Each removal is in warnings().
        """
        api_urls = {s["url"] for s in research.get("api_sources", [])}
        trusted = self._policy.get("trusted_sources", [])
        retrieved_at = research.get("retrieved_at") or ""
        self.__warnings = []
        seen_urls: set[str] = set()
        kept: list[ResearchReport] = []

        for data in research.get("reports", []):
            rid = data.get("report_id", "?") if isinstance(data, dict) else "?"
            try:
                report = ResearchReport.from_dict(data, retrieved_at)
            except ValueError as error:
                logger.warning("CrimeScan: research report %s cannot be read: %s", rid, error)
                self.__warnings.append(f"Removed {rid}: the report could not be read ({error}).")
                continue

            if report.url not in api_urls:
                self.__warnings.append(f"Removed {rid}: URL not found in web search results.")
                continue

            if not self._domain_is_trusted(report.url, trusted):
                self.__warnings.append(f"Removed {rid}: domain not in trusted sources.")
                continue

            if report.url in seen_urls:
                self.__warnings.append(f"Removed {rid}: duplicate URL.")
                continue

            seen_urls.add(report.url)
            kept.append(report)
        return kept

    def verify_typology_sources(self, typologies: list[dict],
        reports: list[ResearchReport]) -> list[Typology]:
        """The AI's typologies whose sources check out, as verified Typology objects. Pure: no I/O.

        For each typology:
        1. source_ids not found in the reports are removed.
        2. source_quotes whose quote does not appear (after normalisation) in the
           cited report's excerpts are removed.
        3. Typologies with no verified quotes left are dropped entirely.
        4. corroborated: True if two of its grounded sources come from independent organisations.
        5. outdated: sources older than policy[source_max_age_years] are listed (not a warning).
        6. unknown_age: reports with missing/invalid year are a warning, not outdated.
        Each removal is in warnings().
        """
        policy = self._policy
        report_map = {report.report_id: report for report in reports}
        max_age = policy.get("source_max_age_years", 10)

        cleaned: list[Typology] = []
        self.__warnings = []
        warnings = self.__warnings

        for typ in typologies:
            typ_id = typ.get("typology_id", "unknown") if isinstance(typ, dict) else "unknown"
            typology = self.__read_typology(typ, typ_id)
            if typology is None:
                continue

            # Check 1: source_ids exist — keep only valid ones
            valid_ids: list[str] = []
            for sid in typology.cited_report_ids():
                if sid in report_map:
                    valid_ids.append(sid)
                else:
                    warnings.append(f"Typology '{typ_id}': source {sid} not found in research.")

            # Check 2: quotes verified (with normalisation) — keep only verified ones
            valid_quotes: list[dict] = []
            for sq in typology.source_quotes:
                rid = sq.get("report_id", "")
                quote = sq.get("quote", "")
                if rid not in report_map:
                    warnings.append(
                        f"Typology '{typ_id}': quote from {rid} invalid — report not found."
                    )
                    continue
                if report_map[rid].contains_quote(quote):
                    valid_quotes.append({"report_id": rid, "quote": quote})
                else:
                    warnings.append(
                        f"Typology '{typ_id}': quote from {rid} not found verbatim in excerpts."
                    )

            # Drop typology if no verified quotes remain
            if not valid_quotes:
                warnings.append(f"Typology '{typ_id}': dropped — no verified quotes remain.")
                continue

            # Check 3: corroborated (valid ID + verified quote, independent orgs)
            quote_ids = {q["report_id"] for q in valid_quotes}
            grounded_ids = [sid for sid in valid_ids if sid in quote_ids]
            org_sets = [self._split_org_names(report_map[sid].organisation) for sid in grounded_ids]
            corroborated = any(
                org_sets[i].isdisjoint(org_sets[j])
                for i in range(len(org_sets))
                for j in range(i + 1, len(org_sets))
            )
            # Check 4: outdated and unknown age
            # Outdated is stored in the result for display — NOT a warning (informational only).
            # Missing/invalid year IS a warning (data quality problem).
            outdated_ids: list[str] = []
            for sid in valid_ids:
                year = report_map[sid].year
                reference_year = report_map[sid].retrieved_year()
                if not isinstance(year, int) or year <= 0:
                    warnings.append(
                        f"Typology '{typ_id}': source {sid} has no valid year (age check skipped)."
                    )
                elif reference_year and (reference_year - year) > max_age:
                    outdated_ids.append(sid)

            cleaned.append(typology.with_verified_sources(valid_ids, valid_quotes, corroborated, outdated_ids))
        return cleaned

    def read_typologies(self, typologies: list[dict]) -> list[Typology]:
        """The AI's typologies as Typology objects, unchecked (used when there is no research to check
        them against). A typology that cannot be read is left out, with a warning in warnings()."""
        self.__warnings = []
        read: list[Typology] = []
        for typ in typologies:
            typ_id = typ.get("typology_id", "unknown") if isinstance(typ, dict) else "unknown"
            typology = self.__read_typology(typ, typ_id)
            if typology is not None:
                read.append(typology)
        return read

    def __read_typology(self, data: dict, typ_id: str) -> Typology | None:
        """One typology of the AI's reply, or None (logged and warned) if it cannot be read."""
        try:
            return Typology.from_dict(data)
        except ValueError as error:
            logger.warning("CrimeScan: typology %s cannot be read: %s", typ_id, error)
            self.__warnings.append(f"Typology '{typ_id}': dropped — it could not be read ({error}).")
            return None

    def _domain_is_trusted(self, url: str, trusted_domains: list[str]) -> bool:
        """Return True if the URL's domain matches or is a subdomain of a trusted domain."""
        netloc = ResearchReport("", url).domain()
        for td in trusted_domains:
            if netloc == td or netloc.endswith("." + td):
                return True
        return False

    def _split_org_names(self, org_string: str) -> set[str]:
        """Split 'FATF and Egmont Group' into {'fatf', 'egmont group'}."""
        s = org_string.replace(" and ", ",").replace("&", ",").replace("/", ",")
        return {p.strip().lower() for p in s.split(",") if p.strip()}

    def _assess(self, typologies: list[Typology] | None, declaration: dict | None) -> dict:
        """Match every typology against the declaration.

        Returns {"breach_count", "match_count", "match_results": list[MatchResult]}.
        """
        # If either AI call failed entirely (returned None), skip assessment
        if typologies is None or declaration is None:
            return {"breach_count": 0, "match_count": 0, "match_results": []}

        # Run all 5 indicators against each typology and collect match results
        match_results = self.match_typologies(Declaration(declaration.get("sources", [])), typologies)

        # Count full breaches (critical/high/medium) and all matches including partial/weak
        breach_count = sum(1 for mr in match_results if mr.breached)
        match_count = sum(1 for mr in match_results if mr.category != "no_match")
        return {"breach_count": breach_count, "match_count": match_count, "match_results": match_results}

    def _categorise_match(self, core_fired: list, core: list, supporting_fired: list) -> str:
        all_core = len(core_fired) == len(core) and len(core) > 0
        n_sup = len(supporting_fired)
        if all_core:
            if n_sup >= 2:
                return "critical"
            if n_sup == 1:
                return "high"
            return "medium"
        if n_sup >= 2:
            return "partial"
        if n_sup >= 1:
            return "weak_signal"
        return "no_match"

    def match_typologies(self, declaration: Declaration, typologies: list[Typology]) -> list[MatchResult]:
        """Match each typology's warning signs against the declaration. Pure function.

        A typology breaches when ALL its core indicators fire.
        Returns one MatchResult per typology, in the same order; each holds its Typology.
        """
        fired = self.flags(declaration)
        indicator_results = {indicator.NAME: indicator.NAME in fired for indicator in self.__indicators}

        matches: list[MatchResult] = []
        for typology in typologies:
            core = typology.core_indicators()
            supporting = typology.supporting_indicators()
            core_fired = [i for i in core if indicator_results.get(i, False)]
            supporting_fired = [i for i in supporting if indicator_results.get(i, False)]
            category = self._categorise_match(core_fired, core, supporting_fired)
            matches.append(MatchResult(typology, core_fired, supporting_fired, category))
        return matches

    def _to_iso(self, value, warnings: list) -> str | None:
        """Convert a country name or code to ISO 3166-1 alpha-2. Pure, no I/O.

        - None/empty → None (no warning)
        - Already 2 uppercase letters → return as-is
        - Lookup in CrimeScan._COUNTRY_TO_ISO (case-insensitive) → return code
        - 2 letters, not uppercase → uppercase (e.g. "sg" → "SG")
        - Unrecognized → keep as-is + warning
        """
        if value is None:
            return None
        stripped = str(value).strip()
        if not stripped:
            return None
        if len(stripped) == 2 and stripped.isalpha() and stripped.isupper():
            return stripped
        lookup = CrimeScan._COUNTRY_TO_ISO.get(stripped.lower())
        if lookup:
            return lookup
        if len(stripped) == 2 and stripped.isalpha():
            return stripped.upper()
        warnings.append(f"Unknown country '{stripped}' — could not convert to ISO-2.")
        return stripped

    def _safe_int(self, value, default=None):
        """Convert value to int if possible. Returns default on None or failure. Pure."""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return default
        return default

    def _prepare_case(self, record: dict) -> tuple[dict, list[str]]:
        """Normalize a client record for typology matching. Pure function.

        Returns (normalized_record, warnings).

        1. Coerces age, career_start_year to int.
        2. Converts country/country_of_residence to ISO-2.
        3. Builds all_jurisdictions: sorted deduplicated list of ISO-2 codes from
           country, country_of_residence, wealth_countries, career_timeline,
           asset_timeline, and declarations.wealth_countries.
        4. Extracts declared_net_worth_sgd from whichever location has it.
        5. Extracts reference_year from record or date fields.
        Does NOT mutate the original record or any sub-dicts.
        """
        warnings: list[str] = []
        out = {**record}

        out["age"] = self._safe_int(record.get("age"))
        out["career_start_year"] = self._safe_int(record.get("career_start_year"))
        out["country"] = self._to_iso(record.get("country"), warnings)
        out["country_of_residence"] = self._to_iso(record.get("country_of_residence"), warnings)

        # declared_net_worth_sgd — check multiple possible field locations
        raw_nw = record.get("declared_net_worth_sgd")
        if raw_nw is None:
            raw_nw = (record.get("declarations") or {}).get("declared_net_worth")
        if raw_nw is None:
            raw_nw = (record.get("client_declarations") or {}).get("declared_net_worth")
        out["declared_net_worth_sgd"] = self._safe_int(raw_nw)

        # reference_year — explicit field, or extracted from date fields
        ref = record.get("reference_year")
        if ref is None:
            date_str = (
                record.get("date_profile_created")
                or (record.get("client_profile") or {}).get("date_profile_created")
                or (record.get("declarations") or {}).get("date_declared")
                or (record.get("client_declarations") or {}).get("date_declared")
            )
            if date_str:
                ref = self._safe_int(str(date_str)[:4])
        out["reference_year"] = self._safe_int(ref)

        all_iso: set[str] = set()

        if out["country"]:
            all_iso.add(out["country"])
        if out["country_of_residence"]:
            all_iso.add(out["country_of_residence"])

        # Top-level wealth_countries (golden case format)
        for c in record.get("wealth_countries", []):
            code = self._to_iso(c, warnings)
            if code:
                all_iso.add(code)

        for entry in record.get("career_timeline", []):
            code = self._to_iso(entry.get("country"), warnings)
            if code:
                all_iso.add(code)

        for entry in record.get("asset_timeline", []):
            code = self._to_iso(entry.get("country"), warnings)
            if code:
                all_iso.add(code)

        decl = record.get("declarations", {})
        for c in (decl or {}).get("wealth_countries", []):
            code = self._to_iso(c, warnings)
            if code:
                all_iso.add(code)

        out["all_jurisdictions"] = sorted(all_iso)
        return out, warnings

    def normalise_jurisdictions(self, declaration: dict) -> tuple[dict, list[str]]:
        """Post-process AI declaration output to ensure jurisdiction fields are ISO-2.

        Pure function. Called after schema validation succeeds.
        Per source:
        - Valid ISO-2 (2 uppercase letters) → kept.
        - Full name in CrimeScan._COUNTRY_TO_ISO → converted + warning.
        - 2 lowercase letters → uppercased + warning.
        - Unrecognizable string → set to None + warning.
        - None → kept.
        Returns (cleaned_declaration, warnings).
        """
        warnings: list[str] = []
        sources = []
        for src in declaration.get("sources", []):
            new_src = {**src}
            j = src.get("jurisdiction")
            if j is None:
                sources.append(new_src)
                continue
            stripped = str(j).strip()
            if len(stripped) == 2 and stripped.isalpha() and stripped.isupper():
                sources.append(new_src)
                continue
            lookup = CrimeScan._COUNTRY_TO_ISO.get(stripped.lower())
            if lookup:
                warnings.append(f"Declaration jurisdiction '{j}' converted to '{lookup}'.")
                new_src["jurisdiction"] = lookup
            elif len(stripped) == 2 and stripped.isalpha():
                upper = stripped.upper()
                warnings.append(f"Declaration jurisdiction '{j}' uppercased to '{upper}'.")
                new_src["jurisdiction"] = upper
            else:
                warnings.append(f"Declaration jurisdiction '{j}' unrecognizable — set to null.")
                new_src["jurisdiction"] = None
            sources.append(new_src)
        return {**declaration, "sources": sources}, warnings

    def crime_declaration(self, declaration: dict | None) -> tuple[dict | None, list[str]]:
        """The declaration the forecast read (Step 0), as the crime scan's warning-sign rows.

        The declaration is read by the AI ONCE; this only reshapes it. A salary, bonus or savings
        source tied to one of his jobs needs no amount: the forecast works out what the job paid.
        Returns ({"sources": [...]}, warnings) or (None, warnings) if there is no declaration.
        """
        policy = self._policy
        if not declaration:
            return None, []
        explained_by_career = set(policy.get("self_explained_source_types", []))
        warnings, rows = [], []
        for source in declaration.get("claimed_sources", []):
            kind = source.get("source_type")
            if kind == "inheritance_gift":
                kind = "inheritance" if "inherit" in str(source.get("description", "")).lower() else "gift"
            read = "counterparty" in source
            rows.append({
                "source_id": source.get("source_id"),
                "source_type": kind,
                "description": source.get("description", ""),
                "amount_sgd": source.get("amount"),
                "start_year": source.get("start_year"),
                "end_year": source.get("end_year"),
                "jurisdiction": source.get("country"),
                # an older saved reading has no counterparty: don't count it as "unnamed"
                "counterparty": source.get("counterparty") if read else "(not read)",
                "evidence_sentence": source.get("quote", ""),
                "occupation_mismatch": bool(source.get("occupation_mismatch", False)),
                "amount_explained_by_forecast": (source.get("source_type") in explained_by_career
                                                 and source.get("linked_position_index") is not None),
            })
            if not read and not warnings:
                warnings.append("The saved declaration reading has no counterparties; run the assessment "
                                "again with a fresh reading to check for unnamed people.")
        return {"sources": rows}, warnings

    def _crime_checks(self, crime_result: dict | None, reports: list[ResearchReport] | None,
                      typologies: list[Typology] | None,
                     types: list[dict], forecast_ran: bool) -> list[Check]:
        """The crime scan's patterns in the shared shape: how well each one matches, and which
        person type was built from it."""
        if crime_result is None:
            return [self._check("CRIME_SCAN", "Crime scan", "pattern", "skipped",
                                "The warning signs couldn't be checked (no typologies or no declaration reading).")]
        built = {t["typology_id"]: t for t in types if t["typology_id"]}
        quotes = {t.typology_id: (t.source_quotes or [{}])[0] for t in typologies or []}
        checks = []
        for match in crime_result.get("match_results", []):
            typology_id = match.typology.typology_id
            category = match.category
            fired = match.fired()
            status = "failed" if category in CrimeScan.FULL_MATCH else "weak" if category in CrimeScan.WEAK_MATCH else "passed"
            signs = ", ".join(f"{CrimeScan.SIGN_LABELS.get(s, s)} ({'core' if s in match.core_fired else 'supporting'})"
                              for s in fired) or "no warning signs fired"
            person = built.get(typology_id)
            if person:
                link = (f"Built into {person['type_id']} ({person['name']}), which "
                        f"{'fits' if person['fits'] else 'does not fit'} his money.")
            elif forecast_ran:
                link = "No person type uses it: none of his jobs, assets or sources opens this channel."
            else:
                link = ""
            quote = quotes.get(typology_id, {})
            sources = ", ".join(match.typology.cited_report_ids())
            detail = f"{CrimeScan.MATCH_LABELS.get(category, category)} match: {signs}"
            explanation = link + (f' "{quote["quote"]}" [{quote.get("report_id", "")}]' if quote.get("quote") else "")
            check = self._check("TYPOLOGY", f"{match.typology.name or typology_id}"
                                + (f" [{sources}]" if sources else ""), "pattern", status, detail, explanation.strip(),
                                group="Patterns")
            check.set_extra("signs", fired)               # the verdict and the report read these three
            check.set_extra("match", category)
            check.set_extra("typology_id", typology_id)
            checks.append(check)
        for person in types:
            if not person["typology_id"]:
                checks.append(self._check("UNBACKED_TYPE", f"{person['type_id']} {person['name']}", "pattern", "info",
                                          "Not backed by research: built from his background only.",
                                          group="Crime stories"))
        if not crime_result.get("match_results"):
            checks.append(self._check("NO_PATTERNS", "Known patterns", "pattern", "info",
                                      f"No verified patterns for his industry ({len(reports or [])} research "
                                      "report(s) found)."))
        return checks
