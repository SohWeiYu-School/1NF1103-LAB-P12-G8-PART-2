"""Band: one money figure kept at three levels (cautious, typical, optimistic)."""


class Band:
    """A money result at three levels. Every figure in the forecast is a Band."""

    LEVELS: tuple[str, ...] = ("cautious", "typical", "optimistic")
    # Which end of an AI {low, typical, high} range each level uses.
    # For money coming in, cautious = low. For money going out (tax, living costs), cautious = high.
    MONEY_IN: dict[str, str] = {"cautious": "low", "typical": "typical", "optimistic": "high"}
    MONEY_OUT: dict[str, str] = {"cautious": "high", "typical": "typical", "optimistic": "low"}

    def __init__(self, cautious: float = 0.0, typical: float = 0.0, optimistic: float = 0.0) -> None:
        self.__cautious: float = round(cautious, 2)
        self.__typical: float = round(typical, 2)
        self.__optimistic: float = round(optimistic, 2)

    @property
    def cautious(self) -> float:
        return self.__cautious

    @property
    def typical(self) -> float:
        return self.__typical

    @property
    def optimistic(self) -> float:
        return self.__optimistic

    def __add__(self, other: "Band") -> "Band":
        return Band(self.__cautious + other.cautious, self.__typical + other.typical,
                    self.__optimistic + other.optimistic)

    def __mul__(self, factor: float) -> "Band":
        return Band(self.__cautious * factor, self.__typical * factor, self.__optimistic * factor)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Band) and self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"Band({self.__cautious}, {self.__typical}, {self.__optimistic})"

    @staticmethod
    def from_values(values: list[float]) -> "Band":
        """Three results worked out from the low, typical and high inputs, lowest first."""
        low, middle, high = sorted(values)
        return Band(low, middle, high)

    @staticmethod
    def from_range(ai_range: dict) -> "Band":
        """An AI {low, typical, high} range as a cautious/typical/optimistic band."""
        return Band(ai_range["low"], ai_range["typical"], ai_range["high"])

    @staticmethod
    def from_dict(data: dict) -> "Band":
        return Band(data["cautious"], data["typical"], data["optimistic"])

    def to_dict(self) -> dict:
        return {"cautious": self.__cautious, "typical": self.__typical, "optimistic": self.__optimistic}

    # ----- the same arithmetic on bands in their saved layout (dicts) -------------
    # Forecast results are saved and compared as plain dicts, so the forecast classes
    # keep them in that layout and ask Band to do the arithmetic.

    @staticmethod
    def as_dict(cautious: float, typical: float, optimistic: float) -> dict:
        return Band(cautious, typical, optimistic).to_dict()

    @staticmethod
    def zero() -> dict:
        return Band().to_dict()

    @staticmethod
    def add(first: dict, second: dict) -> dict:
        return (Band.from_dict(first) + Band.from_dict(second)).to_dict()

    @staticmethod
    def scale(values: dict, factor: float) -> dict:
        return (Band.from_dict(values) * factor).to_dict()

    @staticmethod
    def ordered(values: list[float]) -> dict:
        return Band.from_values(values).to_dict()

    @staticmethod
    def from_ai(ai_range: dict) -> dict:
        return Band.from_range(ai_range).to_dict()
