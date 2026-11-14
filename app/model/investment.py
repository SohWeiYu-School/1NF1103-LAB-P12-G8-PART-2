"""Investment: one asset the client holds or held."""


class Investment:
    """One asset: what it is, where it is, what was paid and what it is declared to be worth."""

    def __init__(self, asset_type: str = "", country: str = "", year_acquired: int | None = None, price_paid: float | None = None,
                 current_declared_value: float | None = None, payment_method: str | None = None,
                 income_produced: float | None = None, extra: dict | None = None) -> None:
        self.__check_year(year_acquired)
        self.__check_amount(price_paid, allow_zero=True)
        self.__check_amount(current_declared_value, allow_zero=True)
        self.__check_amount(income_produced, allow_zero=True)
        self.__check_payment_method(payment_method)
        self.__asset_type: str = asset_type
        self.__country: str = country
        self.__year_acquired: int | None = year_acquired
        self.__price_paid: float | None = price_paid
        self.__current_declared_value: float | None = current_declared_value
        self.__income_produced: float | None = income_produced
        self.__payment_method: str | None = payment_method
        # Details only some screens ask for (year sold, sale price, currency); kept so nothing is lost.
        self.__extra: dict = dict(extra or {})

    @property
    def asset_type(self) -> str:
        return self.__asset_type

    @property
    def country(self) -> str:
        return self.__country

    @property
    def year_acquired(self) -> int | None:
        return self.__year_acquired

    @year_acquired.setter
    def year_acquired(self, year: int | None) -> None:
        self.__check_year(year)
        self.__year_acquired = year

    @property
    def price_paid(self) -> float | None:
        return self.__price_paid

    @price_paid.setter
    def price_paid(self, value: float | None) -> None:
        self.__check_amount(value, allow_zero=True)
        self.__price_paid = value

    @property
    def current_declared_value(self) -> float | None:
        return self.__current_declared_value

    @current_declared_value.setter
    def current_declared_value(self, value: float | None) -> None:
        self.__check_amount(value, allow_zero=True)
        self.__current_declared_value = value

    @property
    def income_produced(self) -> float | None:
        return self.__income_produced

    @income_produced.setter
    def income_produced(self, value: float | None) -> None:
        self.__check_amount(value, allow_zero=True)
        self.__income_produced = value

    @property
    def payment_method(self) -> str | None:
        return self.__payment_method

    def category(self, policy: dict) -> str:
        """property / listed_equities / private_business / other, by the policy's keyword lists."""
        text = (self.__asset_type or "").lower()
        for category, keywords in policy["asset_categories"].items():
            if any(word in text for word in keywords):
                return category
        return "other"

    def to_dict(self) -> dict:
        return {**self.__extra,
                "asset_type": self.__asset_type, "country": self.__country,
                "year_acquired": self.__year_acquired, "price_paid": self.__price_paid,
                "current_declared_value": self.__current_declared_value,
                "payment_method": self.__payment_method, "income_produced": self.__income_produced}

    def __check_year(self, year: int | None) -> None:
        if year is None:
            return
        if isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2100:
            raise ValueError("the year an asset was acquired must be a whole year between 1900 and 2100")

    def __check_amount(self, value: float | None, allow_zero: bool) -> None:
        if value is None:
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("an asset amount must be a number or left empty")
        if value < 0 or (value == 0 and not allow_zero):
            raise ValueError("an asset amount cannot be negative" if value < 0
                             else "an asset amount cannot be zero")

    def __check_payment_method(self, method: str | None) -> None:
        if method is not None and not isinstance(method, str):
            raise ValueError("a payment method must be text or left empty")
