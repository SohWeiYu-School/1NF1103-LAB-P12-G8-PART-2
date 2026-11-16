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
        """forecast is the forecast's reply (or None for no markets). Only the shape this class reads is
        checked: markets.series {id: {history: [{year, change_pct}], outlook: [{year, steady, boom,
        downturn}]}} and markets.scenario_chances [{year, steady, boom, downturn}]. A wrong shape raises
        ValueError, saying which part."""
        if forecast is not None and not isinstance(forecast, dict):
            raise ValueError(f"the forecast must be a dict (or None), not {type(forecast).__name__}")
        markets = (forecast or {}).get("markets") or {}
        if not isinstance(markets, dict):
            raise ValueError("the forecast's markets must be a dict")
        series = markets.get("series") or {}
        if not isinstance(series, dict):
            raise ValueError("the forecast's market series must be a dict of markets")
        # {market_id: {year: % change or None}}
        self.__history: dict = {market_id: self.__read_rows(market_id, one, "history", ("year", "change_pct"))
                                for market_id, one in series.items()}
        # {market_id: {year: {scenario: {low, typical, high}}}}
        self.__outlook: dict = {market_id: self.__read_rows(market_id, one, "outlook",
                                                            ("year", *MarketModel.SCENARIOS))
                                for market_id, one in series.items()}
        # {year: {scenario: share}} with the shares adding up to exactly 1
        self.__scenario_chances: dict = {}
        chances = markets.get("scenario_chances") or []
        if not isinstance(chances, list):
            raise ValueError("the forecast's scenario_chances must be a list")
        for row in chances:
            self.__check_row(row, "a scenario chance", ("year", *MarketModel.SCENARIOS))
            total = sum(row[s] for s in MarketModel.SCENARIOS) or 1
            self.__scenario_chances[row["year"]] = {s: row[s] / total for s in MarketModel.SCENARIOS}

    @staticmethod
    def __check_row(row: object, what: str, keys: tuple[str, ...]) -> None:
        if not isinstance(row, dict) or any(key not in row for key in keys):
            raise ValueError(f"{what} must be a dict with {', '.join(keys)}")

    def __read_rows(self, market_id: str, one: object, part: str, keys: tuple[str, ...]) -> dict:
        """{year: change_pct} for "history", or {year: {scenario: range}} for "outlook"."""
        if not isinstance(one, dict) or not isinstance(one.get(part), list):
            raise ValueError(f"market {market_id} must be a dict with a list called {part}")
        for row in one[part]:
            self.__check_row(row, f"a {part} row of market {market_id}", keys)
        if part == "history":
            return {row["year"]: row["change_pct"] for row in one[part]}
        return {row["year"]: {s: row[s] for s in MarketModel.SCENARIOS} for row in one[part]}

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
