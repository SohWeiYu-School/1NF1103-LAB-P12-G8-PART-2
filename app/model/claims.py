"""Claims: the figures the client declares about his wealth."""


class Claims:
    """Declared net worth, the money he expects to place with the bank, his PEP status,
    how his wealth is split and where it came from."""

    NO_PEP_VALUES: tuple[str, ...] = ("none", "no", "not a pep", "n/a", "na")
    LIQUID_PARTS: tuple[str, ...] = ("listed_equities", "cash")

    def __init__(self, declared_net_worth: float | None = None, expected_aum: float | None = None, pep_status: str = "",
                 asset_composition: dict | None = None, wealth_countries: list[str] | None = None,
                 declared_counterparties: list[str] | None = None, biggest_wealth_jump: float | None = None,
                 wealth_jump_years: int | None = None, extra: dict | None = None) -> None:
        self.__check_positive(declared_net_worth)
        self.__check_positive(expected_aum)
        self.__check_positive(biggest_wealth_jump)
        self.__check_positive(wealth_jump_years)
        self.__check_shares(asset_composition or {})
        self.__declared_net_worth: float | None = declared_net_worth
        self.__expected_aum: float | None = expected_aum
        self.__pep_status: str = pep_status
        self.__asset_composition: dict = dict(asset_composition or {})
        self.__wealth_countries: list[str] = list(wealth_countries or [])
        self.__declared_counterparties: list[str] = list(declared_counterparties or [])
        self.__biggest_wealth_jump: float | None = biggest_wealth_jump
        self.__wealth_jump_years: int | None = wealth_jump_years
        self.__extra: dict = dict(extra or {})

    @property
    def declared_net_worth(self) -> float | None:
        return self.__declared_net_worth

    @declared_net_worth.setter
    def declared_net_worth(self, value: float | None) -> None:
        self.__check_positive(value)
        self.__declared_net_worth = value

    @property
    def expected_aum(self) -> float | None:
        return self.__expected_aum

    @expected_aum.setter
    def expected_aum(self, value: float | None) -> None:
        self.__check_positive(value)
        self.__expected_aum = value

    @property
    def pep_status(self) -> str:
        return self.__pep_status

    @pep_status.setter
    def pep_status(self, status: str) -> None:
        if status is not None and not isinstance(status, str):
            raise ValueError("PEP status must be text")
        self.__pep_status = status

    @property
    def asset_composition(self) -> dict:
        return dict(self.__asset_composition)

    @asset_composition.setter
    def asset_composition(self, composition: dict) -> None:
        self.__check_shares(composition or {})
        self.__asset_composition = dict(composition or {})

    @property
    def wealth_countries(self) -> list[str]:
        return list(self.__wealth_countries)

    @wealth_countries.setter
    def wealth_countries(self, countries: list[str]) -> None:
        self.__wealth_countries = [str(country) for country in countries or []]

    @property
    def declared_counterparties(self) -> list[str]:
        return list(self.__declared_counterparties)

    @property
    def biggest_wealth_jump(self) -> float | None:
        return self.__biggest_wealth_jump

    @biggest_wealth_jump.setter
    def biggest_wealth_jump(self, value: float | None) -> None:
        self.__check_positive(value)
        self.__biggest_wealth_jump = value

    @property
    def wealth_jump_years(self) -> int | None:
        return self.__wealth_jump_years

    @wealth_jump_years.setter
    def wealth_jump_years(self, value: int | None) -> None:
        self.__check_positive(value)
        self.__wealth_jump_years = value

    def is_pep(self) -> bool:
        """True unless the PEP status is one of the ways of writing "no". A blank status is
        unknown, not "no": it counts as a PEP (the cautious side) and problems() lists it."""
        return str(self.__pep_status or "").strip().lower() not in Claims.NO_PEP_VALUES

    def liquid_share(self) -> float:
        """The share of his wealth held in cash and listed equities (0.31 = 31%)."""
        return sum(self.__asset_composition.get(part) or 0 for part in Claims.LIQUID_PARTS)

    def problems(self) -> list[str]:
        """What stops these claims being used. Empty list = nothing."""
        problems = []
        if self.__declared_net_worth is None:
            problems.append("Declared net worth is missing: enter an amount greater than 0.")
        if not str(self.__pep_status or "").strip():
            problems.append("The PEP question is not answered. Answer \"None\" if the client is not a "
                            "politically exposed person, or say which kind of PEP the client is.")
        shares = [share for share in self.__asset_composition.values() if isinstance(share, (int, float))]
        if shares and abs(sum(shares) - 1.0) > 0.01:
            problems.append(f"The asset split adds up to {sum(shares):.0%}, not 100%.")
        return problems

    def warnings(self) -> list[str]:
        """Things worth a second look. Empty list = nothing spotted."""
        warnings = []
        worth, aum = self.__declared_net_worth, self.__expected_aum
        if worth is not None and aum is not None and aum > worth:
            warnings.append("Expected assets with the bank are more than the declared net worth.")
        return warnings

    def to_dict(self) -> dict:
        return {**self.__extra,
                "declared_net_worth": self.__declared_net_worth, "expected_aum": self.__expected_aum,
                "pep_status": self.__pep_status, "wealth_countries": list(self.__wealth_countries),
                "asset_composition": dict(self.__asset_composition) or None,
                "biggest_wealth_jump": self.__biggest_wealth_jump,
                "wealth_jump_years": self.__wealth_jump_years,
                "declared_counterparties": list(self.__declared_counterparties)}

    def __check_positive(self, value: float | None) -> None:
        if value is None:
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("a declared figure must be a number or left empty")
        if value < 0:
            raise ValueError("a declared figure cannot be negative")

    def __check_shares(self, composition: dict) -> None:
        for part, share in composition.items():
            if share is None:
                continue
            if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 <= share <= 1:
                raise ValueError(f"the {part} share must be between 0 and 1 (0.25 = 25%)")
