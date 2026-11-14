"""MarketModel: how each market moved in the past and is forecast to move."""


class MarketModel:
    """The markets behind one client's wealth (from the forecast's Call 1).

    Built once from the forecast; after that every class asks it the same question:
    how much did this market change in this year? Past years come from the recalled
    history, future years from the scenario forecast.
    """

    SCENARIOS: tuple[str, ...] = ("steady", "boom", "downturn")
    RANGE_KEYS: tuple[str, ...] = ("low", "typical", "high")   # every AI figure comes as a range

    def __init__(self, forecast: dict | None = None) -> None:
        markets = (forecast or {}).get("markets") or {}
        series = markets.get("series") or {}
        # {market_id: {year: % change or None}}
        self.__history: dict = {market_id: {row["year"]: row["change_pct"] for row in one["history"]}
                                for market_id, one in series.items()}
        # {market_id: {year: {scenario: {low, typical, high}}}}
        self.__outlook: dict = {market_id: {row["year"]: {s: row[s] for s in MarketModel.SCENARIOS}
                                            for row in one["outlook"]}
                                for market_id, one in series.items()}
        # {year: {scenario: share}} with the shares adding up to exactly 1
        self.__scenario_chances: dict = {}
        for row in markets.get("scenario_chances") or []:
            total = sum(row[s] for s in MarketModel.SCENARIOS) or 1
            self.__scenario_chances[row["year"]] = {s: row[s] / total for s in MarketModel.SCENARIOS}

    def history(self) -> dict:
        return self.__history

    def outlook(self) -> dict:
        return self.__outlook

    def scenario_chances(self) -> dict:
        return self.__scenario_chances

    def change(self, market_id: str, year: int, scenario: str, level: str = "typical",
               shocks: dict | None = None) -> float:
        """A market's % change in a year: the recalled history, otherwise the scenario forecast.
        shocks = {(market_id, year): {level: extra change}} adds an event on top."""
        past = self.__history.get(market_id, {})
        if year in past:
            change = float(past[year] or 0.0)   # a year the AI couldn't find counts as no change
        elif year in self.__outlook.get(market_id, {}):
            change = float(self.__outlook[market_id][year][scenario][level])
        else:
            change = 0.0
        if shocks and (market_id, year) in shocks:
            change += shocks[(market_id, year)][level]
        return change
