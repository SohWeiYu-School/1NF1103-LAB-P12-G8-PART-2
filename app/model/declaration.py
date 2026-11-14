"""Declaration: the client's source of wealth declaration, as a list of claimed sources."""

from app.model.claimed_source import ClaimedSource


class Declaration:
    """What the client says his wealth came from. It creates and owns its ClaimedSources."""

    def __init__(self, sources: list[dict] | None = None) -> None:
        self.__sources: list[ClaimedSource] = []
        for details in sources or []:
            self.add_source(details)

    def sources(self) -> list[ClaimedSource]:
        return list(self.__sources)

    def add_source(self, details: dict) -> ClaimedSource:
        """Add one source from its details. The amount may be under "amount" or "amount_sgd"."""
        amount = details.get("amount_sgd", details.get("amount"))
        source = ClaimedSource(
            source_type=details.get("source_type") or "",
            counterparty=details.get("counterparty"),
            amount=amount,
            occupation_mismatch=details.get("occupation_mismatch") is True,
            amount_explained=bool(details.get("amount_explained_by_forecast")),
        )
        self.__sources.append(source)
        return source

    def unnamed_count(self) -> int:
        """How many sources name no counterparty."""
        return sum(1 for source in self.__sources if not source.has_named_counterparty())
