"""Repository: the three things every store of records can do."""

from abc import ABC, abstractmethod


class Repository(ABC):
    """The interface every repository follows, whether it keeps records in a JSON file
    or in a database. Code that uses a Repository does not need to know which."""

    def __init__(self) -> None:
        """A Repository keeps no state of its own; each kind of store sets up its own."""

    @abstractmethod
    def save(self, record: dict) -> bool:
        """Store one record. Returns False if it could not be stored."""

    @abstractmethod
    def load(self) -> list[dict]:
        """Every record. Returns [] if there are none or they cannot be read."""

    @abstractmethod
    def find(self, ref: str) -> dict | None:
        """The record with this reference, or None."""
