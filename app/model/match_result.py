"""MatchResult: how one typology matched one client."""

from app.model.typology import Typology


class MatchResult:
    """The warning signs of one typology that fired for the client."""

    def __init__(self, typology: Typology | None = None, core_fired: list[str] | None = None) -> None:
        self.__typology: Typology = typology or Typology()
        self.__core_fired: list[str] = list(core_fired or [])

    @property
    def typology(self) -> Typology:
        return self.__typology

    @property
    def core_fired(self) -> list[str]:
        return list(self.__core_fired)

    @property
    def breached(self) -> bool:
        """True when every core warning sign fired (and there is at least one)."""
        core = self.__typology.core_indicators()
        return len(core) > 0 and len(self.__core_fired) == len(core)
