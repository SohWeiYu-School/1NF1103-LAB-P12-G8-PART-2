"""DatabaseRepository: records kept in a database (the cloud backup)."""

import logging
import os
from abc import abstractmethod

from app.data.json_repository import ROOT_DIR
from app.data.repository import Repository

logger = logging.getLogger(__name__)


class DatabaseRepository(Repository):
    """A repository backed by a database. It knows what to store and when; its children
    know how to talk to one kind of database (connect, write, read, store a file)."""

    def __init__(self, collection_name: str, key_field: str, uri: str) -> None:
        self._collection_name: str = collection_name
        self._key_field: str = key_field
        self._uri: str = uri or ""

    @property
    def name(self) -> str:
        """The name of the collection this repository writes to."""
        return self._collection_name

    @property
    def key_field(self) -> str:
        """The field that tells one record from another."""
        return self._key_field

    def save(self, record: dict) -> bool:
        """Add the record, or replace the stored one with the same key."""
        if not isinstance(record, dict) or not self._connect():
            return False
        return self._upsert(str(record.get(self._key_field) or ""), record)

    def load(self) -> list[dict]:
        return self._fetch({}) if self._connect() else []

    def find(self, ref: str) -> dict | None:
        if not ref or not self._connect():
            return None
        matches = self._fetch({self._key_field: ref})
        return matches[0] if matches else None

    def is_online(self) -> bool:
        """True if the database can be reached right now."""
        return self._connect()

    def upload_local_documents(self, record: dict) -> int:
        """Store the record's documents that only exist locally, and write each one's new
        file_id onto the record. Returns how many were uploaded."""
        if not self._connect():
            return 0
        uploaded = 0
        for document in record.get("supporting_documents") or []:
            path = document.get("file_path")
            if document.get("file_id") or not path:
                continue
            full_path = path if os.path.isabs(path) else os.path.join(ROOT_DIR, path)
            if not os.path.exists(full_path):
                continue
            file_id = self._store_file(full_path, document.get("file_name") or os.path.basename(full_path))
            if file_id:
                document["file_id"] = file_id
                uploaded += 1
        return uploaded

    @abstractmethod
    def _connect(self) -> bool:
        """Open the connection if it is not open. Returns False if the database cannot be reached."""

    @abstractmethod
    def _upsert(self, key: str, record: dict) -> bool:
        """Write one record, replacing the one with the same key."""

    @abstractmethod
    def _fetch(self, query: dict) -> list[dict]:
        """The records that match the query."""

    @abstractmethod
    def _store_file(self, path: str, name: str) -> str:
        """Store one file. Returns its id in the database, or "" if it could not be stored."""
