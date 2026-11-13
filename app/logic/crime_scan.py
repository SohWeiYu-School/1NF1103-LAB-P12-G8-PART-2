"""CrimeScan: is a crime story a known pattern for his industry, and did its warning signs fire?"""

import logging
from urllib.parse import urlparse

from app.logic.feature import Feature
from app.logic.indicator import (CounterpartyUnnamed, GiftOrInheritanceUnnamed, Indicator,
                                 RelatedPartyTransaction, SourceContradictsOccupation, UnvaluedSource)
from app.model.check import Check
from app.model.declaration import Declaration
from app.model.research_report import ResearchReport

logger = logging.getLogger(__name__)


class CrimeScan(Feature):
    """The crime scan feature. It trusts nothing the AI found until it has checked it: a
    research report must come from a trusted site, and a typology's quotes must really be
    in the reports it cites. It then runs its five Indicators (the warning signs) on the
    client's declaration and matches them against each typology.

    The crime scan creates and owns its Indicators (composition).
    """

    NAME: str = "crime"

    def __init__(self, policy: dict | None = None) -> None:
        super().__init__(policy)
        self.__indicators: list[Indicator] = [
            GiftOrInheritanceUnnamed(self._policy), CounterpartyUnnamed(self._policy),
            SourceContradictsOccupation(self._policy), UnvaluedSource(self._policy),
            RelatedPartyTransaction(self._policy)]

    def run(self, case: dict, ai_data: dict) -> dict:
        """Match the typologies against the client. ai_data is {"typology_response", "declaration"}."""
        self._results = self._assess(case, ai_data.get("typology_response"), ai_data.get("declaration"))
        return self._results

    def checks(self, context: dict) -> list[Check]:
        """The crime scan's findings. context holds crime_result, research, typologies, types, forecast_ran."""
        return self._as_checks(self._crime_checks(
            context.get("crime_result"), context.get("research"), context.get("typologies"),
            context.get("types") or [], context.get("forecast_ran", True)))

    def flags(self, declaration: Declaration) -> list[str]:
        """The names of the warning signs that fire for this declaration."""
        return [indicator.NAME for indicator in self.__indicators if indicator.fires(declaration)]

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

    def verify_research(self, research: dict) -> tuple[dict, list[str]]:
        """Filter research reports by grounding, domain trust, and uniqueness.

        Pure function — no I/O, no network.

        Rules applied in order per report:
        1. URL must be in research["api_sources"] (actually retrieved by web search).
        2. URL domain must be in policy["trusted_sources"].
        3. Duplicate URLs are dropped (first kept).
        4. Surviving reports are renumbered R1, R2, ...

        Returns (clean_research_dict, warnings).
        """
        policy = self._policy
        api_urls = {s["url"] for s in research.get("api_sources", [])}
        trusted = policy.get("trusted_sources", [])
        warnings: list[str] = []
        seen_urls: set[str] = set()
        kept: list[dict] = []

        for report in research.get("reports", []):
            url = report.get("url", "")
            rid = report.get("report_id", "?")

            if url not in api_urls:
                warnings.append(
                    f"Removed {rid}: URL not found in web search results."
                )
                continue

            if not self._domain_is_trusted(url, trusted):
                warnings.append(
                    f"Removed {rid}: domain not in trusted sources."
                )
                continue

            if url in seen_urls:
                warnings.append(
                    f"Removed {rid}: duplicate URL."
                )
                continue

            seen_urls.add(url)
            kept.append(report)

        clean_research = {
            "reports": kept,
            "api_sources": research.get("api_sources", []),
            "retrieved_at": research.get("retrieved_at", ""),
            "model": research.get("model", ""),
        }
        return clean_research, warnings

    def verify_typology_sources(self, typologies: list[dict],
        clean_research: dict) -> tuple[list[dict], list[str]]:
        """Verify and clean AI typology source citations against filtered research reports.

        Pure function — no I/O, no network.

        For each typology:
        1. source_ids not found in clean_research are removed.
        2. source_quotes whose quote does not appear (after normalisation) in the
           cited report's excerpts are removed.
        3. Typologies with no verified quotes left are dropped entirely.
        4. corroborated: warns if fewer than 2 independent-org sources remain.
        5. outdated: warns if a source exceeds policy[source_max_age_years].
        6. unknown_age: reports with missing/invalid year are noted, not outdated.

        Returns (cleaned_typologies, warnings).
        """
        policy = self._policy
        report_map = {r["report_id"]: r for r in clean_research.get("reports", [])}
        max_age = policy.get("source_max_age_years", 10)

        try:
            reference_year = int(clean_research.get("retrieved_at", "")[:4])
        except (ValueError, IndexError):
            reference_year = 0

        cleaned: list[dict] = []
        warnings: list[str] = []

        for typ in typologies:
            typ_id = typ.get("typology_id", "unknown")

            # Check 1: source_ids exist — keep only valid ones
            valid_ids: list[str] = []
            for sid in typ.get("source_ids", []):
                if sid in report_map:
                    valid_ids.append(sid)
                else:
                    warnings.append(f"Typology '{typ_id}': source {sid} not found in research.")

            # Check 2: quotes verified (with normalisation) — keep only verified ones
            valid_quotes: list[dict] = []
            for sq in typ.get("source_quotes", []):
                rid = sq.get("report_id", "")
                quote = sq.get("quote", "")
                if rid not in report_map:
                    warnings.append(
                        f"Typology '{typ_id}': quote from {rid} invalid — report not found."
                    )
                    continue
                excerpts = report_map[rid].get("excerpts", [])
                if self._report_contains_quote(excerpts, quote):
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
            org_sets = [
                self._split_org_names(report_map[sid].get("organisation", ""))
                for sid in grounded_ids
            ]
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
                year = report_map[sid].get("year")
                if not isinstance(year, int) or year <= 0:
                    warnings.append(
                        f"Typology '{typ_id}': source {sid} has no valid year (age check skipped)."
                    )
                elif reference_year and (reference_year - year) > max_age:
                    outdated_ids.append(sid)

            cleaned.append({
                **typ,
                "source_ids": valid_ids,
                "source_quotes": valid_quotes,
                "corroborated": corroborated,
                "outdated_source_ids": outdated_ids,
            })

        return cleaned, warnings

    def _report_contains_quote(self, excerpts: list[str], quote: str) -> bool:
        """True if the quote appears in an excerpt, ignoring case, spacing and curly quote marks."""
        return ResearchReport("", "", excerpts).contains_quote(quote)

    def _domain_is_trusted(self, url: str, trusted_domains: list[str]) -> bool:
        """Return True if the URL's domain matches or is a subdomain of a trusted domain."""
        netloc = urlparse(url).netloc.lower()
        for td in trusted_domains:
            if netloc == td or netloc.endswith("." + td):
                return True
        return False

    def _split_org_names(self, org_string: str) -> set[str]:
        """Split 'FATF and Egmont Group' into {'fatf', 'egmont group'}."""
        s = org_string.replace(" and ", ",").replace("&", ",").replace("/", ",")
        return {p.strip().lower() for p in s.split(",") if p.strip()}

    def _assess(self, case_input: dict,
        typology_response: dict | None,
        declaration: dict | None) -> dict:
        """Run the full Sector Crime Scan assessment for a single case.

        Returns a dict with keys: outcome, findings, documents, match_results.
        """

        # If either AI call failed entirely (returned None), skip assessment
        if typology_response is None or declaration is None:
            return {"breach_count": 0, "match_count": 0, "match_results": []}

        # Normalise the client record so country fields and int fields are clean
        clean_case, _ = self._prepare_case(case_input)
        typologies = typology_response.get("sector_typologies", [])

        # Run all 5 indicators against each typology and collect match results
        match_results = self.match_typologies(typologies, declaration, clean_case)

        # Count full breaches (critical/high/medium) and all matches including partial/weak
        breach_count = sum(1 for mr in match_results if mr["breached"])
        match_count = sum(1 for mr in match_results if mr["category"] != "no_match")
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

    def match_typologies(self, typologies: list[dict],
        declaration: dict,
        clean_case: dict) -> list[dict]:
        """Match each typology's indicators against client data. Pure function.

        A typology breaches when ALL its core indicators fire.
        Returns a list of match result dicts, one per typology.
        """
        fired = self.flags(Declaration(declaration.get("sources", [])))
        indicator_results = {indicator.NAME: indicator.NAME in fired for indicator in self.__indicators}

        matches: list[dict] = []
        for typ in typologies:
            indicators = typ.get("indicators", [])
            core = [i["indicator"] for i in indicators if i.get("weight") == "core"]
            supporting = [i["indicator"] for i in indicators if i.get("weight") == "supporting"]
            core_fired = [i for i in core if indicator_results.get(i, False)]
            supporting_fired = [i for i in supporting if indicator_results.get(i, False)]
            breached = len(core_fired) == len(core) and len(core) > 0
            category = self._categorise_match(core_fired, core, supporting_fired)

            matches.append({
                "typology_id": typ.get("typology_id", ""),
                "name": typ.get("name", ""),
                "source_ids": typ.get("source_ids", []),
                "breached": breached,
                "category": category,
                "core_indicators": core,
                "core_fired": core_fired,
                "supporting_indicators": supporting,
                "supporting_fired": supporting_fired,
                "typical_documents": typ.get("typical_documents", []),
            })
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

    def _crime_checks(self, crime_result: dict | None, research: dict | None, typologies: list[dict] | None,
                     types: list[dict], forecast_ran: bool) -> list[dict]:
        """The crime scan's patterns in the shared shape: how well each one matches, and which
        person type was built from it."""
        if crime_result is None:
            return [self._row("crime", "CRIME_SCAN", "Crime scan", "pattern", "skipped",
                           "The warning signs couldn't be checked (no typologies or no declaration reading).")]
        built = {t["typology_id"]: t for t in types if t["typology_id"]}
        quotes = {t.get("typology_id"): (t.get("source_quotes") or [{}])[0] for t in typologies or []}
        checks = []
        for match in crime_result.get("match_results", []):
            category = match.get("category", "no_match")
            fired = match.get("core_fired", []) + match.get("supporting_fired", [])
            status = "failed" if category in CrimeScan.FULL_MATCH else "weak" if category in CrimeScan.WEAK_MATCH else "passed"
            signs = ", ".join(f"{CrimeScan.SIGN_LABELS.get(s, s)} ({'core' if s in match.get('core_fired', []) else 'supporting'})"
                              for s in fired) or "no warning signs fired"
            person = built.get(match["typology_id"])
            if person:
                link = (f"Built into {person['type_id']} ({person['name']}), which "
                        f"{'fits' if person['fits'] else 'does not fit'} his money.")
            elif forecast_ran:
                link = "No person type uses it: none of his jobs, assets or sources opens this channel."
            else:
                link = ""
            quote = quotes.get(match["typology_id"], {})
            sources = ", ".join(match.get("source_ids", []))
            detail = f"{CrimeScan.MATCH_LABELS.get(category, category)} match: {signs}"
            explanation = link + (f' "{quote["quote"]}" [{quote.get("report_id", "")}]' if quote.get("quote") else "")
            check = self._row("crime", "TYPOLOGY", f"{match.get('name') or match['typology_id']}"
                           + (f" [{sources}]" if sources else ""), "pattern", status, detail, explanation.strip(),
                           group="Patterns")
            check["signs"] = fired
            check["match"] = category
            check["typology_id"] = match["typology_id"]
            checks.append(check)
        for person in types:
            if not person["typology_id"]:
                checks.append(self._row("crime", "UNBACKED_TYPE", f"{person['type_id']} {person['name']}", "pattern", "info",
                                     "Not backed by research: built from his background only.", group="Crime stories"))
        if not crime_result.get("match_results"):
            reports = len((research or {}).get("reports", []))
            checks.append(self._row("crime", "NO_PATTERNS", "Known patterns", "pattern", "info",
                                 f"No verified patterns for his industry ({reports} research report(s) found)."))
        return checks
