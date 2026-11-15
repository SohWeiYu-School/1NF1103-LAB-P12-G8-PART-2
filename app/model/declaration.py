"""Declaration: the client's source of wealth declaration, as a list of claimed sources."""

from app.model.claimed_source import ClaimedSource


class Declaration:
    """What the client says his wealth came from. It creates and owns its ClaimedSources.

    It is written down in two layouts: the AI's reading {"claimed_sources": [...]} (to_dict,
    sent in the forecast prompts) and the crime scan's rows {"sources": [...]} (to_scan_dict,
    saved with the assessment). from_dict reads either one.
    """

    def __init__(self, sources: list[dict] | None = None) -> None:
        self.__sources: list[ClaimedSource] = []
        for details in sources or []:
            self.add_source(details)

    @staticmethod
    def from_dict(data: dict) -> "Declaration":
        """A declaration from the AI's reading {"claimed_sources": [...]} or the crime scan's
        rows {"sources": [...]}."""
        if not isinstance(data, dict):
            raise ValueError("a declaration must be an object with a list of sources")
        sources = data["claimed_sources"] if "claimed_sources" in data else data.get("sources", [])
        if not isinstance(sources, list) or not all(isinstance(source, dict) for source in sources):
            raise ValueError("a declaration's sources must be a list of objects")
        return Declaration(sources)

    def sources(self) -> list[ClaimedSource]:
        return list(self.__sources)

    def add_source(self, details: dict) -> ClaimedSource:
        """Add one source from its details, in either layout (see ClaimedSource.from_dict)."""
        source = ClaimedSource.from_dict(details)
        self.__sources.append(source)
        return source

    def unnamed_count(self) -> int:
        """How many sources name no counterparty."""
        return sum(1 for source in self.__sources if not source.has_named_counterparty())

    def to_dict(self) -> dict:
        """The AI's reading layout: {"claimed_sources": [...]}."""
        return {"claimed_sources": [source.to_dict() for source in self.__sources]}

    def to_scan_dict(self) -> dict:
        """The crime scan's layout, as the assessment saves it: {"sources": [...]}."""
        return {"sources": [source.to_scan_dict() for source in self.__sources]}
