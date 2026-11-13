"""Indicator and its five children: the warning signs looked for in a declaration."""

from abc import ABC, abstractmethod

from app.model.declaration import Declaration


class Indicator(ABC):
    """One warning sign. Each child answers one question about the client's declaration:
    does this sign fire? A typology is matched by the signs it lists, by NAME."""

    NAME: str = "indicator"

    def __init__(self, policy: dict | None = None) -> None:
        self._policy: dict = policy or {}

    @abstractmethod
    def fires(self, declaration: Declaration) -> bool:
        """True if the declaration shows this warning sign."""


class GiftOrInheritanceUnnamed(Indicator):
    """A gift or inheritance from someone who is not named."""

    NAME: str = "gift_or_inheritance_unnamed"

    def __init__(self, policy: dict | None = None) -> None:
        super().__init__(policy)

    def fires(self, declaration: Declaration) -> bool:
        return any(source.is_gift_or_inheritance() and not source.has_named_counterparty()
                   for source in declaration.sources())


class CounterpartyUnnamed(Indicator):
    """Too many sources with no named counterparty (the policy sets how many is too many)."""

    NAME: str = "counterparty_unnamed"

    def __init__(self, policy: dict | None = None) -> None:
        super().__init__(policy)

    def fires(self, declaration: Declaration) -> bool:
        limit = self._policy.get("thresholds", {}).get("unknown_counterparty_limit", 1)
        return declaration.unnamed_count() >= limit


class SourceContradictsOccupation(Indicator):
    """A source the declaration reading marked as not fitting the client's occupation."""

    NAME: str = "source_contradicts_occupation"

    def __init__(self, policy: dict | None = None) -> None:
        super().__init__(policy)

    def fires(self, declaration: Declaration) -> bool:
        return any(source.occupation_mismatch for source in declaration.sources())


class UnvaluedSource(Indicator):
    """A source with no amount. A salary, bonus or savings source tied to one of his jobs
    does not count: the forecast works out what that job paid."""

    NAME: str = "unvalued_source_present"

    def __init__(self, policy: dict | None = None) -> None:
        super().__init__(policy)

    def fires(self, declaration: Declaration) -> bool:
        return any(not source.is_valued() for source in declaration.sources())


class RelatedPartyTransaction(Indicator):
    """A counterparty described as family or a close associate."""

    NAME: str = "related_party_transaction"
    __KEYWORDS: list[str] = [
        "associate", "family", "relative", "friend",
        "brother", "sister", "spouse", "wife", "husband",
        "son", "daughter", "parent", "mother", "father",
        "partner", "in-law",
    ]

    def __init__(self, policy: dict | None = None) -> None:
        super().__init__(policy)

    def fires(self, declaration: Declaration) -> bool:
        for source in declaration.sources():
            counterparty = source.counterparty
            if counterparty and any(word in counterparty.lower() for word in RelatedPartyTransaction.__KEYWORDS):
                return True
        return False
