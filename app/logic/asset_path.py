"""AssetPath: the value and income of each asset, year by year."""

from app.logic.case_timeline import CaseTimeline
from app.logic.market_model import MarketModel
from app.model.band import Band


class AssetPath:
    """Follows each asset from the year it was bought: its value moves with the markets it
    is exposed to (asked from the MarketModel) plus its own growth, and it pays an income.

    asset_models is the forecast's description of each asset (Call 2): which markets it
    follows, how strongly, its own growth and its income yield.
    """

    def __init__(self, market_model: MarketModel | None = None, asset_models: list[dict] | None = None) -> None:
        self.__market_model: MarketModel = market_model or MarketModel()
        self.__asset_models: list[dict] = sorted(asset_models or [], key=lambda model: model["asset_index"])
        self.__paths: list[dict] = []

    def build(self, record: dict, last_year: int, scenario: str = "steady",
              shocks: dict | None = None) -> list[dict]:
        """One path per asset, in the order the client listed them:
        {"values": {year: band}, "income": {year: band}} from purchase to last_year."""
        _, end = CaseTimeline(record).career_years()
        self.__paths = [self.__one_path(asset, model, end, last_year, scenario, shocks)
                        for asset, model in zip(record.get("investments", []), self.__asset_models)]
        return self.__paths

    def income_up_to(self, path: dict, year: int) -> dict:
        """Total income one asset produced up to and including a year."""
        total = Band()
        for income_year, income in path["income"].items():
            if income_year <= year:
                total = total + Band.from_dict(income)
        return total.to_dict()

    def __one_path(self, asset: dict, model: dict, end_year: int, last_year: int, scenario: str,
                   shocks: dict | None) -> dict:
        bought = int(asset["year_acquired"])
        past_yields = {row["year"]: row["yield_pct"] for row in model["income_yield_by_year"]}
        future_yield = model["future_income_yield_pct"][scenario]

        results = {}
        for level in MarketModel.RANGE_KEYS:   # one path using all the low inputs, one typical, one high
            value = float(asset["price_paid"])
            values, incomes = {}, {}
            for year in range(bought, last_year + 1):
                if year > bought:
                    change = sum(exposure["sensitivity"][level]
                                 * self.__market_model.change(exposure["market_id"], year, scenario, level, shocks)
                                 for exposure in model["exposures"])
                    value = max(value * (1 + (change + model["own_growth_pct"][level]) / 100), 0.0)
                yield_pct = past_yields.get(year, future_yield) if year <= end_year else future_yield
                values[year] = value
                incomes[year] = value * yield_pct[level] / 100
            results[level] = (values, incomes)

        years = range(bought, last_year + 1)
        return {"values": {year: Band.from_values([results[level][0][year] for level in MarketModel.RANGE_KEYS]).to_dict()
                           for year in years},
                "income": {year: Band.from_values([results[level][1][year] for level in MarketModel.RANGE_KEYS]).to_dict()
                           for year in years}}
