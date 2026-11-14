"""Formatter: small text and date helpers with nothing to store."""

import datetime


class Formatter:
    """A utility: how money and review dates are written. It holds no data, so its
    methods are static and are called on the class."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def sgd(value: float) -> str:
        """12345.6 -> 'S$12,346'. Anything that is not a number -> 'n/a'."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "n/a"
        return f"-S${-value:,.0f}" if value < 0 else f"S${value:,.0f}"

    @staticmethod
    def add_months(date_text: str, months: int) -> str:
        """'2026-09-24' + 3 months = '2026-12-24' (the day is clipped to the month's length)."""
        date = datetime.date.fromisoformat(date_text)
        month_index = date.month - 1 + months
        year, month = date.year + month_index // 12, month_index % 12 + 1
        first_of_next = datetime.date(year + month // 12, month % 12 + 1, 1)
        last_day = (first_of_next - datetime.timedelta(days=1)).day
        return datetime.date(year, month, min(date.day, last_day)).isoformat()

    @staticmethod
    def percent(value: float) -> str:
        """0.256 -> '25.6%'."""
        try:
            return f"{value * 100:.1f}%"
        except Exception:
            print("could not format percent")
            return "0.0%"
