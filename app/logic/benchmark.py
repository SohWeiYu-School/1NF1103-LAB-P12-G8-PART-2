"""Benchmark: is the client's wealth in line with people who have the same career?"""

import re

from app.logic.case_timeline import CaseTimeline
from app.logic.risk_analysis import RiskAnalysis
from app.logic.formatter import Formatter
from app.logic.market_model import MarketModel
from app.model.check import Check
from app.model.config import Config
from app.model.declaration import Declaration


class Benchmark(RiskAnalysis):
    """The benchmark feature. It compares what the client declared with what the AI says a
    typical person with his career would have: total wealth, liquidity, the asset mix, the
    speed of his biggest wealth jump, his counterparties and his countries.

    Each result is then cross-checked against the forecast: a difference the honest
    forecast explains is marked "explained" and does not count towards the verdict.
    """

    LIMITS = {
        "total_wealth": 3,
        "liquidity": 2,
        "composition": 40,
        "velocity": 2,
        "counterparties": 1,
        "jurisdiction": 1
    }
    _COMPOSITION_PARTS = [
        ("COMPOSITION_PROPERTY",  "property",        "expected_property",        "Property"),
        ("COMPOSITION_EQUITIES",  "listed_equities",  "expected_listed_equities", "Listed equities"),
        ("COMPOSITION_BUSINESS",  "private_business", "expected_private_business","Private business"),
        ("COMPOSITION_CASH",      "cash",             "expected_cash",            "Cash"),
    ]
    BENCHMARK_LABELS = {
        "TOTAL_WEALTH": "Total wealth", "UNEXPLAINED_GAP": "Unexplained wealth",
        "VELOCITY": "Wealth growth speed", "JUMP_VS_ECONOMY": "Wealth jump vs economy",
        "LIQUIDITY": "Liquidity", "AUM_FUNDING": "Money brought to the bank",
        "COMPOSITION_PROPERTY": "Asset mix: property", "COMPOSITION_EQUITIES": "Asset mix: listed shares",
        "COMPOSITION_BUSINESS": "Asset mix: private business", "COMPOSITION_CASH": "Asset mix: cash",
        "COUNTERPARTIES": "Counterparties", "JURISDICTION": "Countries", "PEP_STATUS": "PEP status",
    }
    FORECAST_DERIVED = ("UNEXPLAINED_GAP", "PEP_STATUS", "PEER_BENCHMARK")
    COMPOSITION_RULES = {"COMPOSITION_PROPERTY": "property", "COMPOSITION_EQUITIES": "listed_equities",
                         "COMPOSITION_BUSINESS": "private_business", "COMPOSITION_CASH": "cash"}

    NAME: str = "benchmark"

    def __init__(self, policy: dict | None = None, config: Config | None = None) -> None:
        super().__init__(policy)
        self.__config: Config = config or Config(self._policy, {})

    def run(self, case: dict, ai_data: dict) -> dict:
        """Run the benchmark rules. ai_data is {"benchmark_input", "benchmark_ai"}.
        Returns {} if the AI gave no benchmark."""
        self._results = self._run_rules(ai_data.get("benchmark_input"), ai_data.get("benchmark_ai")) or {}
        return self._results

    def checks(self, context: dict) -> list[Check]:
        """The benchmark's findings. context holds case, bench_input, ai_data, findings, honest,
        assessment, declaration (the forecast's Declaration), markets and types."""
        return self._benchmark_checks(
            context["case"], context.get("bench_input"), context.get("ai_data"), context.get("findings"),
            context.get("honest"), context.get("assessment"), context.get("declaration"),
            context.get("markets"), context.get("types") or [])

    def _market_history(self, forecast: dict) -> dict:
        return MarketModel(forecast).history()

    def _total_wealth(self, client_data, ai_data):

        declared = client_data["declared_net_worth"]
        expected = ai_data["expected_wealth"]

        result1 = declared / expected

        return result1

    def _liquidity(self, client_data, ai_data):

        declared = client_data["listed_equities"] + client_data["cash"]
        expected = ai_data["expected_liquidity"]

        result2 = declared / expected

        return result2

    def _composition(self, client_data, ai_data):
        results = []
        for rule_id, client_key, ai_key, label in Benchmark._COMPOSITION_PARTS:
            declared = client_data[client_key]
            expected = ai_data[ai_key]
            diff = abs(declared - expected)
            results.append({"rule_id": rule_id, "failed": diff > Benchmark.LIMITS["composition"],
                            "detail": f"{label}: declared {declared}%, expected {expected}%, diff {diff}%"})
        return results

    def _velocity(self, client_data, ai_data):
        jump = client_data.get("biggest_wealth_jump")
        years = client_data.get("wealth_jump_years")
        expected = ai_data.get("expected_velocity")
        if jump is None or years is None or years <= 0 or expected is None or expected <= 0:
            return None, None          # (ratio, per_year) — None means skipped
        per_year = jump / years
        return per_year / expected, per_year

    def _counterparties(self, declared, expected):
        unknown = []

        for item in declared:
            if item not in expected:
                unknown.append(item)

        return unknown

    def _clean_country(self, country):
        if country == "SG":
            return "Singapore"
        elif country == "MY":
            return "Malaysia"
        elif country == "ID":
            return "Indonesia"
        elif country == "HK":
            return "Hong Kong"
        elif country == "AE":
            return "United Arab Emirates"

        return country

    def _jurisdiction(self, declared, expected):
        unknown = []

        for country in declared:
            country = self._clean_country(country)

            if country not in expected:
                unknown.append(country)

        return unknown

    def _run_rules(self, client_data: dict, ai_data: dict):
        """Run all benchmark checks for a client."""
        policy = self._policy

        if ai_data is None:
            return None

        findings = []

        # 1. TOTAL WEALTH CHECK
        result1 = self._total_wealth(client_data, ai_data)
        findings.append({"rule_id": "TOTAL_WEALTH", "failed": result1 > Benchmark.LIMITS["total_wealth"],
                         "detail": f"Declared {client_data['declared_net_worth']:,}, expected {ai_data['expected_wealth']:,}, ratio {round(result1, 2)}"})

        # 2. LIQUIDITY CHECK
        result2 = self._liquidity(client_data, ai_data)
        findings.append({"rule_id": "LIQUIDITY", "failed": result2 > Benchmark.LIMITS["liquidity"],
                         "detail": f"Declared {client_data['listed_equities'] + client_data['cash']}%, expected {ai_data['expected_liquidity']}%, ratio {round(result2, 2)}"})

        # 3. ASSET COMPOSITION CHECK
        findings += self._composition(client_data, ai_data)

        # 4. VELOCITY CHECK
        ratio, per_year = self._velocity(client_data, ai_data)
        if ratio is None:
            findings.append({"rule_id": "VELOCITY", "failed": False,
                             "detail": "Skipped — missing or invalid wealth timeline data"})
        else:
            findings.append({"rule_id": "VELOCITY", "failed": ratio > Benchmark.LIMITS["velocity"],
                             "detail": f"Actual velocity {round(per_year, 2)}, expected {ai_data.get('expected_velocity')}, ratio {round(ratio, 2)}"})

        # 5. COUNTERPARTIES CHECK — service providers (banks, law firms, etc.) are excluded
        declared_counterparties = client_data.get("declared_counterparties", [])
        if policy:
            words = policy.get("verdict", {}).get("service_provider_words", [])
            declared_counterparties = [c for c in declared_counterparties
                                       if not any(re.search(rf"\b{re.escape(w)}\b", c.lower()) for w in words)]
        expected_counterparties = ai_data.get("expected_counterparties", [])
        unknown_counterparties = self._counterparties(declared_counterparties, expected_counterparties)
        findings.append({"rule_id": "COUNTERPARTIES", "failed": len(unknown_counterparties) > Benchmark.LIMITS["counterparties"],
                         "detail": f"Unknown counterparties: {unknown_counterparties or 'none'}"})

        # 6. JURISDICTION CHECK
        declared_countries = client_data.get("declared_countries", [])
        expected_countries = ai_data.get("expected_jurisdiction", [])
        unknown_countries = self._jurisdiction(declared_countries, expected_countries)
        findings.append({"rule_id": "JURISDICTION", "failed": len(unknown_countries) > Benchmark.LIMITS["jurisdiction"],
                         "detail": f"Unknown countries: {unknown_countries or 'none'}"})

        return {"findings": findings}

    def _market_growth(self, history: dict, market_id: str, first: int, last: int) -> float:
        """% a market grew from the end of `first` to the end of `last` (unknown years count as 0)."""
        level = 1.0
        for year in range(first + 1, last + 1):
            level *= 1 + float(history.get(market_id, {}).get(year) or 0.0) / 100
        return (level - 1) * 100

    def _best_market_stretch(self, markets: dict | None, years: int, start: int, end: int) -> tuple[float, int, int] | None:
        """The best `years`-long stretch of his markets during his career: (average % a year, first, last)."""
        if not markets or not markets.get("series"):
            return None
        changes = {}
        for series in markets["series"].values():
            for row in series.get("history", []):
                if row.get("change_pct") is not None:
                    changes.setdefault(row["year"], []).append(row["change_pct"])
        yearly = {y: sum(v) / len(v) for y, v in changes.items() if start <= y <= end}
        if not yearly:
            return None
        years = max(1, min(years, end - start + 1))
        best = None
        for last in range(start + years - 1, end + 1):
            window = [yearly.get(y, 0.0) for y in range(last - years + 1, last + 1)]
            average = sum(window) / years
            if best is None or average > best[0]:
                best = (round(average, 1), last - years + 1, last)
        return best

    def is_pep(self, case: dict) -> bool:
        policy = self._policy
        status = str(case.get("claims", {}).get("pep_status") or "").strip().lower()
        return status not in policy["verdict"]["no_pep_values"]

    def _benchmark_checks(self, case: dict, bench_input: dict | None, ai_data: dict | None, findings: list[dict] | None,
                         honest: dict | None, assessment: dict | None, declaration: Declaration | None,
                         markets: dict | None, types: list[dict]) -> list[Check]:
        """The peer benchmark's checks, each cross-checked against the forecast: a failure the
        honest forecast explains is marked "explained" and doesn't count towards the verdict."""
        policy = self._policy
        settings = policy["verdict"]
        claims = case.get("claims", {})
        worth = claims.get("declared_net_worth") or 0
        split = claims.get("asset_composition") or {}
        liquid_share = (split.get("listed_equities") or 0) + (split.get("cash") or 0)
        declared_liquid = liquid_share * worth
        t1 = honest["t1"] if honest else None
        checks = []
        by_rule = {f["rule_id"]: f for f in findings or []}
        not_checked = "Couldn't be cross-checked: the forecast didn't finish."

        def failed_or_explained(failed: bool, explained: bool | None, yes: str, no: str) -> tuple[str, str]:
            if not failed:
                return "passed", ""
            if explained is None:
                return "failed", not_checked
            return ("explained", yes) if explained else ("failed", no)

        if findings is None:
            checks.append(self._check("PEER_BENCHMARK", "Peer benchmark", "wealth", "skipped",
                                 "The peer benchmark couldn't run, so declared figures weren't compared with peers."))

        # Total wealth vs peers
        if "TOTAL_WEALTH" in by_rule:
            expected = ai_data["expected_wealth"]
            ratio = worth / expected if expected else 0
            status, why = failed_or_explained(
                by_rule["TOTAL_WEALTH"]["failed"], t1["net_worth_fits"] if t1 else None,
                f"Explained: the honest forecast reaches {Formatter.sgd(t1['wealth_now']['cautious'])} to "
                f"{Formatter.sgd(t1['wealth_now']['optimistic'])}, which "
                + ("covers it." if worth <= t1["wealth_now"]["optimistic"] else
                   f"is within the {policy['tolerance']['net_worth']:.0%} tolerance.") if t1 else "",
                f"Not explained: the honest forecast reaches at most {Formatter.sgd(t1['wealth_now']['optimistic'])}." if t1 else "")
            checks.append(self._check("TOTAL_WEALTH", Benchmark.BENCHMARK_LABELS["TOTAL_WEALTH"], "wealth", status,
                                 f"Declared {Formatter.sgd(worth)} vs about {Formatter.sgd(expected)} for peers in this economy "
                                 f"({ratio:.1f}x; flagged above {Benchmark.LIMITS['total_wealth']}x)", why))

        # NEW: how much the honest story can't explain, in money and in years of his pay
        if honest:
            reach = t1["wealth_now"]["optimistic"]
            gap = worth - reach
            over = worth > reach * (1 + policy["tolerance"]["net_worth"])
            years = gap / honest["peak_pay"] if honest["peak_pay"] > 0 else None
            if over:
                detail = (f"{Formatter.sgd(gap)} of the declared {Formatter.sgd(worth)} is beyond the most the honest story reaches "
                          f"({Formatter.sgd(reach)})" + (f": about {years:.0f} years of his peak pay "
                                                f"({Formatter.sgd(honest['peak_pay'])} a year)" if years else ""))
            elif worth > reach:
                detail = (f"The honest story reaches up to {Formatter.sgd(reach)}, within the "
                          f"{policy['tolerance']['net_worth']:.0%} tolerance of the declared {Formatter.sgd(worth)}.")
            else:
                detail = f"The honest story reaches up to {Formatter.sgd(reach)}, which covers the declared {Formatter.sgd(worth)}."
            checks.append(self._check("UNEXPLAINED_GAP", Benchmark.BENCHMARK_LABELS["UNEXPLAINED_GAP"], "wealth",
                                 "failed" if over else "passed", detail))
        else:
            checks.append(self._check("UNEXPLAINED_GAP", Benchmark.BENCHMARK_LABELS["UNEXPLAINED_GAP"], "wealth",
                                 "skipped", "Needs the honest forecast, which didn't finish."))

        # Wealth growth speed vs peers, cross-checked with the honest path
        jump, jump_years = self._jump_years(case)
        velocity_failed = velocity_status = None
        if "VELOCITY" in by_rule:
            finding = by_rule["VELOCITY"]
            if finding["detail"].startswith("Skipped") or jump is None:
                checks.append(self._check("VELOCITY", Benchmark.BENCHMARK_LABELS["VELOCITY"], "wealth", "skipped",
                                     "No biggest wealth jump was recorded, so growth speed wasn't checked."))
            else:
                velocity_failed = finding["failed"]
                expected = ai_data["expected_velocity"]
                per_year = jump / jump_years
                explained = None
                if honest:
                    best = self._best_honest_jump(honest, jump_years)
                    explained = jump <= best[0] * (1 + policy["tolerance"]["net_worth"])
                status, why = failed_or_explained(
                    velocity_failed, explained,
                    f"Explained: the honest story could gain up to {Formatter.sgd(best[0])} in {best[1]}-{best[2]}."
                    if honest else "",
                    f"Not explained: the honest story gains at most {Formatter.sgd(best[0])} in any {jump_years}-year "
                    f"stretch (best {best[1]}-{best[2]})." if honest else "")
                velocity_status = status
                checks.append(self._check("VELOCITY", Benchmark.BENCHMARK_LABELS["VELOCITY"], "wealth", status,
                                     f"Biggest jump {Formatter.sgd(jump)} over {jump_years} year(s) = {Formatter.sgd(per_year)} a year vs "
                                     f"about {Formatter.sgd(expected)} a year for peers ({per_year / expected if expected else 0:.1f}x; "
                                     f"flagged above {Benchmark.LIMITS['velocity']}x)", why))

        # NEW: was the economy strong enough for such a jump?
        if jump is None:
            checks.append(self._check("JUMP_VS_ECONOMY", Benchmark.BENCHMARK_LABELS["JUMP_VS_ECONOMY"], "wealth",
                                 "skipped", "No biggest wealth jump was recorded."))
        else:
            start, end = CaseTimeline(case).career_years()
            best = self._best_market_stretch(markets, jump_years, start, end)
            if best is None or velocity_failed is None:
                checks.append(self._check("JUMP_VS_ECONOMY", Benchmark.BENCHMARK_LABELS["JUMP_VS_ECONOMY"], "wealth",
                                     "skipped", "Needs the economy forecast and the peer growth speed."))
            else:
                average, first, last = best
                boom = settings["booming_market_pct"]
                note = "The jump's own years aren't recorded, so his markets' best stretch is used."
                if not velocity_failed:
                    status, detail = "passed", (f"Within the peer range. His markets' best {jump_years}-year stretch "
                                                f"was {first}-{last} ({average:+.1f}% a year).")
                elif average >= boom:
                    status, detail = "explained", (f"Faster than peers, but his markets boomed in {first}-{last} "
                                                   f"({average:+.1f}% a year), which can explain it. {note}")
                elif velocity_status == "explained":
                    status, detail = "explained", (f"Faster than peers and his markets never boomed (best {jump_years}-"
                                                   f"year stretch {first}-{last}, {average:+.1f}% a year), but the "
                                                   f"honest story's own growth explains the jump (see growth speed).")
                else:
                    status, detail = "failed", (f"Faster than peers, and his markets never boomed: their best "
                                                f"{jump_years}-year stretch was {first}-{last} at {average:+.1f}% a year "
                                                f"(a boom is {boom:g}% or more). {note}")
                checks.append(self._check("JUMP_VS_ECONOMY", Benchmark.BENCHMARK_LABELS["JUMP_VS_ECONOMY"], "wealth",
                                     status, detail))

        # Liquidity vs peers, cross-checked with the honest story's cash and shares
        if "LIQUIDITY" in by_rule:
            declared_pct = bench_input["listed_equities"] + bench_input["cash"]
            explained = (declared_liquid <= honest["liquid"]["optimistic"] * (1 + settings["aum_tolerance"])
                         if honest else None)
            status, why = failed_or_explained(
                by_rule["LIQUIDITY"]["failed"], explained,
                f"Explained: the honest story leaves him up to {Formatter.sgd(honest['liquid']['optimistic'])} in cash and "
                f"shares, enough for the {Formatter.sgd(declared_liquid)} he declares." if honest else "",
                f"Not explained: he declares {Formatter.sgd(declared_liquid)} in cash and shares; the honest story leaves "
                f"at most {Formatter.sgd(honest['liquid']['optimistic'])}." if honest else "")
            checks.append(self._check("LIQUIDITY", Benchmark.BENCHMARK_LABELS["LIQUIDITY"], "wealth", status,
                                 f"{declared_pct}% of his wealth in cash and listed shares vs about "
                                 f"{ai_data['expected_liquidity']:g}% for peers ("
                                 + (f"{declared_pct / ai_data['expected_liquidity']:.1f}x; " if ai_data['expected_liquidity'] else "")
                                 + f"flagged above {Benchmark.LIMITS['liquidity']}x)", why))

        # NEW: can he fund the money he says he'll bring to the bank?
        aum = claims.get("expected_aum")
        if isinstance(aum, (int, float)) and aum > 0:
            tolerance = 1 + settings["aum_tolerance"]
            short_own = aum > declared_liquid * tolerance
            short_honest = honest is not None and aum > honest["liquid"]["optimistic"] * tolerance
            detail = f"Plans to bring {Formatter.sgd(aum)}; by his own split he holds {Formatter.sgd(declared_liquid)} in cash and shares"
            if honest:
                detail += f", and the honest story leaves him up to {Formatter.sgd(honest['liquid']['optimistic'])}"
            checks.append(self._check("AUM_FUNDING", Benchmark.BENCHMARK_LABELS["AUM_FUNDING"], "wealth",
                                 "failed" if short_own or short_honest else "passed", detail + "."))
            checks[-1].set_extra("independent", short_own)   # short by his OWN figures, not only by the forecast

        # Asset mix vs peers, cross-checked with his listed assets and their markets
        history = self._market_history({"markets": markets}) if markets and markets.get("series") else {}
        asset_checks = {c["asset_index"]: c for c in (assessment or {}).get("asset_checks", [])
                        if c["rule_id"] == "ASSET_VALUE"}
        models = {m["asset_index"]: m for m in (honest or {}).get("models", [])}
        for rule, key in Benchmark.COMPOSITION_RULES.items():
            if rule not in by_rule:
                continue
            declared_pct = bench_input[key]
            expected_pct = ai_data[f"expected_{key}"]
            declared_amount = (split.get(key) or 0) * worth
            explained, yes, no = None, "", ""
            if honest:
                if key == "cash":
                    reach = honest["cash"]["optimistic"]
                    explained = 0 < declared_amount <= reach * (1 + settings["composition_tolerance"])
                    yes = f"Explained: the honest story leaves him up to {Formatter.sgd(reach)} in cash."
                    no = f"Not explained: the honest story leaves him at most {Formatter.sgd(reach)} in cash."
                else:
                    indexes = [i for i, a in enumerate(case.get("investments", []))
                               if self.__config.asset_category(a["asset_type"]) == key]
                    listed = sum(case["investments"][i]["current_declared_value"] for i in indexes)
                    values_ok = all(not asset_checks.get(i, {}).get("failed") for i in indexes)
                    close = listed > 0 and abs(listed - declared_amount) <= settings["composition_tolerance"] * max(
                        listed, declared_amount)
                    explained = bool(indexes) and close and values_ok
                    market_note = ""
                    if indexes and history:
                        first = case["investments"][indexes[0]]
                        model = models.get(indexes[0])
                        if model and model["exposures"]:
                            top = max(model["exposures"], key=lambda e: e["sensitivity"]["typical"])
                            growth = self._market_growth(history, top["market_id"], int(first["year_acquired"]), honest["end"])
                            market_note = f" ({top['market_id']} {growth:+.0f}% since {first['year_acquired']})"
                    yes = (f"Explained: his {key.replace('_', ' ')} assets ({Formatter.sgd(listed)}) match that share and their "
                           f"markets explain their values{market_note}.")
                    no = ("Not explained: " + (f"his {key.replace('_', ' ')} assets add up to {Formatter.sgd(listed)}, not "
                                               f"{Formatter.sgd(declared_amount)}" if indexes else
                                               f"no {key.replace('_', ' ')} assets are listed")
                          + ("" if values_ok else ", and their declared values are above what their markets explain")
                          + ".")
            status, why = failed_or_explained(by_rule[rule]["failed"], explained, yes, no)
            checks.append(self._check(rule, Benchmark.BENCHMARK_LABELS[rule], "wealth", status,
                                 f"Declared {declared_pct}% vs about {expected_pct:g}% for peers "
                                 f"(off by {abs(declared_pct - expected_pct):g} points; flagged above "
                                 f"{Benchmark.LIMITS['composition']})", why, group="Asset mix"))

        # Counterparties not expected for his career, cross-checked with his declaration
        if "COUNTERPARTIES" in by_rule:
            words = settings["service_provider_words"]
            providers = [c for c in bench_input.get("declared_counterparties", [])
                         if any(re.search(rf"\b{re.escape(w)}\b", c.lower()) for w in words)]
            # Service providers were already excluded by run_benchmark — unknown comes from its finding
            unknown = self._counterparties([c for c in bench_input.get("declared_counterparties", [])
                                                if c not in providers], ai_data.get("expected_counterparties", []))
            sources = declaration.sources() if declaration is not None else []

            def backed(name: str) -> bool:
                low = name.lower()
                return any((source.linked_position_index is not None or source.linked_asset_index is not None)
                           and source.counterparty
                           and (low in source.counterparty.lower() or source.counterparty.lower() in low)
                           for source in sources)
            explained = all(backed(name) for name in unknown) if declaration is not None else None
            status, why = failed_or_explained(
                by_rule["COUNTERPARTIES"]["failed"], explained,
                "Explained: each one is named in his declaration as linked to one of his jobs or assets.",
                "Not explained: not every one is linked to a job or asset in his declaration.")
            checks.append(self._check("COUNTERPARTIES", Benchmark.BENCHMARK_LABELS["COUNTERPARTIES"], "people", status,
                                 ((f"{len(unknown)} not usual for his career: {', '.join(unknown)} "
                                   f"(flagged when more than {Benchmark.LIMITS['counterparties']})") if unknown
                                  else "All usual for his career.")
                                 + (f" Banks, brokers and law firms are left out: {', '.join(providers)}." if providers else ""),
                                 why))

        # Countries not expected for his career, cross-checked with the forecast's countries
        if "JURISDICTION" in by_rule:
            unknown = self._jurisdiction(bench_input.get("declared_countries", []),
                                             ai_data.get("expected_jurisdiction", []))
            explained = None
            if assessment:
                juris = assessment["jurisdiction"]
                flagged = {self.__config.same_country(c) for c in juris["unexplained_countries"] + juris["listed_countries"]}
                explained = not any(self.__config.same_country(c) in flagged for c in unknown)
            status, why = failed_or_explained(
                by_rule["JURISDICTION"]["failed"], explained,
                "Explained: each has a job, asset or declared source behind it, and none is on a risk list.",
                "Not explained: at least one has nothing behind it or is on a risk list.")
            checks.append(self._check("JURISDICTION", Benchmark.BENCHMARK_LABELS["JURISDICTION"], "countries", status,
                                 (f"{len(unknown)} not usual for his career: {', '.join(unknown)} "
                                  f"(flagged when more than {Benchmark.LIMITS['jurisdiction']})") if unknown
                                 else "All usual for his career.", why))

        # NEW: PEP status (a PEP always needs a person to look, and a public-office crime story matters more)
        status_text = str(claims.get("pep_status") or "None")
        pep = self.is_pep(case)
        pep_types = [t for t in types if t["fits"] and t["category"] in settings["pep_crime_categories"]]
        checks.append(self._check(
            "PEP_STATUS", Benchmark.BENCHMARK_LABELS["PEP_STATUS"], "pattern", "failed" if pep else "passed",
            f"{status_text}" + (" - a politically exposed person needs enhanced due diligence" if pep else " - not a PEP"),
            ("A public-office crime story also fits his money: "
             + "; ".join(f"{t['type_id']} {t['name']}" for t in pep_types) + ".") if pep and pep_types else ""))
        # Which failures are evidence of their own (from peers or his own figures), rather than the
        # forecast's honest story seen again: only these can be the "second feature" that agrees.
        for item in checks:
            if item.extra("independent") is None:
                item.set_extra("independent", item.check not in Benchmark.FORECAST_DERIVED)
            item.set_extra("optional", item.status == "skipped" and item.detail.startswith("No biggest wealth jump"))
        return checks
