"""AuditRepository: the audit log, an append-only chain of events in one JSON file."""

import logging
import os
import re
import threading

from app.data.json_repository import JsonRepository
from app.model.audit_event import AuditEvent

logger = logging.getLogger(__name__)


class AuditRepository(JsonRepository):
    """Events in audit_log.json. save() only ever adds one sealed event to the end; there is no
    replace, update or delete. Each event holds the hash of the one before it, so a change made
    outside the app shows up when the chain is checked."""

    __HASH_PATTERN: str = r"^[0-9a-f]{64}$"

    def __init__(self, path: str = os.path.join(JsonRepository.DATA_DIR, "audit_log.json"),
                 key_field: str = "event_id") -> None:
        super().__init__(path, key_field)
        # save() reads the file, adds a row and writes it back; the lock stops two saves at the
        # same time from taking the same sequence number.
        self.__lock: threading.Lock = threading.Lock()

    def save(self, record: dict) -> bool:
        """Seal one event onto the end of the chain and write it. The record may be unsealed. Returns
        False (the reason logged, the file untouched) if the record is not a valid audit event, if the
        file cannot be read (so it is never overwritten) or if it cannot be written. If the last row is
        damaged the event is still added, chained to the all-zero start hash, and a warning is logged;
        checking the chain will show the break."""
        try:
            event = AuditEvent.from_dict(record)
        except ValueError as error:
            logger.error("AuditRepository.save: not saved, the event is not valid: %s", error)
            return False
        with self.__lock:
            try:
                rows = self.load()
            except (OSError, ValueError) as error:
                logger.error("AuditRepository.save: not saved, the existing log cannot be read: %r", error)
                return False
            last = rows[-1] if rows else None
            previous_hash = AuditEvent.GENESIS
            sequence = len(rows) + 1
            if last is not None:
                last_hash, last_sequence = last.get("hash"), last.get("sequence")
                if isinstance(last_hash, str) and re.match(AuditRepository.__HASH_PATTERN, last_hash):
                    previous_hash = last_hash
                else:
                    logger.warning("AuditRepository.save: the last row (entry %d) has no valid hash; chaining "
                                   "the new event to the start hash, so checking the log will show a break",
                                   len(rows))
                if isinstance(last_sequence, int) and not isinstance(last_sequence, bool) and last_sequence >= 1:
                    sequence = last_sequence + 1
            event.seal(sequence, previous_hash)
            return self._write_all(rows + [event.to_dict()])

    def for_client(self, client_ref: str) -> list[dict]:
        """Every event about one client, oldest first (the reference is matched ignoring case). An
        empty reference matches nothing. Raises OSError or ValueError if the file cannot be read."""
        wanted = str(client_ref or "").strip().casefold()
        if not wanted:
            return []
        return [row for row in self.load() if str(row.get("client_ref", "")).casefold() == wanted]
