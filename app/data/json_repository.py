"""JsonRepository: records kept as a list in one local JSON file."""

import json
import logging
import os
import tempfile
from abc import abstractmethod

from app.data.repository import Repository

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class JsonRepository(Repository):
    """A repository backed by one JSON file. Children decide how a record is saved
    (replace the one with the same reference, or always add a new one)."""

    DATA_DIR: str = os.path.join(ROOT_DIR, "data", "local database")

    def __init__(self, path: str, key_field: str) -> None:
        """path and key_field must be given and cannot be empty (ValueError): a repository with
        no file has nowhere to keep its records, and one with no key cannot tell them apart."""
        super().__init__()
        if not isinstance(path, str) or not path.strip():
            raise ValueError("A JSON repository needs the path of its file (it cannot be empty).")
        if not isinstance(key_field, str) or not key_field.strip():
            raise ValueError("A JSON repository needs a key field, the field that tells one record "
                             "from another (it cannot be empty).")
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
        """Replace the file's contents with these records. Written to a temporary file in the
        same folder first, then swapped in, so a reader never sees a half-written file and a
        crash half way leaves the old file whole. Returns False (the real error logged, the
        temporary file removed) if the file could not be written or a record cannot be held in JSON."""
        temporary = None
        try:
            folder = os.path.dirname(os.path.abspath(self._path))
            os.makedirs(folder, exist_ok=True)
            # A name no other writer (thread or process) shares, so two writers never swap in
            # each other's half-written file.
            descriptor, temporary = tempfile.mkstemp(dir=folder, prefix=os.path.basename(self._path) + ".",
                                                     suffix=".tmp")
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(records, handle, indent=4, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
            return True
        except (OSError, TypeError, ValueError) as error:   # TypeError/ValueError: a record JSON cannot hold
            logger.error("JsonRepository: could not write %s: %s", self._path, repr(error))
            try:
                if temporary is not None and os.path.exists(temporary):
                    os.remove(temporary)
            except OSError as cleanup_error:
                logger.error("JsonRepository: could not remove %s: %s", temporary, repr(cleanup_error))
            return False
