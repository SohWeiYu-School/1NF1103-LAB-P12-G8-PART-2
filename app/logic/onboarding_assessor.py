"""OnboardingAssessor: does what the client declared fit each person type?"""

from app.logic.case_timeline import CaseTimeline
from app.logic.future_paths import FuturePaths
from app.model.band import Band
from app.model.config import Config
from app.model.verdict import Verdict


class OnboardingAssessor:
    """Tests the client's declared figures against every person type the forecast built.

    For each type it asks: is his declared wealth within what that type would have, could
    he have paid for each purchase that year, and do his assets' values and income look
    right? It also checks the countries and the declared sources, then applies the
    onboarding rule. It is handed the FuturePaths (which knows each type's wealth), the
    policy (tolerances and weights) and the Config (country and asset names).
    """

    def __init__(self, future_paths: FuturePaths, policy: dict, config: Config) -> None:
        self.__future_paths: FuturePaths = future_paths
        self.__policy: dict = policy or {}
        self.__config: Config = config

    def _check_asset_values(self, record: dict, forecast: dict, paths: list[dict], end: int,
                           scale: float = 1.0) -> list[dict]:
        """Is each declared asset value within what its markets explain?"""
        policy = self.__policy
        tolerance = policy["tolerance"]["asset_value"]
        models = sorted(forecast["earnings"]["assets"], key=lambda a: a["asset_index"])
        findings = []
        for index, (asset, path, model) in enumerate(zip(record.get("investments", []), paths, models)):
            expected = Band.scale(path["values"][end], scale)
            ceiling = expected["optimistic"] * (1 + tolerance)
            declared = asset["current_declared_value"]
            findings.append({
                "rule_id": "ASSET_VALUE", "asset_index": index, "category": self.__config.asset_category(asset["asset_type"]),
                "failed": declared > ceiling, "declared": declared, "expected": expected, "ceiling": round(ceiling),
                "valuation_basis": model["valuation_basis"],
                "detail": f"Asset {index} ({asset['asset_type']}): declared {declared:,.0f}, "
                          f"markets explain about {expected['typical']:,.0f} (up to {ceiling:,.0f})"})
        return findings

    def _check_asset_income(self, record: dict, paths: list[dict], end: int, scale: float = 1.0) -> list[dict]:
        """Is each asset's declared income within what an asset of that value normally pays?"""
        policy = self.__policy
        tolerance = policy["tolerance"]["asset_income"]
        findings = []
        for index, (asset, path) in enumerate(zip(record.get("investments", []), paths)):
            expected = Band.scale(path["income"][end], scale)
            ceiling = expected["optimistic"] * (1 + tolerance)
            declared = asset.get("income_produced", 0)
            findings.append({
                "rule_id": "ASSET_INCOME", "asset_index": index, "category": self.__config.asset_category(asset["asset_type"]),
                "failed": declared > ceiling, "declared": declared, "expected": expected, "ceiling": round(ceiling),
                "detail": f"Asset {index}: declared income {declared:,.0f}, expected about "
                          f"{expected['typical']:,.0f} (up to {ceiling:,.0f})"})
        return findings

    def _check_affordability(self, record: dict, savings_rows: list[dict], paths: list[dict], behaviour: dict,
                            scale: float = 1.0) -> list[dict]:
        """For one type: could he pay the cash part of each purchase from what he had that year?"""
        policy = self.__policy
        loan_share = policy["loan_to_value_max"]
        savings_by_year = {row["year"]: row["savings"] for row in savings_rows}
        assets = record.get("investments", [])
        order = sorted(range(len(assets)), key=lambda i: (int(assets[i]["year_acquired"]), i))

        rows, spent = [], 0.0
        for position, index in enumerate(order):
            asset = assets[index]
            year = int(asset["year_acquired"])
            method = asset.get("payment_method", "cash")
            needed = asset["price_paid"] * (1 - loan_share) if method == "loan" else asset["price_paid"]
            available = savings_by_year.get(year, Band.zero())
            for earlier in order[:position]:
                available = Band.add(available, self.__future_paths.asset_path().income_up_to(paths[earlier], year))
            available = Band.add(available, self.__future_paths.extra_money_up_to(behaviour, year))
            available = Band.scale(Band.as_dict(*(available[b] - spent for b in Band.LEVELS)), scale)
            rows.append({"asset_index": index, "year": year, "payment_method": method, "needed": round(needed),
                         "available": available, "affordable": needed <= available["optimistic"]})
            spent += needed
        return rows

    def _check_jurisdictions(self, record: dict, forecast: dict) -> dict:
        """Countries he named with nothing behind them, and linked countries on a risk list."""
        behind = {self.__config.same_country(job.get("country", "")) for job in CaseTimeline(record).positions()}
        behind |= {self.__config.same_country(asset.get("country", "")) for asset in record.get("investments", [])}
        behind |= {self.__config.same_country(source["country"]) for source in forecast["declaration"]["claimed_sources"]}
        named = {self.__config.same_country(country) for country in record.get("claims", {}).get("wealth_countries", [])}
        unexplained = sorted(named - behind)
        listed = sorted(j["country"] for j in forecast["markets"]["jurisdictions"]
                        if j["listings"] and self.__config.same_country(j["country"]) in behind | named)
        return {"rule_id": "JURISDICTION", "failed": bool(unexplained or listed),
                "unexplained_countries": unexplained, "listed_countries": listed,
                "detail": f"Named countries with no job, asset or declared source: {unexplained or 'none'}. "
                          f"Linked countries on a risk list: {listed or 'none'}."}

    def _check_declared_sources(self, forecast: dict) -> list[dict]:
        """Declared sources with no amount and no job or asset behind them (e.g. 'some advisory work').
        Salary, bonuses and savings are explained by the career forecast, so they don't count."""
        policy = self.__policy
        explained_by_career = set(policy.get("self_explained_source_types", []))
        findings = []
        for source in forecast["declaration"]["claimed_sources"]:
            unquantified = (source["amount"] is None and source["linked_position_index"] is None
                            and source["linked_asset_index"] is None
                            and source["source_type"] not in explained_by_career)
            years = f"{source['start_year'] or '?'}-{source['end_year'] or '?'}"
            findings.append({
                "rule_id": "UNQUANTIFIED_SOURCE", "source_id": source["source_id"],
                "source_type": source["source_type"], "failed": unquantified,
                "detail": f"{source['source_id']} {source['description']} ({years}, {source['country']}): "
                          + ("no amount and no job or asset behind it" if unquantified else "backed"),
                "quote": source["quote"]})
        return findings

    def _fit_for_type(self, type_id: str, wealth_now: dict, affordability: list[dict], asset_checks: list[dict],
                     declared: float, scale: float = 1.0) -> dict:
        """How well his declared figures fit one type. Fit score 0-1."""
        policy = self.__policy
        tolerance = policy["tolerance"]["net_worth"]
        weights = policy["fit"]
        wealth = Band.scale(wealth_now, scale)
        upper = wealth["optimistic"] * (1 + tolerance)
        lower = wealth["cautious"] * (1 - tolerance)
        # Anyone can have spent money, so the as-declared type has no lower limit. A dishonest
        # type that brought in extra money would leave him at least this rich.
        net_worth_fits = declared <= upper and (type_id == FuturePaths.BASELINE_TYPE or declared >= lower)
        affordable = sum(1 for row in affordability if row["affordable"])
        affordable_share = affordable / len(affordability) if affordability else 1.0
        assets_share = (sum(1 for check in asset_checks if not check["failed"]) / len(asset_checks)
                        if asset_checks else 1.0)
        score = (weights["weight_net_worth"] * net_worth_fits + weights["weight_affordability"] * affordable_share
                 + weights["weight_assets"] * assets_share)
        return {"type_id": type_id, "fits": net_worth_fits and score >= weights["minimum_fit"],
                "fit_score": round(score, 3), "net_worth_fits": net_worth_fits, "wealth_now": wealth,
                "purchases_affordable": f"{affordable} of {len(affordability)}",
                "fits_at_typical": declared <= wealth["typical"] * (1 + policy["tolerance"]["typical_band"])}

    def _decide_onboarding(self, fits: dict, t1_affordability_breach: bool, other_failures: list[str]) -> str:
        """The onboarding rule. fits = {type_id: fit result}."""
        t1 = fits[FuturePaths.BASELINE_TYPE]
        others_fit = [t for t, result in fits.items() if t != FuturePaths.BASELINE_TYPE and result["fits"]]
        if not t1["fits"] and others_fit:
            return "SERIOUS_RISK"          # only a dishonest version explains him
        if not t1["fits"]:
            return "RISKY"                 # no forecast explains him
        if not t1["fits_at_typical"] or t1_affordability_breach:
            return "RISKY"                 # honest only at the optimistic edge, or a purchase he couldn't afford
        if other_failures:
            return "MANUAL_REVIEW"
        return "PASSED"

    def stable_outcome(self, outcome: str, outcomes_when_shifted: dict) -> tuple[str, bool]:
        """If moving the forecasts 10% changes the answer, the case is borderline and a person
        must look at it, so it goes to at least Manual Review."""
        borderline = len(set(outcomes_when_shifted.values())) > 1
        if borderline and Verdict.SEVERITY[outcome] < Verdict.SEVERITY["MANUAL_REVIEW"]:
            outcome = "MANUAL_REVIEW"
        return outcome, borderline

    def evaluate(self, record: dict, forecast: dict, savings_rows: list[dict], paths: list[dict],
                 scale: float = 1.0) -> dict:
        """Run every onboarding check with all money forecasts multiplied by `scale`."""
        _, end = CaseTimeline(record).career_years()
        declared = record["claims"]["declared_net_worth"]
        behaviours = forecast["types"]["behaviour"]
        wealth_now = self.__future_paths.type_wealth_now(record, savings_rows, paths)

        # an asset the AI couldn't describe is held at its purchase price and not checked
        unmodelled = {a["asset_index"] for a in forecast["earnings"].get("fallback_assets", [])}
        asset_values = [c for c in self._check_asset_values(record, forecast, paths, end, scale)
                        if c["asset_index"] not in unmodelled]
        asset_income = [c for c in self._check_asset_income(record, paths, end, scale)
                        if c["asset_index"] not in unmodelled]
        asset_checks = asset_values + asset_income
        affordability = {t: self._check_affordability(record, savings_rows, paths, b, scale)
                         for t, b in behaviours.items()}
        fits = {t: self._fit_for_type(t, wealth_now[t], affordability[t], asset_checks, declared, scale)
                for t in behaviours}

        jurisdiction = self._check_jurisdictions(record, forecast)
        sources = self._check_declared_sources(forecast)
        t1_breach = not all(row["affordable"] for row in affordability[FuturePaths.BASELINE_TYPE])
        other_failures = [c["rule_id"] for c in asset_checks + [jurisdiction] + sources if c["failed"]]
        outcome = self._decide_onboarding(fits, t1_breach, other_failures)
        return {"outcome": outcome, "fits": fits, "affordability": affordability,
                "asset_checks": asset_checks, "jurisdiction": jurisdiction, "sources": sources,
                "t1_affordability_breach": t1_breach}
