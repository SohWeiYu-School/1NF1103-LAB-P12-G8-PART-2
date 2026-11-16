"""CloudSync: copies what is new or changed from a local repository to the cloud backup."""

import hashlib
import json
import logging
import os

from app.data.database_repository import DatabaseRepository
from app.data.json_repository import JsonRepository
from app.data.repository import Repository

logger = logging.getLogger(__name__)


class CloudSync:
    """Backs up one local repository to one database repository.

    Both repositories are made elsewhere and handed in. A record is sent only if it is
    new or has changed since the last sync; a state file remembers what was sent.
    """

    def __init__(self, local: Repository | None = None, remote: DatabaseRepository | None = None,
                 state_path: str = os.path.join(JsonRepository.DATA_DIR, "sync_state.json")) -> None:
        self.__local: Repository | None = local
        self.__remote: DatabaseRepository | None = remote
        self.__state_path: str = state_path

    def is_online(self) -> bool:
        return self.__local is not None and self.__remote is not None and self.__remote.is_online()

    def sync(self) -> dict:
        """Send new and changed records. Returns {"synced", "skipped", "errors"}. If the local
        records cannot be read, nothing is sent and the failure is listed in "errors"."""
        stats = {"synced": 0, "skipped": 0, "errors": []}
        if not self.is_online():
            stats["errors"].append("Cannot reach the cloud database. Your data is still safe in the local files.")
            return stats

        try:
            records = self.__local.load()
        except (OSError, ValueError) as error:
            # Not "0 records synced": the local records could not be read, so nothing was backed up.
            logger.error("CloudSync.sync: the local records cannot be read: %r", error)
            stats["errors"].append(f"The local records for {self.__remote.name.replace('_', ' ')} could not be read, "
                                   "so nothing was sent to the cloud database.")
            return stats

        state = self.__load_state()
        sent = state.setdefault(self.__remote.name, {})
        for record in records:
            # Upload local-only documents first: this writes each file's id onto the record.
            if self.__remote.upload_local_documents(record):
                self.__local.save(record)
            fingerprint = CloudSync.__fingerprint(record)
            key = str(record.get(self.__remote.key_field) or fingerprint)
            if sent.get(key) == fingerprint:
                stats["skipped"] += 1
                continue
            if self.__remote.save(record):
                sent[key] = fingerprint
                stats["synced"] += 1
            else:
                stats["errors"].append(f"{key}: could not be sent to the cloud database.")
        self.__save_state(state)
        return stats

    def __load_state(self) -> dict:
        if not os.path.exists(self.__state_path):
            return {}
        try:
            with open(self.__state_path, "r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (ValueError, OSError) as error:
            logger.warning("CloudSync: could not read the sync state: %s", repr(error))
            return {}
        return state if isinstance(state, dict) else {}

    def __save_state(self, state: dict) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.__state_path)), exist_ok=True)
            with open(self.__state_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=4)
        except OSError as error:
            logger.warning("CloudSync: could not write the sync state: %s", repr(error))

    @staticmethod
    def __fingerprint(record: dict) -> str:
        """The same content gives the same fingerprint, so an unchanged record can be skipped."""
        return hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()
