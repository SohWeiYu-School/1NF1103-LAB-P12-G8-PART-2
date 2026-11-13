"""CareerSavings: what his jobs paid and how much of it he could have saved."""

import logging

from app.model.band import Band

logger = logging.getLogger(__name__)


class CareerSavings:
    """Year by year: total pay, after tax, living costs, saved, and savings so far.

    pay is the forecast's earnings (Call 2): one yearly pay table per job. Every figure
    is worked out at three levels (a Band): cautious uses low pay with high tax and costs,
    optimistic the opposite.
    """

    def __init__(self, pay: dict | None = None) -> None:
        self.__pay: dict = pay or {}
        self.__rows: list[dict] = []

    def rows(self, start: int, end: int) -> list[dict]:
        """One row per year from start to end. A year with no pay forecast counts as no pay."""
        pay_by_year = {}
        for job in sorted(self.__pay.get("positions", []), key=lambda position: position["position_index"]):
            for row in job["yearly"]:
                pay_by_year[row["year"]] = row

        savings = {level: 0.0 for level in Band.LEVELS}
        rows = []
        zero = Band().to_dict
        for year in range(start, end + 1):
            row = pay_by_year.get(year)
            if row is None:
                logger.warning("No pay forecast for %d, counting it as a year with no pay", year)
                rows.append({"year": year, "total_pay": zero(), "after_tax": zero(), "living_costs": zero(),
                             "saved": zero(), "savings": Band(*savings.values()).to_dict()})
                continue
            parts = {"total_pay": {}, "after_tax": {}, "living_costs": {}, "saved": {}}
            for level in Band.LEVELS:
                gross = self.pay_total(row, Band.MONEY_IN[level])
                after_tax = gross * (1 - row["tax_rate_pct"][Band.MONEY_OUT[level]] / 100)
                costs = row["living_costs"][Band.MONEY_OUT[level]]
                growth = savings[level] * row["savings_return_pct"][Band.MONEY_IN[level]] / 100
                savings[level] += after_tax - costs + growth
                parts["total_pay"][level], parts["after_tax"][level] = gross, after_tax
                parts["living_costs"][level], parts["saved"][level] = costs, after_tax - costs
            rows.append({"year": year,
                         **{key: Band(*(values[level] for level in Band.LEVELS)).to_dict()
                            for key, values in parts.items()},
                         "savings": Band(*(savings[level] for level in Band.LEVELS)).to_dict()})
        self.__rows = rows
        return rows

    def pay_total(self, pay: dict, level: str) -> float:
        """Base pay + bonus + equity or profit share of one pay row, at one end of its range."""
        return pay["base_pay"][level] + pay["bonus"][level] + pay["equity_or_profit_share"][level]
