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
        """Every record. Returns [] only when there are none yet. If the records cannot be read,
        the real details are logged and an error is raised, so an unreadable store is never
        mistaken for an empty one: OSError (file cannot be read), ValueError (content is damaged),
        ConnectionError (database unreachable or failed; ConnectionError is an OSError)."""

    @abstractmethod
    def find(self, ref: str) -> dict | None:
        """The record with this reference, or None if there is none. Raises the same errors as
        load() when the store cannot be read."""
