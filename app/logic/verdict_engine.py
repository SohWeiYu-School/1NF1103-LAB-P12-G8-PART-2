"""VerdictEngine: one verdict from every feature's checks."""

from app.logic.benchmark import Benchmark
from app.logic.case_timeline import CaseTimeline
from app.logic.crime_scan import CrimeScan
from app.logic.risk_analysis import RiskAnalysis
from app.logic.formatter import Formatter
from app.logic.future_paths import FuturePaths
from app.model.check import Check
from app.model.config import Config
from app.model.typology import Typology
from app.model.verdict import Verdict


class VerdictEngine:
    """Combines the features' checks into one verdict and one report.

    The engine is handed a list of Features and the Config. It gathers findings by
    calling checks() on each feature in the same way, whichever child class it is
    (polymorphism). The features are made elsewhere and can exist without the engine
    (aggregation). A feature the engine was not given simply adds no findings.

    The ladder it applies (the numbers are in the policy's "verdict" block) is described
    on combine().
    """

    VERDICT_LABELS: dict[str, str] = {"PASSED": "PASSED", "MANUAL_REVIEW": "MANUAL REVIEW", "RISKY": "RISKY", "SERIOUS_RISK": "SERIOUS RISK"}
    THEMES: dict[str, str] = {
        "wealth":    "Wealth too high for his career",
        "purchases": "Purchases he couldn't afford",
        "people":    "Unknown or unnamed people giving money",
        "countries": "Money from risky or unexpected countries",
        "sources":   "Sources that don't match his job",
        "pattern":   "Matches a known crime pattern",
    }
    MARKS: dict[str, str] = {"failed": "fail", "weak": "weak", "explained": "explained", "passed": "pass", "skipped": "skip", "info": "info"}
    REPORT_LEGEND: list[dict[str, str]] = [
        {"mark": "fail", "symbol": "\u2717", "meaning": "counts towards the verdict"},
        {"mark": "explained", "symbol": "~", "meaning": "failed, but another feature explains it"},
        {"mark": "weak", "symbol": "!", "meaning": "loose end"},
        {"mark": "pass", "symbol": "\u2713", "meaning": "clean"},
        {"mark": "skip", "symbol": "-", "meaning": "couldn't run"},
        {"mark": "info", "symbol": "\u2022", "meaning": "information"},
    ]
    _ROUTINE_NOTES: tuple[str, ...] = ("converted to", "renumbered", "kept first")
    ORIGINAL_BENCHMARK: list[str] = ["TOTAL_WEALTH", "LIQUIDITY", "COMPOSITION_PROPERTY", "COMPOSITION_EQUITIES",
                          "COMPOSITION_BUSINESS", "COMPOSITION_CASH", "VELOCITY", "COUNTERPARTIES", "JURISDICTION"]

    def __init__(self, features: list[RiskAnalysis] | None = None, config: Config | None = None) -> None:
        if features is not None and not isinstance(features, list):
            raise ValueError(f"the features must be a list (or None), not {type(features).__name__}")
        if not all(isinstance(feature, RiskAnalysis) for feature in features or []):
            raise ValueError("every feature must be a RiskAnalysis (crime scan, documents, benchmark or forecast)")
        if config is not None and not isinstance(config, Config):
            raise ValueError(f"the config must be a Config (or None), not {type(config).__name__}")
        self.__features: list[RiskAnalysis] = list(features or [])
        self.__config: Config = config or Config()
        self.__policy: dict = self.__config.policy

    def features(self) -> list[RiskAnalysis]:
        return list(self.__features)

    def __feature(self, name: str) -> RiskAnalysis | None:
        """The feature with this NAME, or None if the engine was not given one."""
        return next((feature for feature in self.__features if feature.NAME == name), None)

    def __feature_checks(self, name: str, context: dict) -> list[Check]:
        """One feature's checks. A feature the engine was not given has none."""
        feature = self.__feature(name)
        return list(feature.checks(context)) if feature else []

    def __check(self, feature: str, check: str, label: str, theme: str, status: str, detail: str,
               explanation: str = "", group: str = "") -> Check:
        """One finding the engine adds itself."""
        return Check(feature, check, label, theme, status, detail, explanation, group)

    def _is_pep(self, case: dict) -> bool:
        """True if the client is a politically exposed person (anything but the policy's "no" values).
        A blank answer is unknown, not "no": it counts as a PEP, the cautious side."""
        status = str(case.get("claims", {}).get("pep_status") or "").strip().lower()
        return not status or status not in self.__policy["verdict"]["no_pep_values"]

    def __type_patterns(self, forecast: dict | None, assessment: dict | None, crime_result: dict | None,
                      typologies: list[Typology] | None) -> list[dict]:
        """One row per crime person type: does its money fit (forecast), which researched pattern it
        was built from, and how many of that pattern's warning signs fired (crime scan)."""
        if not forecast or not assessment:
            return []
        matches = {m.typology.typology_id: m for m in (crime_result or {}).get("match_results", [])}
        by_id = {t.typology_id: t for t in typologies or []}
        fits = {row["type_id"]: row for row in assessment.get("types", [])}
        rows = []
        for person_type in forecast["types"]["person_types"]:
            type_id = person_type["type_id"]
            if type_id == FuturePaths.BASELINE_TYPE:
                continue
            fit = fits.get(type_id, {})
            typology_id = person_type.get("typology_id")
            if typology_id not in by_id:   # older replies: link by category, as ai_manager.link_typologies does
                typology_id = next((t.typology_id for t in typologies or []
                                    if t.crime_category == person_type.get("category")), None)
            match = matches.get(typology_id)
            typology = by_id.get(typology_id)
            rows.append({
                "type_id": type_id, "name": person_type["name"], "category": person_type["category"],
                "category_name": self.__config.category_name(person_type["category"]),
                "fits": bool(fit.get("fits")), "fit_score": fit.get("fit_score"),
                "route_years": fit.get("route_years", ""), "enabled_by": fit.get("enabled_by", ""),
                "typology_id": typology_id, "typology_name": typology.name if typology else None,
                "match": match.category if match else None,
                "fired": match.fired() if match else [],
                "quote": (typology.source_quotes or [{}])[0] if typology else {},
                "source_ids": typology.cited_report_ids() if typology else [],
            })
        return rows

    def describe_piece(self, case: dict, piece: str | None) -> str:
        """A forecast piece's name in words: 'call2_earnings.asset.0' -> 'asset 1 (Property - Condo, Bishan)'."""
        piece = piece or ""
        parts = piece.split(".")
        assets, jobs = case.get("investments", []), CaseTimeline(case).positions()
        if len(parts) == 3 and parts[1] == "asset" and parts[2].isdigit() and int(parts[2]) < len(assets):
            return f"asset {int(parts[2]) + 1} ({assets[int(parts[2])].get('asset_type', 'asset')})"
        if len(parts) == 3 and parts[1] == "position" and parts[2].isdigit() and int(parts[2]) < len(jobs):
            job = jobs[int(parts[2])]
            return f"the pay for job {int(parts[2]) + 1} ({job.get('occupation')} at {job.get('employer_name')})"
        names = {"step0_declaration": "reading the declaration", "call1_markets.list": "choosing the markets",
                 "call2_earnings.future_pay": "his future pay", "call3_types.list": "the list of person types",
                 "call4_events.list": "the future events"}
        if piece in names:
            return names[piece]
        if len(parts) == 3 and parts[0] == "call1_markets":
            return f"the {parts[2]} market figures"
        if len(parts) == 3 and parts[0].startswith("call3_types"):
            return f"how person type {parts[2]} behaves"
        if len(parts) == 3 and parts[0].startswith("call4_events"):
            return f"how person type {parts[2]} reacts to events"
        return piece or "an early step"

    def __agreement(self, checks: list[Check]) -> list[dict]:
        """Group the findings that count (failed, or a crime warning sign) by theme, most agreement first."""
        themes: dict = {}
        for check in checks:
            if check.status not in ("failed", "weak"):
                continue
            signs = check.extra("signs") or []
            if check.feature == "crime" and signs:
                keys = {CrimeScan.SIGN_THEMES.get(sign, "pattern") for sign in signs}
                if check.failed():
                    keys.add("pattern")
            elif check.failed():
                keys = {check.theme}
            else:
                continue
            for key in keys:
                entry = themes.setdefault(key, {"theme": key, "title": VerdictEngine.THEMES[key], "features": [], "lines": []})
                if check.feature not in entry["features"]:
                    entry["features"].append(check.feature)
                detail = check.detail
                if check.feature == "crime" and key != "pattern":   # only the warning signs of this theme
                    detail = "warning signs fired: " + ", ".join(
                        CrimeScan.SIGN_LABELS.get(sign, sign) for sign in signs if CrimeScan.SIGN_THEMES.get(sign) == key)
                entry["lines"].append(f"{check.feature.capitalize()}: {check.label} - {detail}")
                entry.setdefault("short", []).append(f"{check.feature.capitalize()}: {check.label}")
        order = list(VerdictEngine.THEMES)
        return sorted(themes.values(), key=lambda t: (-len(t["features"]), order.index(t["theme"])))

    def _documents(self, assessment: dict | None, bench: list[Check], crime: list[Check],
                   typologies: list[Typology] | None,
                   case: dict, docs: list[Check] | None = None) -> list[dict]:
        """Documents to ask for: first for what his own documents contradict, then the forecast's (failed
        checks, then the ones that rule out the most stories), the benchmark's failed checks, and the
        matched patterns' typical documents."""
        policy = self.__policy
        names = self.__config.vocabulary.get("document_codes", {})
        settings = policy["verdict"]
        wanted, seen = [], set()

        def add(document: str, reason: str) -> None:
            key = document.strip().lower()
            if key and key not in seen:
                seen.add(key)
                wanted.append({"document": document, "reason": reason})

        kinds = settings["document_evidence"]
        for check in docs or []:
            if check.status in ("failed", "weak") and check.check.lower() in kinds:
                for code in kinds[check.check.lower()]["documents"]:
                    if code in names:
                        add(names[code], f"His documents show: {check.label.lower()}")
        for document in (assessment or {}).get("documents", []):
            add(document["document"], document["reason"])
        for check in bench:
            if not check.failed():
                continue
            rule = "COMPOSITION" if check.check.startswith("COMPOSITION") else check.check
            for code in settings["benchmark_documents"].get(rule, []):
                if code in names:
                    add(names[code], f"Benchmark check failed: {check.label.lower()}")
        by_id = {t.typology_id: t for t in typologies or []}
        for check in crime:
            if check.check == "TYPOLOGY" and check.status in ("failed", "weak"):
                name = check.label.split(" [")[0]
                typology = by_id.get(check.extra("typology_id"))
                for document in typology.typical_documents if typology else []:
                    add(document, f"Matches the known pattern: {name}")
        return wanted[:settings["max_documents"]]

    def __build_context(self, case: dict, results: dict) -> dict:
        """What the checks are worked out from: the case and the results, the forecast and its
        assessment, the honest numbers (None if there is no forecast to take them from) and the
        crime person types."""
        forecast, assessment = results.get("forecast"), results.get("forecast_assessment")
        honest = None
        if forecast and assessment:
            honest = self.__feature("forecast").honest_numbers(case, forecast, assessment)
        types = self.__type_patterns(forecast, assessment, results.get("crime_result"), results.get("typologies"))
        return {"case": case, "results": results, "forecast": forecast, "assessment": assessment,
                "honest": honest, "types": types}

    def __collect_checks(self, context: dict) -> dict[str, list[Check]]:
        """Every feature's checks, as {"benchmark", "forecast", "crime", "documents": [Check, ...]}.
        The documents are checked first, because the types then record which documents support them."""
        case, results = context["case"], context["results"]
        forecast, assessment = context["forecast"], context["assessment"]
        honest, types = context["honest"], context["types"]
        evidence = results.get("evidence")
        docs = self.__feature_checks("documents", {"evidence": evidence, "types": types})
        for t in types:                                 # which of his documents support each crime story
            t["documents"] = [c.label for c in docs if c.failed() and t["category"] in c.supports]
        bench = self.__feature_checks("benchmark", {
            "case": case, "bench_input": results.get("benchmark_input"), "ai_data": results.get("benchmark_ai"),
            "findings": results.get("benchmark_findings"), "honest": honest, "assessment": assessment,
            "declaration": results.get("declaration"), "markets": results.get("markets"), "types": types})
        fore = self.__feature_checks("forecast", {
            "case": case, "assessment": assessment, "honest": honest, "types": types,
            "failed_step": results.get("failed_step"),
            "unmodelled": (forecast or {}).get("earnings", {}).get("fallback_assets")})
        for adjusted in reversed(results.get("pay_adjustments") or []):
            fore.insert(1, self.__check("forecast", "PAY_FROM_DOCUMENTS", "Pay taken from his documents", "wealth", "info",
                                  f"The AI estimated {Formatter.sgd(adjusted['ai_pay'])} for {adjusted['year']}; "
                                  f"{adjusted['source_file'] or 'his documents'} shows {Formatter.sgd(adjusted['documented_pay'])}, "
                                  f"so his pay as {adjusted['job']} was scaled x{adjusted['ratio']:g} for every year of that job."))
        crime = self.__feature_checks("crime", {
            "crime_result": results.get("crime_result"), "reports": results.get("reports"),
            "typologies": results.get("typologies"), "types": types, "forecast_ran": forecast is not None})
        return {"benchmark": bench, "forecast": fore, "crime": crime, "documents": docs}

    def combine(self, case: dict, results: dict) -> Verdict:
        """ONE Verdict from the crime scan, the benchmark, the forecast and the documents.

        results: reports (the trusted ResearchReports; None if the research did not run),
                 typologies (the Typology objects), crime_result (CrimeScan.run: its match_results are
                 MatchResult objects), declaration (the Declaration forecast Step 0 read),
                 benchmark_input, benchmark_ai, benchmark_findings, forecast, forecast_assessment,
                 markets (Call 1, even if the forecast stopped later), evidence (the documents layer),
                 pay_adjustments (calibrate_pay), failed_step, not_run, notes, and the
                 assessment_id and assessed_at the caller gives this assessment (the engine
                 makes no ids and reads no clock)

        The Verdict holds the outcome, every feature's checks, the next step and review date,
        the notes and what could not run, the explanation (reasons, agreement, documents to
        request, evidence ...) and the report both front ends show.

        The ladder (config/policy.json "verdict" holds the numbers):
          SERIOUS RISK   the honest story can't explain his wealth AND a crime story can AND another
                         feature agrees (its warning signs fired, his documents support it, or a
                         benchmark failure the forecast can't explain); OR his documents contradict his
                         declaration in several ways AND another feature agrees. One feature alone can
                         never reach Serious Risk.
          "RISKY"          the honest story fails or only works at the optimistic edge, a purchase he
                         couldn't afford, a crime story that fits whose warning signs fired, money for
                         the bank he can't fund, a PEP with a public-office crime story that fits, or
                         several unexplained benchmark failures
          MANUAL REVIEW  loose ends: an unexplained benchmark failure, other forecast checks failed,
                         a borderline result, a PEP, a known pattern on its own, a part that couldn't run,
                         or nothing ran at all (an assessment that checked nothing is never PASSED)
          "PASSED"         everything else
        """
        policy = self.__policy
        settings = policy["verdict"]
        context = self.__build_context(case, results)
        forecast, assessment = context["forecast"], context["assessment"]
        honest, types = context["honest"], context["types"]
        collected = self.__collect_checks(context)
        bench, fore, crime, docs = (collected["benchmark"], collected["forecast"], collected["crime"],
                                    collected["documents"])
        checks = bench + fore + crime + docs

        triggers: list[tuple[str, str]] = []           # (level, reason)

        def flag(level: str, reason: str) -> None:
            triggers.append((level, reason))

        unexplained = [c for c in bench if c.failed() and c.extra("independent")]
        fitting = [t for t in types if t["fits"]]
        backed = [t for t in fitting if t["match"] in CrimeScan.FULL_MATCH]
        contradicted = [c for c in docs if c.failed()]

        if honest:
            t1 = honest["t1"]
            if not t1["fits"]:
                agrees = ([f"{t['type_id']}'s warning signs fired ({CrimeScan.MATCH_LABELS[t['match']]} match)" for t in backed]
                          + [f"his documents support {t['type_id']} ({', '.join(t['documents']).lower()})"
                             for t in fitting if t["documents"]]
                          + [f"the benchmark's {c.label.lower()} check failed and the forecast can't explain it"
                             for c in unexplained])
                if fitting and agrees:
                    flag("SERIOUS_RISK", "The honest story can't explain his wealth, a crime story can ("
                         + "; ".join(f"{t['type_id']} {t['name']}" for t in fitting) + "), and another check agrees: "
                         + "; ".join(agrees[:3]) + ".")
                elif fitting:
                    flag("RISKY", "The honest story can't explain his wealth and a crime story can ("
                         + "; ".join(f"{t['type_id']} {t['name']}" for t in fitting)
                         + "), but no other check agrees yet.")
                else:
                    flag("RISKY", "No story explains his wealth: neither the honest story nor any crime story reaches "
                         f"{Formatter.sgd(case['claims']['declared_net_worth'])}.")
            elif not t1["fits_at_typical"]:
                flag("RISKY", "The honest story only reaches his declared wealth at its optimistic edge.")
            for check in fore:
                if check.check == "AFFORDABILITY" and check.failed():
                    flag("RISKY", f"He couldn't have afforded the {check.label.split(':')[0]}: {check.detail}.")
            for t in backed:
                flag("RISKY", f"{t['type_id']} {t['name']} fits his money AND its researched pattern's warning signs "
                            f"fired ({CrimeScan.MATCH_LABELS[t['match']]} match).")
            if assessment["borderline"]:
                flag("MANUAL_REVIEW", "The result is borderline: it changes when every forecast moves 10%.")
            other = [c for c in fore if c.failed()
                     and c.check in ("ASSET_VALUE", "ASSET_INCOME", "JURISDICTION", "UNQUANTIFIED_SOURCE", "WEALTH_JUMP")]
            if other:
                flag("MANUAL_REVIEW", f"{len(other)} forecast check(s) failed: "
                     + "; ".join(c.label for c in other[:4])
                     + (f"; and {len(other) - 4} more." if len(other) > 4 else "."))

        # What his own documents show against what he declared
        if contradicted:
            found = "; ".join(c.label.lower() for c in contradicted)
            others = []
            if honest and not honest["t1"]["fits"]:
                others.append("the honest story can't explain his wealth")
            elif honest and not honest["t1"]["fits_at_typical"]:
                others.append("the honest story only reaches his wealth at its optimistic edge")
            others += [f"{t['type_id']} {t['name']} fits his money" for t in fitting]
            others += [f"the crime scan matched \"{c.label.split(' [')[0]}\"" for c in crime
                       if c.check == "TYPOLOGY" and c.failed()]
            others += [f"the benchmark's {c.label.lower()} check failed" for c in unexplained]
            others += [f"he couldn't have afforded the {c.label.split(':')[0]}" for c in fore
                       if c.check == "AFFORDABILITY" and c.failed()]
            if len(contradicted) >= settings["min_serious_document_findings"] and others:
                flag("SERIOUS_RISK", f"His documents contradict his declaration ({len(contradicted)} findings: {found}), "
                                   "and another check agrees: " + "; ".join(others[:3]) + ".")
            else:
                flag("RISKY", f"His documents contradict his declaration: {found}.")
        loose = [c for c in docs if c.status == "weak"]
        if loose:
            flag("MANUAL_REVIEW", "His documents show things to check: " + "; ".join(c.label.lower() for c in loose) + ".")

        if any(c.check == "AUM_FUNDING" and c.failed() for c in bench):
            flag("RISKY", "He plans to bring more money to the bank than his cash and shares can fund.")
        if self._is_pep(case):
            answered = bool(str(case["claims"].get("pep_status") or "").strip())
            who = "He is a PEP" if answered else "His PEP status is not answered, so he is treated as a PEP"
            pep_types = [t for t in fitting if t["category"] in settings["pep_crime_categories"]]
            if pep_types:
                flag("RISKY", f"{who} and a public-office crime story fits his money ("
                     + "; ".join(f"{t['type_id']} {t['name']}" for t in pep_types) + ").")
            else:
                flag("MANUAL_REVIEW", f"He is a PEP ({case['claims']['pep_status']}): a KYC officer must review him."
                     if answered else "His PEP status is not answered, so it is unknown: a KYC officer must ask "
                     "him and review him before he can be passed.")
        counted = [c for c in unexplained if c.check != "AUM_FUNDING"]      # AUM has its own rule above
        if len(counted) >= settings["unexplained_benchmark_for_risky"]:
            flag("RISKY", f"{len(counted)} benchmark checks failed that the forecast can't explain: "
                 + ", ".join(c.label.lower() for c in counted) + ".")
        elif counted:
            flag("MANUAL_REVIEW", "Benchmark check(s) failed that the forecast can't explain: "
                 + ", ".join(c.label.lower() for c in counted) + ".")
        built = {t["typology_id"] for t in fitting if t["typology_id"]}
        for check in crime:
            if check.check == "TYPOLOGY" and check.extra("match") not in (None, "no_match"):
                level = settings["pattern_alone"].get(check.extra("match"), "PASSED")
                if level != "PASSED" and check.extra("typology_id") not in built:
                    flag(level, f"Known pattern \"{check.label.split(' [')[0]}\": {check.detail}.")
        for part in results.get("not_run", []):
            flag("MANUAL_REVIEW", f"{part} couldn't run, so a person must check what it would have covered.")
        if not any(results.get(key) for key in ("forecast", "crime_result", "benchmark_findings", "benchmark_ai")):
            flag("MANUAL_REVIEW", "None of the forecast, the crime scan or the peer benchmark ran, so nothing "
                                  "was checked: a person must review him before he can be passed.")

        level = max((t[0] for t in triggers), key=lambda lv: Verdict.SEVERITY[lv], default="PASSED")
        reasons = []
        for trigger_level, reason in sorted(triggers, key=lambda t: -Verdict.SEVERITY[t[0]]):
            if reason not in [r["text"] for r in reasons]:
                reasons.append({"level": trigger_level, "text": reason})
        summary = reasons[0]["text"] if reasons else "Every check came back clean or was explained by another feature."

        # Next review: by the verdict, sooner if the forecast says two stories can be told apart earlier
        current = case["current_date"]
        review = Formatter.add_months(current, policy["review_interval_months"][level])
        for watch in (assessment or {}).get("watch_dates", []):
            if "told apart" in watch["what"] and current < watch["date"] < review:
                review = watch["date"]

        groups: dict = {}
        for check in bench + fore + docs:
            groups.setdefault((check.feature, check.group), []).append(check.status)
        clean = [group for (feature, group), statuses in groups.items()
                 if statuses and all(s == "passed" for s in statuses)]

        verdict = Verdict(results.get("assessment_id", ""), case["client_ref"], results.get("assessed_at", ""),
                          level, policy["routing"][level], review,
                          list(results.get("notes", [])), list(results.get("not_run", [])))
        for check in checks:
            verdict.add_check(check)
        verdict.explanation = {
            "name": case.get("name", ""),
            "assessed_on": current,
            "policy_version": policy["policy_version"],
            "verdict_label": VerdictEngine.VERDICT_LABELS[level],
            "summary": summary,
            "reasons": reasons,
            "agreement": self.__agreement(checks),
            "types": types,
            "documents": (self._documents(assessment, bench, crime, results.get("typologies"), case, docs)
                          if level != "PASSED" else []),
            "clean": clean,
            "evidence": self.__evidence(case, results, assessment, honest),
        }
        verdict.report = self.__report(verdict)
        return verdict

    def __evidence(self, case: dict, results: dict, assessment: dict | None, honest: dict | None) -> list[dict]:
        """The detail behind the verdict, shown under "Full evidence"."""
        sections = []
        evidence = results.get("evidence") or {}
        if evidence.get("files"):
            lines = [f"Read: {', '.join(evidence['files'])}"]
            lines += [f"Pay shown for {p['year']}: {Formatter.sgd(p['amount'])} ({p['source_file'] or 'documents'})"
                      for p in evidence.get("documented_pay", [])]
            lines += [f"{f['summary']} ({', '.join(f['source_files'])})" for f in evidence.get("findings", [])]
            if not evidence.get("findings"):            # the findings already say what the notes say
                lines += [f"Reader's note: {note}" for note in evidence.get("notes", [])]
            sections.append({"title": "What his documents show", "lines": lines})
        reports = results.get("reports") or []
        sections.append({"title": "Research reports", "lines": [
            f"[{r.report_id or '?'}] {r.organisation}{' (' + str(r.year) + ')' if r.year else ''}"
            f" - {r.title}" for r in reports] or ["No research reports were found."]})
        typology_lines = []
        for t in results.get("typologies") or []:
            unchecked = "" if t.verified else " (not checked against research)"
            typology_lines.append(f"{t.name} ({self.__config.category_name(t.crime_category)}){unchecked}")
            if t.description:
                typology_lines.append(f"    {t.description}")
        sections.append({"title": "Sector typologies", "lines": typology_lines or ["No verified typologies."]})
        if assessment and honest:
            sections.append({"title": "Person types", "lines": [
                f"{row['type_id']} {row['name']} - {'fits' if row['fits'] else 'does not fit'} "
                f"(fit {row['fit_score']:.2f}); wealth today "
                f"{Formatter.sgd(row['wealth_now']['cautious'])} to {Formatter.sgd(row['wealth_now']['optimistic'])}; route {row['route']}"
                for row in assessment["types"]]})
            documented = {p["year"]: p for p in evidence.get("documented_pay", [])}
            rows = honest["savings_rows"]
            shown = [row for i, row in enumerate(rows) if i % 5 == 0 or i == len(rows) - 1 or row["year"] in documented]
            sections.append({"title": "Career savings (typical, every 5 years)", "lines": [
                f"{row['year']}: pay {Formatter.sgd(row['total_pay']['typical'])}"
                + (f" (documents show {Formatter.sgd(documented[row['year']]['amount'])})" if row["year"] in documented else "")
                + f", saved {Formatter.sgd(row['saved']['typical'])}, savings so far {Formatter.sgd(row['savings']['typical'])}"
                for row in shown]})
            events = {}
            for row in assessment["event_impacts"]:
                events.setdefault((row["year"], row["event_id"], row["event"], row["chance"]), []).append(
                    f"{row['type_id']} {'+' if row['impact'] >= 0 else ''}{Formatter.sgd(row['impact'])}")
            sections.append({"title": "Future events and how each story's 2030 wealth would change", "lines": [
                f"{year} {name} ({chance:.0%} chance): " + ", ".join(impacts)
                for (year, event_id, name, chance), impacts in sorted(events.items())] or ["No events."]})
            sections.append({"title": "When the stories can be told apart", "lines": [
                f"T1 and {d['type_id']}: " + (f"from {d['distinguishable_from']}" if d["distinguishable_from"]
                                             else "not within the forecast years (his wealth alone won't tell them apart)")
                for d in assessment["divergence"]] or ["No crime stories to tell apart."]})
            names = self.__config.vocabulary.get("signal_codes", {})
            sections.append({"title": "Normal account activity next year (honest story)", "lines": [
                f"{names.get(code, code)}: up to {Formatter.sgd(r['amount_max'])} a year"
                + (f" in up to {r['count_max']:g} payments" if r["count_max"] >= 2 else "")
                for code, r in assessment["monitoring_ranges"].items()] or ["None forecast."]})
            quality = assessment["data_quality"]
            sections.append({"title": "Data quality", "lines": [
                f"{quality['market_figures']} market figures, {quality['unverified_share']:.0%} from AI memory "
                "(not checked online) or missing."] + [f"Gap: {gap}" for gap in quality["data_gaps"]]})
            sections.append({"title": "Stability test (the forecast's own result)", "lines": [
                f"Forecasts {shift}: {VerdictEngine.VERDICT_LABELS.get(outcome, outcome)}"
                for shift, outcome in assessment["stability"].items()]})
        warnings = list(dict.fromkeys(n for n in results.get("notes", [])
                                      if not any(word in n.lower() for word in VerdictEngine._ROUTINE_NOTES)))
        if warnings:
            sections.append({"title": "Warnings from the run", "lines": warnings})
        return sections

    def _items(self, checks: list[dict], statuses: tuple) -> list[dict]:
        return [{"mark": VerdictEngine.MARKS[c["status"]], "text": f"{c['label']}: {c['detail']}",
                 "sub": [c["explanation"]] if c["explanation"] else []}
                for c in checks if c["status"] in statuses and not c.get("optional")]

    def _benchmark_items(self, checks: list[dict]) -> list[dict]:
        """The benchmark section: the 9 original checks every time (passed, failed, explained or not
        run, each with its numbers), then any of the newer checks that failed or need a look."""
        by_rule = {c["check"]: c for c in checks}
        items = []
        for rule in VerdictEngine.ORIGINAL_BENCHMARK:
            check = by_rule.get(rule)
            if check is None:
                items.append({"mark": "skip", "text": f"{Benchmark.BENCHMARK_LABELS[rule]}: couldn't run - the peer benchmark "
                                                      "didn't finish, so this wasn't compared with peers.", "sub": []})
                continue
            items.append({"mark": VerdictEngine.MARKS[check["status"]], "text": f"{check['label']}: {check['detail']}",
                          "sub": [check["explanation"]] if check["explanation"] else []})
        newer = [c for c in checks if c["check"] not in VerdictEngine.ORIGINAL_BENCHMARK and c["check"] != "PEER_BENCHMARK"]
        return items + self._items(newer, ("failed", "explained", "weak", "skipped"))

    def __report(self, verdict: Verdict) -> dict:
        """The report as plain data: a header, short sections of marked lines, and the full evidence.
        ReportView prints it and the web app's template shows it, so both give exactly the same content.

        The benchmark section always lists its 9 original checks, passed or not. The other sections show
        only what matters: failures, what another feature explained, loose ends and what couldn't run;
        their passed checks are listed under "What came back clean"."""
        data = verdict.details()            # the saved layout, which the sections below read
        level_marks = {"SERIOUS_RISK": "fail", "RISKY": "fail", "MANUAL_REVIEW": "weak", "PASSED": "pass"}
        why = [{"mark": level_marks[r["level"]], "text": f"[{VerdictEngine.VERDICT_LABELS[r['level']]}] {r['text']}", "sub": []}
               for r in data["reasons"]] or [{"mark": "pass", "text": data["summary"], "sub": []}]
        why += [{"mark": "fail", "text": f"Checks agree - {a['title']} ({len(a['features'])} features: "
                                         f"{', '.join(a['features'])})",
                 "sub": ["; ".join(dict.fromkeys(a.get("short", a["lines"])))]}
                for a in data["agreement"] if len(a["features"]) > 1]

        forecast = self._items(data["forecast"], ("failed", "weak", "explained", "skipped"))
        forecast += [{"mark": "info", "text": f"{c['label']}: {c['detail']}", "sub": []} for c in data["forecast"]
                     if c["check"] == "PAY_FROM_DOCUMENTS"
                     or (c["check"] == "CRIME_STORY" and c["detail"].startswith("Fits"))]
        forecast += [{"mark": "pass", "text": f"{c['label']}: {c['detail']}", "sub": []} for c in data["forecast"]
                     if c["check"] == "STABILITY" and c["status"] == "passed"]
        crime = self._items(data["crime"], ("failed", "weak", "skipped"))
        documents = self._items(data["document_findings"], ("failed", "weak", "skipped", "info", "passed"))
        for item, check in zip(documents, [c for c in data["document_findings"]
                                           if c["status"] in ("failed", "weak", "skipped", "info", "passed")]):
            if check.get("sources"):
                item["sub"] = item["sub"] + [f"From: {', '.join(check['sources'])}"]

        sections = [
            {"title": "Why", "items": why},
            {"title": "Benchmark - compared with peers in the same economy",
             "items": self._benchmark_items(data["benchmark"])},
            {"title": "Forecast - what it predicted",
             "items": forecast or [{"mark": "pass", "text": "Every forecast check passed.", "sub": []}]},
            {"title": "Crime - known patterns for his industry",
             "items": crime or [{"mark": "pass", "text": "No known pattern matched his declaration.", "sub": []}]},
            {"title": "Documents - what his papers show", "items": documents},
            {"title": "Documents to request", "items": [
                {"mark": "info", "text": f"{n}. {d['document']}", "sub": [d["reason"]]}
                for n, d in enumerate(data["documents"], 1)]
             or [{"mark": "pass", "text": "None.", "sub": []}]},
            {"title": "What came back clean", "items": [{"mark": "pass", "text": group, "sub": []}
                                                        for group in data["clean"]]
             or [{"mark": "info", "text": "Nothing came back fully clean.", "sub": []}]},
        ]
        if data["not_run"]:
            sections.append({"title": "Could not run", "items": [{"mark": "skip", "text": part, "sub": []}
                                                                 for part in data["not_run"]]})
        return {
            "header": {"client_ref": data["client_ref"], "name": data["name"],
                       "assessed_on": data["assessed_on"], "verdict": data["verdict"],
                       "verdict_label": data["verdict_label"], "next_step": data["next_step"],
                       "next_review_date": data["next_review_date"], "summary": data["summary"],
                       "policy_version": data["policy_version"]},
            "sections": sections,
            "evidence": data["evidence"],
            "evidence_titles": [part["title"] for part in data["evidence"]],
            "legend": VerdictEngine.REPORT_LEGEND,
        }