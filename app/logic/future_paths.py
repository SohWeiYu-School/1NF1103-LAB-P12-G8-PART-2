"""FuturePaths: the wealth of every person type, today and in each forecast year."""

from app.logic.asset_path import AssetPath
from app.logic.career_savings import CareerSavings
from app.logic.case_timeline import CaseTimeline
from app.logic.market_model import MarketModel
from app.model.band import Band


class FuturePaths:
    """Works out how rich each person type would be: the honest type (T1, wealth exactly as
    declared) from savings plus assets, and each crime type from that plus its extra money.

    It creates and owns the CareerSavings and the AssetPath it needs, and is handed the
    MarketModel they share. forecast is the finished forecast (earnings, types, events).
    """

    BASELINE_TYPE: str = "T1"     # T1 is always "his wealth came exactly as declared"

    def __init__(self, market_model: MarketModel, forecast: dict | None = None,
                 policy: dict | None = None) -> None:
        self.__forecast: dict = forecast or {}
        self.__policy: dict = policy or {}
        self.__market_model: MarketModel = market_model
        earnings = self.__forecast.get("earnings") or {}
        self.__career_savings: CareerSavings = CareerSavings(earnings)
        self.__asset_path: AssetPath = AssetPath(market_model, earnings.get("assets"))
        self.__paths: dict = {}

    def career_savings(self) -> CareerSavings:
        return self.__career_savings

    def asset_path(self) -> AssetPath:
        return self.__asset_path

    def extra_money_up_to(self, behaviour: dict, year: int) -> dict:
        """A type's extra money (Call 3) added up to and including a year."""
        total = Band.zero()
        for row in behaviour["extra_money_history"]:
            if row["year"] <= year:
                total = Band.add(total, Band.from_ai(row["amount"]))
        return total

    def honest_wealth(self, record: dict, savings_rows: list[dict], paths: list[dict], year: int) -> dict:
        """Wealth of the as-declared version: savings + gain on each asset + its income so far."""
        savings = next(row["savings"] for row in savings_rows if row["year"] == year)
        total = dict(savings)
        for asset, path in zip(record.get("investments", []), paths):
            if int(asset["year_acquired"]) > year:
                continue
            gain = Band.as_dict(*(path["values"][year][b] - asset["price_paid"] for b in Band.LEVELS))
            total = Band.add(total, Band.add(gain, self.__asset_path.income_up_to(path, year)))
        return total

    def type_wealth_now(self, record: dict, savings_rows: list[dict], paths: list[dict]) -> dict:
        """{type_id: wealth band today} = honest wealth + that type's extra money so far."""
        forecast = self.__forecast
        _, end = CaseTimeline(record).career_years()
        honest = self.honest_wealth(record, savings_rows, paths, end)
        return {type_id: Band.add(honest, self.extra_money_up_to(behaviour, end))
                for type_id, behaviour in forecast["types"]["behaviour"].items()}

    def forward_paths(self, record: dict, savings_rows: list[dict], scenario: str,
                      shocks: dict | None = None, event_changes: dict | None = None) -> dict:
        """
        Wealth of every type for the current year and each forecast year in one scenario.
        event_changes = {type_id: (year, extra money change)} adds an event reaction.
        """
        forecast = self.__forecast
        _, end = CaseTimeline(record).career_years()
        years = CaseTimeline(record).future_years()
        paths = self.__asset_path.build(record, years[-1], scenario, shocks)
        future_pay = {row["year"]: row for row in forecast["earnings"]["future_pay"]["yearly"]}

        honest_now = self.honest_wealth(record, savings_rows, paths, end)
        cash = {b: honest_now[b] - sum(p["values"][end][b] for p in paths) for b in Band.LEVELS}
        honest = {end: honest_now}
        for year in years:
            row = future_pay[year]
            for b in Band.LEVELS:
                income = self.__career_savings.pay_total(row[scenario], Band.MONEY_IN[b]) + sum(p["income"][year][b] for p in paths)
                after_tax = income * (1 - row["tax_rate_pct"][Band.MONEY_OUT[b]] / 100)
                growth = cash[b] * row["savings_return_pct"][Band.MONEY_IN[b]] / 100
                cash[b] += after_tax - row["living_costs"][Band.MONEY_OUT[b]] + growth
            honest[year] = Band.as_dict(*(cash[b] + sum(p["values"][year][b] for p in paths) for b in Band.LEVELS))

        result = {}
        for type_id, behaviour in forecast["types"]["behaviour"].items():
            extra = self.extra_money_up_to(behaviour, end)
            forecast_rows = {row["year"]: row for row in behaviour["extra_money_forecast"]}
            points = {end: Band.add(honest[end], extra)}
            for year in years:
                extra = Band.add(extra, Band.from_ai(forecast_rows[year][scenario]))
                if event_changes and type_id in event_changes and event_changes[type_id][0] == year:
                    extra = Band.add(extra, Band.from_ai(event_changes[type_id][1]))
                points[year] = Band.add(honest[year], extra)
            result[type_id] = points
        return result

    def expected_paths(self, record: dict, savings_rows: list[dict]) -> dict:
        """Each type's wealth path weighted by the AI's chance of each scenario."""
        forecast = self.__forecast
        chances = self.__market_model.scenario_chances()
        by_scenario = {s: self.forward_paths(record, savings_rows, s) for s in MarketModel.SCENARIOS}
        expected = {}
        for type_id in forecast["types"]["behaviour"]:
            expected[type_id] = {}
            for year in by_scenario["steady"][type_id]:
                weights = chances.get(year, {"steady": 1.0, "boom": 0.0, "downturn": 0.0})
                expected[type_id][year] = Band.as_dict(*(sum(weights[s] * by_scenario[s][type_id][year][b]
                                                     for s in MarketModel.SCENARIOS) for b in Band.LEVELS))
        return expected

    def event_impacts(self, record: dict, savings_rows: list[dict]) -> list[dict]:
        """For each event and type: change in 2030 wealth if it happens, and weighted by its chance."""
        forecast = self.__forecast
        last_year = CaseTimeline(record).future_years()[-1]
        without = self.forward_paths(record, savings_rows, "steady")
        rows = []
        for event in forecast["events"]["events"]:
            shocks = {(s["market_id"], event["year"]): s["change_pct"] for s in event["shocks"]}
            changes = {}
            for type_id, reactions in forecast["events"]["reactions"].items():
                for reaction in reactions["reactions"]:
                    if reaction["event_id"] == event["event_id"]:
                        changes[type_id] = (event["year"], reaction["extra_money_change"])
            with_event = self.forward_paths(record, savings_rows, "steady", shocks, changes)
            chance = event["probability_pct"]["typical"] / 100
            for type_id in with_event:
                impact = with_event[type_id][last_year]["typical"] - without[type_id][last_year]["typical"]
                rows.append({"event_id": event["event_id"], "event": event["name"], "year": event["year"],
                             "type_id": type_id, "impact": round(impact), "chance": round(chance, 3),
                             "weighted_impact": round(impact * chance)})
        return rows

    def divergence_years(self, paths: dict) -> list[dict]:
        """First forecast year each type's range stops overlapping the as-declared type's range."""
        baseline = paths[FuturePaths.BASELINE_TYPE]
        rows = []
        for type_id, points in paths.items():
            if type_id == FuturePaths.BASELINE_TYPE:
                continue
            first = None
            for year in sorted(points)[1:]:
                a, b = baseline[year], points[year]
                if a["cautious"] > b["optimistic"] or b["cautious"] > a["optimistic"]:
                    first = year
                    break
            rows.append({"type_id": type_id, "distinguishable_from": first})
        return rows

    def monitoring_ranges(self, year: int) -> dict:
        """What normal account activity looks like next year, from the as-declared type's signals."""
        forecast = self.__forecast
        policy = self.__policy
        tolerance = policy["tolerance"]["signal_amount"]
        ranges = {}
        for signal in forecast["types"]["behaviour"][FuturePaths.BASELINE_TYPE]["signals"]:
            if not signal["first_year"] <= year <= signal["last_year"]:
                continue
            code = signal["signal_code"]
            count_max = round(signal["count_per_year"]["high"] * (1 + tolerance), 2)
            amount_max = round(signal["amount_per_year"]["high"] * (1 + tolerance))
            if code in ranges:
                count_max = max(count_max, ranges[code]["count_max"])
                amount_max = max(amount_max, ranges[code]["amount_max"])
            ranges[code] = {"count_max": count_max, "amount_max": amount_max}
        return ranges
