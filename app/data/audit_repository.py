"""AuditRepository: the audit log, an append-only chain of events in one JSON file."""

import logging
import os
import re
import threading
import time

try:
    import fcntl            # POSIX (macOS, Linux)
except ImportError:         # Windows
    fcntl = None
try:
    import msvcrt           # Windows
except ImportError:         # POSIX
    msvcrt = None

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
        # The web server and the terminal menu are separate processes on the same file, so the
        # thread lock is not enough: save() also holds an exclusive lock on this sidecar file.
        self.__lock_path: str = path + ".lock"

    def __lock_file(self):
        """Open the sidecar lock file and take an exclusive lock on it, waiting for the other
        process to finish. Returns the open handle (give it to __unlock_file). Raises OSError if
        the file cannot be opened or locked."""
        os.makedirs(os.path.dirname(os.path.abspath(self.__lock_path)), exist_ok=True)
        handle = open(self.__lock_path, "a+b")
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            elif msvcrt is not None:
                while True:
                    try:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        time.sleep(0.05)
            else:
                raise OSError("this system has no file locking")
        except BaseException:
            handle.close()
            raise
        return handle

    def __unlock_file(self, handle) -> None:
        """Release the lock taken by __lock_file and close the handle (closing frees it anyway)."""
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError as error:
            logger.warning("AuditRepository: could not release the lock file cleanly: %r", error)
        finally:
            handle.close()

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
                lock_handle = self.__lock_file()
            except OSError as error:
                logger.error("AuditRepository.save: not saved, the lock file %s cannot be locked: %r",
                             self.__lock_path, error)
                return False
            try:
                return self.__save_locked(event)
            finally:
                self.__unlock_file(lock_handle)

    def __save_locked(self, event: AuditEvent) -> bool:
        """The read, seal and write of save(), run while both locks are held."""
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
        try:
            event.seal(sequence, previous_hash)
            sealed = event.to_dict()
        except ValueError as error:
            logger.error("AuditRepository.save: not saved, the event could not be sealed: %r", error)
            return False
        return self._write_all(rows + [sealed])

    def for_client(self, client_ref: str) -> list[dict]:
        """Every event about one client, oldest first (the reference is matched ignoring case). An
        empty reference matches nothing. Raises OSError or ValueError if the file cannot be read."""
        wanted = str(client_ref or "").strip().casefold()
        if not wanted:
            return []
        return [row for row in self.load() if str(row.get("client_ref", "")).casefold() == wanted]
