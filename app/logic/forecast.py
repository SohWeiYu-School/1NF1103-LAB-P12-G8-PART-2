"""Forecast: could the money add up under each person type?"""

from app.logic.case_timeline import CaseTimeline
from app.logic.risk_analysis import RiskAnalysis
from app.logic.formatter import Formatter
from app.logic.future_paths import FuturePaths
from app.logic.market_model import MarketModel
from app.logic.onboarding_assessor import OnboardingAssessor
from app.logic.pay_calibrator import PayCalibrator
from app.model.band import Band
from app.model.check import Check
from app.model.config import Config


class Forecast(RiskAnalysis):
    """The forecast feature. From the AI's forecast (markets, pay, assets, person types,
    events) it works out, with arithmetic only, whether the declared wealth fits the honest
    type or a crime type, how stable that answer is, what to watch and which documents
    would settle it.

    When it is given a forecast it creates the objects that do the work and owns them:
    the MarketModel, the FuturePaths, the OnboardingAssessor and the PayCalibrator.
    """

    NAME: str = "forecast"

    def __init__(self, policy: dict | None = None, config: Config | None = None) -> None:
        super().__init__(policy)
        self.__config: Config = config or Config(self._policy, {})
        self.__forecast: dict = {}
        self.__market_model: MarketModel = MarketModel()
        self.__future_paths: FuturePaths = FuturePaths(self.__market_model, {}, self._policy)
        self.__assessor: OnboardingAssessor = OnboardingAssessor(self.__future_paths, self._policy, self.__config)
        self.__pay_calibrator: PayCalibrator = PayCalibrator(self.__future_paths.career_savings(), self._policy)

    def run(self, case: dict, ai_data: dict) -> dict:
        """The forecast assessment for this case. ai_data is {"forecast": the finished forecast}."""
        self.__use(ai_data["forecast"])
        results = self._assess(case)
        self._results = results
        return results          # the local value: another run may replace self._results meanwhile

    def checks(self, context: dict) -> list[Check]:
        """The forecast's findings. context holds case, assessment, honest, types, failed_step, unmodelled."""
        return self._forecast_checks(
            context["case"], context.get("assessment"), context.get("honest"), context.get("types") or [],
            context.get("failed_step"), context.get("unmodelled"))

    def honest_numbers(self, case: dict, forecast: dict, assessment: dict) -> dict:
        """The honest type's figures the benchmark and the report compare against."""
        self.__use(forecast)
        return self.__honest_numbers(case, assessment)

    def calibrate_pay(self, case: dict, forecast: dict, documented_pay: list[dict]) -> tuple[dict, list[dict]]:
        """The forecast with its pay set to what his documents show, and what was changed."""
        return self.__pay_calibrator.calibrate(case, forecast, documented_pay)

    def __use(self, forecast: dict) -> None:
        """Take a forecast and build the objects that read it."""
        self.__forecast = forecast or {}
        self.__market_model = MarketModel(self.__forecast)
        self.__future_paths = FuturePaths(self.__market_model, self.__forecast, self._policy)
        self.__assessor = OnboardingAssessor(self.__future_paths, self._policy, self.__config)
        self.__pay_calibrator = PayCalibrator(self.__future_paths.career_savings(), self._policy)

    def _enabled_by_text(self, person_type: dict, record: dict) -> str:
        """What makes this type possible for him, in words: the job, asset or declared source."""
        if person_type["type_id"] == FuturePaths.BASELINE_TYPE:
            return "everything he declared"
        parts = []
        jobs = CaseTimeline(record).positions()
        assets = record.get("investments", [])
        job_index = person_type.get("enabled_by_position_index")
        asset_index = person_type.get("enabled_by_asset_index")
        if job_index is not None and 0 <= job_index < len(jobs):
            job = jobs[job_index]
            parts.append(f"job {job_index} ({job.get('title') or job.get('occupation') or 'position'}, "
                         f"{job.get('country', '')})")
        if asset_index is not None and 0 <= asset_index < len(assets):
            parts.append(f"asset {asset_index} ({assets[asset_index].get('asset_type', 'asset')})")
        if person_type.get("enabled_by_source_id"):
            parts.append(f"declared source {person_type['enabled_by_source_id']}")
        return " and ".join(parts) or "not stated"

    def __rank_documents(self, candidates: list[str]) -> list[dict]:
        """Documents ordered by how many candidate types each one would rule out."""
        forecast = self.__forecast
        pool = set(candidates)
        covers: dict[str, set] = {}
        for person_type in forecast["types"]["person_types"]:
            if person_type["type_id"] not in pool:
                continue
            for document in person_type["rule_out_documents"]:
                ruled_out = ({person_type["type_id"]} | set(document["also_rules_out"])) & pool
                covers.setdefault(document["document_code"], set()).update(ruled_out)
        ranked = sorted(covers.items(), key=lambda item: (-len(item[1]), item[0]))
        return [{"document_code": code, "rules_out": sorted(types)} for code, types in ranked]

    def document_request(self, failures: list[dict], candidates: list[str]) -> list[dict]:
        """Documents for failed checks first, then the ones that rule out the most types."""
        policy = self._policy
        names = self.__config.vocabulary.get("document_codes", {})
        lookup = policy.get("breach_documents", {})
        request, seen = [], set()

        def add(code: str, reason: str) -> None:
            if code in names and code not in seen:
                seen.add(code)
                request.append({"document_code": code, "document": names[code], "reason": reason})

        for failure in failures:
            key = failure["rule_id"]
            if key in ("ASSET_VALUE", "ASSET_INCOME"):
                key = f"{key}.{failure['category']}"
            elif key == "AFFORDABILITY":
                key = f"AFFORDABILITY.{failure['payment_method']}"
            elif key == "UNQUANTIFIED_SOURCE":
                key = f"UNQUANTIFIED_SOURCE.{failure['source_type']}"
            for code in lookup.get(key, []):
                add(code, failure["detail"])
        if len(candidates) > 1:
            for document in self.__rank_documents(candidates):
                add(document["document_code"], f"rules out {', '.join(document['rules_out'])}")
        return request[:policy["max_documents"]]

    def __data_quality(self) -> dict:
        """How many market figures the AI could only give from memory or not at all."""
        forecast = self.__forecast
        figures = [row for series in forecast["markets"]["series"].values() for row in series["history"]]
        unverified = [row for row in figures
                      if row["change_pct"] is None or "unverified" in row["source_name"].lower()]
        gaps = list(forecast["markets"]["data_gaps"])
        for series in forecast["markets"]["series"].values():
            gaps += series["data_gaps"]
        return {"market_figures": len(figures),
                "unverified_share": round(len(unverified) / len(figures), 3) if figures else 0.0,
                "data_gaps": sorted(set(gaps))}

    def _assess(self, record: dict) -> dict:
        """Measure the client against the forecasts and decide. No AI involved."""
        forecast = self.__forecast
        policy = self._policy
        start, end = CaseTimeline(record).career_years()
        years = CaseTimeline(record).future_years()
        savings_rows = self.__future_paths.career_savings().rows(start, end)
        paths = self.__future_paths.asset_path().build(record, end, "steady")

        # The decision, plus the stability test with every forecast 10% lower and higher
        shift = policy["stability_shift"]
        main = self.__assessor.evaluate(record, forecast, savings_rows, paths)
        stability = {f"{-shift:+.0%}": self.__assessor.evaluate(record, forecast, savings_rows, paths, 1 - shift)["outcome"],
                     "+0%": main["outcome"],
                     f"{shift:+.0%}": self.__assessor.evaluate(record, forecast, savings_rows, paths, 1 + shift)["outcome"]}
        outcome, borderline = self.__assessor.stable_outcome(main["outcome"], stability)

        # Type table and starting scores (every type starts equal; only the fit separates them)
        names = {t["type_id"]: t for t in forecast["types"]["person_types"]}
        total_fit = sum(f["fit_score"] for f in main["fits"].values()) or 1.0
        type_table = []
        for type_id, fit in main["fits"].items():
            behaviour = forecast["types"]["behaviour"][type_id]
            person_type = names[type_id]
            type_table.append({**fit, "category": person_type["category"],
                               "category_name": self.__config.category_name(person_type["category"]),
                               "name": person_type["name"], "route": person_type["route"],
                               "enabled_by": self._enabled_by_text(person_type, record),
                               "why_it_applies": person_type.get("why_it_applies", ""),
                               "route_years": f"{behaviour['route_open_from']}-{behaviour['route_open_to']}",
                               "score": round(fit["fit_score"] / total_fit, 3)})

        # Reasons in plain words
        t1 = main["fits"][FuturePaths.BASELINE_TYPE]
        declared = record["claims"]["declared_net_worth"]
        others_fit = [t for t, f in main["fits"].items() if t != FuturePaths.BASELINE_TYPE and f["fits"]]
        reasons = [f"Declared net worth {declared:,.0f}; the honest version explains "
                   f"{t1['wealth_now']['cautious']:,.0f} to {t1['wealth_now']['optimistic']:,.0f}."]
        if not t1["fits"]:
            reasons.append("The honest version does not fit his figures.")
        if others_fit:
            reasons.append("Crime types that do fit: " + "; ".join(
                f"{t} {self.__config.category_name(names[t]['category'])} via {self._enabled_by_text(names[t], record)} "
                f"({forecast['types']['behaviour'][t]['route_open_from']}-"
                f"{forecast['types']['behaviour'][t]['route_open_to']})" for t in others_fit) + ".")
        for row in main["affordability"][FuturePaths.BASELINE_TYPE]:
            if not row["affordable"]:
                reasons.append(f"{row['year']}: he needed {row['needed']:,.0f} in cash but the honest "
                               f"version had at most {row['available']['optimistic']:,.0f}.")
        failures = [c for c in main["asset_checks"] + [main["jurisdiction"]] + main["sources"] if c["failed"]]
        reasons += [c["detail"] for c in failures]
        if borderline:
            reasons.append(f"Borderline: the outcome changes when the forecasts move 10% ({stability}).")

        # Documents: for the failed checks, then to tell the fitting types apart
        affordability_failures = [{"rule_id": "AFFORDABILITY", "payment_method": row["payment_method"],
                                   "detail": f"{row['year']} purchase of asset {row['asset_index']}"}
                                  for row in main["affordability"][FuturePaths.BASELINE_TYPE] if not row["affordable"]]
        if not t1["fits"]:
            affordability_failures.insert(0, {"rule_id": "NET_WORTH", "detail": reasons[0]})
        candidates = [FuturePaths.BASELINE_TYPE] + others_fit
        if len(candidates) == 1 and outcome != "PASSED":
            candidates = [t for t, b in forecast["types"]["behaviour"].items() if b["route_open_to"] >= end]
        documents = []
        if outcome != "PASSED":
            documents = self.document_request(affordability_failures + failures, candidates)

        # The future
        expected = self.__future_paths.expected_paths(record, savings_rows)
        divergence = self.__future_paths.divergence_years(expected)
        watch_dates = sorted(
            [{"date": f"{d['distinguishable_from']}-01-01", "what": f"{FuturePaths.BASELINE_TYPE} and {d['type_id']} "
              "can be told apart"} for d in divergence if d["distinguishable_from"]]
            + [{"date": f"{e['year']}-01-01", "what": f"{e['event_id']} {e['name']} could happen"}
               for e in forecast["events"]["events"]],
            key=lambda w: (w["date"], w["what"]))
        scheduled = Formatter.add_months(record["current_date"], policy["review_interval_months"][outcome])
        first_divergence = [w["date"] for w in watch_dates if "told apart" in w["what"] and w["date"] > record["current_date"]]

        return {
            "case_ref": record["client_ref"],
            "assessed_on": record["current_date"],
            "policy_version": policy["policy_version"],
            "prompt_versions": forecast.get("prompt_versions", {}),
            "outcome": outcome,
            "routing": policy["routing"][outcome],
            "reasons": reasons,
            "borderline": borderline,
            "stability": stability,
            "declared_net_worth": declared,
            "types": type_table,
            "affordability": main["affordability"][FuturePaths.BASELINE_TYPE],
            "asset_checks": main["asset_checks"],
            "jurisdiction": main["jurisdiction"],
            "declared_sources": main["sources"],
            "country_notes": [{"country": j["country"], "listings": j["listings"], "summary": j["summary"],
                               "source_name": j["source_name"]} for j in forecast["markets"]["jurisdictions"]],
            "markets_used": [{"market_id": m["market_id"], "name": m["name"], "country": m["country"],
                              "indicator": m["indicator"]} for m in forecast["markets"]["relevant_markets"]],
            "career_savings": savings_rows,
            "career_outlook": forecast["earnings"]["future_pay"]["career_outlook"],
            "forward_paths": {t: [{"year": y, **v} for y, v in points.items()] for t, points in expected.items()},
            "event_impacts": self.__future_paths.event_impacts(record, savings_rows),
            "divergence": divergence,
            "monitoring_ranges": self.__future_paths.monitoring_ranges(years[0]),
            "documents": documents,
            "watch_dates": watch_dates,
            "next_review_date": min([scheduled] + first_divergence),
            "data_quality": self.__data_quality(),
        }

    def economy_brief(self, markets: dict | None) -> dict | None:
        """What the benchmark AI may see of the forecast's economy (Call 1): each market's yearly %
        change and each country's risk listings. Nothing about the client's own figures."""
        if not markets or not markets.get("series"):
            return None
        return {
            "markets": [{"name": m["name"], "country": m["country"], "indicator": m["indicator"],
                         "yearly_change_pct": {str(h["year"]): h["change_pct"]
                                               for h in markets["series"].get(m["market_id"], {}).get("history", [])}}
                        for m in markets.get("relevant_markets", [])],
            "country_listings": [{"country": j["country"], "listings": j["listings"]}
                                 for j in markets.get("jurisdictions", [])],
        }

    def __honest_numbers(self, case: dict, assessment: dict) -> dict:
        """T1's fit, wealth today, liquid wealth, wealth by year and peak pay."""
        forecast = self.__forecast
        policy = self._policy
        start, end = CaseTimeline(case).career_years()
        savings_rows = self.__future_paths.career_savings().rows(start, end)
        paths = self.__future_paths.asset_path().build(case, end, "steady")
        t1 = next(row for row in assessment["types"] if row["type_id"] == FuturePaths.BASELINE_TYPE)
        now = self.__future_paths.honest_wealth(case, savings_rows, paths, end)
        held = {b: sum(p["values"][end][b] for p in paths) for b in Band.LEVELS}
        # honest_wealth counts each asset as bought outright from savings. In cash terms, a loan
        # only took the deposit out of savings, and an asset sale paid with the sale's proceeds.
        not_from_savings = sum(asset["price_paid"] * policy["loan_to_value_max"] if asset.get("payment_method") == "loan"
                               else asset["price_paid"] if asset.get("payment_method") == "asset_sale" else 0.0
                               for asset in case.get("investments", []))
        cash = Band.as_dict(*(now[b] - held[b] + not_from_savings for b in Band.LEVELS))
        listed = {b: sum(p["values"][end][b] for asset, p in zip(case.get("investments", []), paths)
                         if self.__config.asset_category(asset["asset_type"]) == "listed_equities") for b in Band.LEVELS}
        liquid = Band.as_dict(*(cash[b] + listed[b] for b in Band.LEVELS))
        by_year = {start - 1: Band.zero()}
        for year in range(start, end + 1):
            by_year[year] = self.__future_paths.honest_wealth(case, savings_rows, paths, year)
        peak_pay = max((row["total_pay"]["typical"] for row in savings_rows), default=0.0)
        return {"t1": t1, "now": now, "cash": cash, "liquid": liquid, "by_year": by_year,
                "peak_pay": peak_pay, "paths": paths, "savings_rows": savings_rows, "start": start, "end": end,
                "models": sorted(forecast["earnings"]["assets"], key=lambda a: a["asset_index"])}

    def _forecast_checks(self, case: dict, assessment: dict | None, honest: dict | None, types: list[dict],
                        failed_step: str | None, unmodelled: list[dict] | None = None) -> list[Check]:
        """The forecast's checks in the shared shape, plus the two new ones (wealth jump, liquid wealth).
        failed_step: why the forecast stopped, in words (if it did)."""
        policy = self._policy
        if not assessment or not honest:
            return [self._check("FORECAST", "Forecast", "wealth", "skipped",
                           f"The forecast stopped at {failed_step or 'an early step'}, so the stories couldn't be tested.")]
        worth = case["claims"]["declared_net_worth"]
        t1 = honest["t1"]
        wealth = t1["wealth_now"]
        checks = []
        if not t1["fits"]:
            status, note = "failed", "It doesn't reach the declared wealth."
        elif not t1["fits_at_typical"]:
            status, note = "failed", "It only reaches the declared wealth at the optimistic edge."
        else:
            status, note = "passed", "That covers the declared wealth."
        checks.append(self._check("NET_WORTH_FIT", "Honest story (T1)", "wealth", status,
                             f"Explains {Formatter.sgd(wealth['cautious'])} to {Formatter.sgd(wealth['optimistic'])} today (typical "
                             f"{Formatter.sgd(wealth['typical'])}); declared {Formatter.sgd(worth)}. {note}"))

        assets = case.get("investments", [])
        for row in assessment["affordability"]:
            asset = assets[row["asset_index"]] if row["asset_index"] < len(assets) else {}
            checks.append(self._check(
                "AFFORDABILITY", f"{row['year']} purchase: {asset.get('asset_type', 'asset')}", "purchases",
                "passed" if row["affordable"] else "failed",
                f"Needed {Formatter.sgd(row['needed'])} ({row['payment_method'].replace('_', ' ')}); the honest story had up to "
                f"{Formatter.sgd(row['available']['optimistic'])}", group="Purchases"))
        for check in assessment["asset_checks"]:
            asset = assets[check["asset_index"]] if check["asset_index"] < len(assets) else {}
            is_value = check["rule_id"] == "ASSET_VALUE"
            checks.append(self._check(
                check["rule_id"],
                f"{asset.get('asset_type', 'Asset')}: {'value' if is_value else 'income'}", "wealth",
                "failed" if check["failed"] else "passed",
                (f"Declared {Formatter.sgd(check['declared'])}; its markets explain about {Formatter.sgd(check['expected']['typical'])} "
                 f"(up to {Formatter.sgd(check['ceiling'])})") if is_value else
                (f"Declared {Formatter.sgd(check['declared'])} a year; normal is about {Formatter.sgd(check['expected']['typical'])} "
                 f"(up to {Formatter.sgd(check['ceiling'])})"),
                group="Asset values" if is_value else "Asset income"))
        for missing in unmodelled or []:
            asset = assets[missing["asset_index"]] if missing["asset_index"] < len(assets) else {}
            checks.append(self._check("ASSET_NOT_MODELLED", f"{asset.get('asset_type', 'Asset')}: not modelled",
                                 "wealth", "skipped",
                                 f"The AI's answers about this asset failed the sense checks ({missing['error']}), so it is "
                                 f"held at its purchase price {Formatter.sgd(asset.get('price_paid'))} and its value and income "
                                 "weren't checked.", group="Asset values"))
        juris = assessment["jurisdiction"]
        checks.append(self._check("JURISDICTION", "Countries behind his wealth", "countries",
                             "failed" if juris["failed"] else "passed",
                             f"With nothing behind them: {', '.join(juris['unexplained_countries']) or 'none'}. "
                             f"On a risk list: {', '.join(juris['listed_countries']) or 'none'}."))
        for source in assessment["declared_sources"]:
            checks.append(self._check("UNQUANTIFIED_SOURCE", f"Declared source {source['source_id']}", "sources",
                                 "failed" if source["failed"] else "passed", source["detail"], group="Declared sources"))

        # NEW: could the honest path make his biggest wealth jump?
        jump, jump_years = self._jump_years(case)
        if jump is not None:
            gain, first, last = self._best_honest_jump(honest, jump_years)
            fits = jump <= gain * (1 + policy["tolerance"]["net_worth"])
            checks.append(self._check("WEALTH_JUMP", "Wealth jump vs honest path", "wealth",
                                 "passed" if fits else "failed",
                                 f"Declared jump {Formatter.sgd(jump)} over {jump_years} year(s); the honest story gains at most "
                                 f"{Formatter.sgd(gain)} in any {jump_years}-year stretch (best {first}-{last})"))
        # NEW: cash and shares the honest story leaves him today (used by "Money brought to the bank")
        liquid = honest["liquid"]
        checks.append(self._check("LIQUID_WEALTH", "Liquid wealth today", "wealth", "info",
                             f"The honest story leaves him {Formatter.sgd(liquid['cautious'])} to {Formatter.sgd(liquid['optimistic'])} "
                             f"in cash and listed shares"))
        checks.append(self._check("STABILITY", "Stability", "wealth",
                             "weak" if assessment["borderline"] else "passed",
                             "Moving every forecast 10% changes the result, so it is borderline."
                             if assessment["borderline"] else "The result holds when every forecast moves 10%."))
        for row in types:
            checks.append(self._check("CRIME_STORY", f"{row['type_id']} {row['name']}", "pattern", "info",
                                 f"{'Fits' if row['fits'] else 'Does not fit'} his money (fit {row['fit_score'] or 0:.2f}"
                                 f"{', open ' + row['route_years'] if row['route_years'] else ''})",
                                 group="Crime stories"))
        return checks
