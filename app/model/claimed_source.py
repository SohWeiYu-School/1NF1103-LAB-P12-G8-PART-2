"""ClaimedSource: one source of wealth the client named in the declaration."""


class ClaimedSource:
    """One claimed source (a salary, a gift, a business sale, ...) as the AI read it."""

    GIFT_TYPES: tuple[str, ...] = ("inheritance", "gift")

    def __init__(self, source_type: str = "", counterparty: str | None = None, amount: float | None = None,
                 occupation_mismatch: bool = False, amount_explained: bool = False) -> None:
        self.__check_amount(amount)
        self.__source_type: str = source_type
        self.__counterparty: str | None = counterparty
        self.__amount: float | None = amount
        self.__occupation_mismatch: bool = bool(occupation_mismatch)
        # True for a salary, bonus or savings source tied to one of his jobs: the forecast
        # works out what that job paid, so the source needs no amount of its own.
        self.__amount_explained: bool = bool(amount_explained)

    @property
    def source_type(self) -> str:
        return self.__source_type

    @property
    def counterparty(self) -> str | None:
        return self.__counterparty

    @property
    def amount(self) -> float | None:
        return self.__amount

    @amount.setter
    def amount(self, amount: float | None) -> None:
        self.__check_amount(amount)
        self.__amount = amount

    @property
    def occupation_mismatch(self) -> bool:
        return self.__occupation_mismatch

    def is_gift_or_inheritance(self) -> bool:
        return self.__source_type in ClaimedSource.GIFT_TYPES

    def has_named_counterparty(self) -> bool:
        return self.__counterparty is not None

    def is_valued(self) -> bool:
        """True if the source has an amount, or needs none because the forecast explains it."""
        return self.__amount is not None or self.__amount_explained

    def __check_amount(self, amount: float | None) -> None:
        if amount is None:
            return
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("a source amount must be a number or left empty")
        if amount < 0:
            raise ValueError("a source amount cannot be negative")
