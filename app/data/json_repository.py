"""JsonRepository: records kept as a list in one local JSON file."""

import json
import logging
import os
from abc import abstractmethod

from app.data.repository import Repository

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class JsonRepository(Repository):
    """A repository backed by one JSON file. Children decide how a record is saved
    (replace the one with the same reference, or always add a new one)."""

    DATA_DIR: str = os.path.join(ROOT_DIR, "data", "local database")

    def __init__(self, path: str = "", key_field: str = "") -> None:
        super().__init__()
        self._path: str = path
        self._key_field: str = key_field

    @abstractmethod
    def save(self, record: dict) -> bool:
        """Store one record. Returns False if it could not be stored."""

    def load(self) -> list[dict]:
        """Every record in the file. A missing file means no records yet and gives [].
        Raises OSError if the file cannot be read and ValueError if its content is damaged
        (not valid JSON, not a list, or a list with something other than records in it);
        the real details are logged first."""
        if not os.path.exists(self._path):
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as error:
            logger.error("JsonRepository.load: could not read %s: %s", self._path, repr(error))
            raise
        except ValueError as error:      # includes JSONDecodeError and UnicodeDecodeError
            logger.error("JsonRepository.load: %s is damaged: %s", self._path, repr(error))
            raise ValueError(f"The file {os.path.basename(self._path)} is damaged: {error}") from error
        if not isinstance(data, list) or not all(isinstance(record, dict) for record in data):
            logger.error("JsonRepository.load: %s does not hold a list of records", self._path)
            raise ValueError(f"The file {os.path.basename(self._path)} is damaged: "
                             "it must hold a list of records.")
        return data

    def find(self, ref: str) -> dict | None:
        """The record whose key matches ref (upper and lower case are treated the same), or None
        if there is none. Raises what load() raises when the file cannot be read."""
        wanted = str(ref or "").strip().upper()
        if not wanted:
            return None
        for record in self.load():
            if str(record.get(self._key_field, "")).upper() == wanted:
                return record
        return None

    def _write_all(self, records: list[dict]) -> bool:
        """Replace the file's contents with these records."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as handle:
                json.dump(records, handle, indent=4, ensure_ascii=False)
            return True
        except OSError as error:
            logger.error("JsonRepository: could not write %s: %s", self._path, repr(error))
            return False
