"""ClaimedSource: one source of wealth the client named in the declaration."""


class ClaimedSource:
    """One claimed source (a salary, a gift, a business sale, ...) as the AI read it.

    It is written down in two layouts: the AI's reading (to_dict, the keys of the declaration
    schema) and the crime scan's row (to_scan_dict, as the assessment saves it). from_dict reads
    either one.
    """

    GIFT_TYPES: tuple[str, ...] = ("inheritance", "gift")
    # The keys of the AI's reading, in the declaration schema's order. The last two were added
    # later, so an older saved reading may not have them.
    READING_KEYS: tuple[str, ...] = ("source_id", "source_type", "description", "start_year", "end_year", "amount",
                                     "country", "linked_position_index", "linked_asset_index", "quote",
                                     "counterparty", "occupation_mismatch")
    # The crime scan's row names for the same facts
    __SCAN_NAMES: dict = {"amount_sgd": "amount", "jurisdiction": "country", "evidence_sentence": "quote"}

    def __init__(self, source_type: str = "", counterparty: str | None = None, amount: float | None = None,
                 occupation_mismatch: bool = False, amount_explained: bool = False, source_id: str | None = None,
                 description: str = "", start_year: int | None = None, end_year: int | None = None,
                 country: str | None = None, quote: str = "", linked_position_index: int | None = None,
                 linked_asset_index: int | None = None, layout: tuple[str, ...] = READING_KEYS) -> None:
        self.__check_text(source_type, "type", False)
        self.__check_text(description, "description", False)
        self.__check_text(quote, "quote", False)
        self.__check_text(counterparty, "counterparty", True)
        self.__check_text(source_id, "id", True)
        self.__check_text(country, "country", True)
        self.__check_amount(amount)
        self.__check_year(start_year, "start year")
        self.__check_year(end_year, "end year")
        self.__check_index(linked_position_index, "linked job")
        self.__check_index(linked_asset_index, "linked asset")
        self.__check_layout(layout)
        self.__source_type: str = source_type
        self.__counterparty: str | None = counterparty
        self.__amount: float | None = amount
        self.__occupation_mismatch: bool = bool(occupation_mismatch)
        # True for a salary, bonus or savings source tied to one of his jobs: the forecast
        # works out what that job paid, so the source needs no amount of its own.
        self.__amount_explained: bool = bool(amount_explained)
        self.__source_id: str | None = source_id
        self.__description: str = description
        self.__start_year: int | None = start_year
        self.__end_year: int | None = end_year
        self.__country: str | None = country
        self.__quote: str = quote
        self.__linked_position_index: int | None = linked_position_index
        self.__linked_asset_index: int | None = linked_asset_index
        # The keys the reading had, in its order, so to_dict gives back the same layout
        self.__layout: tuple[str, ...] = tuple(layout)

    @staticmethod
    def from_dict(details: dict) -> "ClaimedSource":
        """A source from the AI's reading ({"amount", "country", "quote", ...}) or from the crime
        scan's row ({"amount_sgd", "jurisdiction", "evidence_sentence", ...})."""
        layout = []
        for key in details:
            name = ClaimedSource.__SCAN_NAMES.get(key, key)
            if name in ClaimedSource.READING_KEYS and name not in layout:
                layout.append(name)
        return ClaimedSource(
            source_type=details.get("source_type") or "",
            counterparty=details.get("counterparty"),
            amount=details["amount_sgd"] if "amount_sgd" in details else details.get("amount"),
            occupation_mismatch=details.get("occupation_mismatch") is True,
            amount_explained=bool(details.get("amount_explained_by_forecast")),
            source_id=details.get("source_id"),
            description=details.get("description") or "",
            start_year=details.get("start_year"),
            end_year=details.get("end_year"),
            country=details["jurisdiction"] if "jurisdiction" in details else details.get("country"),
            quote=(details["evidence_sentence"] if "evidence_sentence" in details else details.get("quote")) or "",
            linked_position_index=details.get("linked_position_index"),
            linked_asset_index=details.get("linked_asset_index"),
            layout=tuple(layout))

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

    @property
    def amount_explained(self) -> bool:
        return self.__amount_explained

    @property
    def source_id(self) -> str | None:
        return self.__source_id

    @property
    def description(self) -> str:
        return self.__description

    @property
    def start_year(self) -> int | None:
        return self.__start_year

    @property
    def end_year(self) -> int | None:
        return self.__end_year

    @property
    def country(self) -> str | None:
        return self.__country

    @property
    def quote(self) -> str:
        return self.__quote

    @property
    def linked_position_index(self) -> int | None:
        return self.__linked_position_index

    @property
    def linked_asset_index(self) -> int | None:
        return self.__linked_asset_index

    def is_gift_or_inheritance(self) -> bool:
        return self.__source_type in ClaimedSource.GIFT_TYPES

    def has_named_counterparty(self) -> bool:
        return self.__counterparty is not None

    def counterparty_read(self) -> bool:
        """False for an older saved reading, made before the AI was asked for counterparties."""
        return "counterparty" in self.__layout

    def is_valued(self) -> bool:
        """True if the source has an amount, or needs none because the forecast explains it."""
        return self.__amount is not None or self.__amount_explained

    def to_dict(self) -> dict:
        """The source in the AI's reading layout, with the keys the reading had, in its order."""
        values = {"source_id": self.__source_id, "source_type": self.__source_type,
                  "description": self.__description, "start_year": self.__start_year,
                  "end_year": self.__end_year, "amount": self.__amount, "country": self.__country,
                  "linked_position_index": self.__linked_position_index,
                  "linked_asset_index": self.__linked_asset_index, "quote": self.__quote,
                  "counterparty": self.__counterparty, "occupation_mismatch": self.__occupation_mismatch}
        return {key: values[key] for key in self.__layout}

    def to_scan_dict(self) -> dict:
        """The source as the crime scan's row (the layout saved under crime_scan.declaration)."""
        return {"source_id": self.__source_id, "source_type": self.__source_type,
                "description": self.__description, "amount_sgd": self.__amount,
                "start_year": self.__start_year, "end_year": self.__end_year, "jurisdiction": self.__country,
                "counterparty": self.__counterparty, "evidence_sentence": self.__quote,
                "occupation_mismatch": self.__occupation_mismatch,
                "amount_explained_by_forecast": self.__amount_explained}

    def __check_text(self, value: object, label: str, or_none: bool) -> None:
        """Text fields hold text. The optional ones (counterparty, id, country) may also be None."""
        if value is None and or_none:
            return
        if not isinstance(value, str):
            raise ValueError(f"a source's {label} must be text, not {type(value).__name__}")

    def __check_amount(self, amount: float | None) -> None:
        if amount is None:
            return
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("a source amount must be a number or left empty")
        if amount < 0:
            raise ValueError("a source amount cannot be negative")

    def __check_year(self, year: int | None, label: str) -> None:
        if year is not None and not self.__is_whole(year):
            raise ValueError(f"a source's {label} must be a whole number or left empty")

    def __check_index(self, index: int | None, label: str) -> None:
        if index is not None and not (self.__is_whole(index) and index >= 0):
            raise ValueError(f"a source's {label} must be a position (0 or more) or left empty")

    def __is_whole(self, value: object) -> bool:
        """A whole number (a JSON reply may write 3 as 3.0); True and False are not numbers."""
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())

    def __check_layout(self, layout: tuple[str, ...]) -> None:
        unknown = [key for key in layout if key not in ClaimedSource.READING_KEYS]
        if unknown:
            raise ValueError(f"a source's reading can only have the keys {list(ClaimedSource.READING_KEYS)}, "
                             f"not {unknown}")
