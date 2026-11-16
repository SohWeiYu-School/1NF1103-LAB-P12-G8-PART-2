"""AssessmentRepository: every assessment that was run, several per client."""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone

from app.data.json_repository import JsonRepository

logger = logging.getLogger(__name__)


class AssessmentRepository(JsonRepository):
    """Assessments in ai_assessments.json. Saving always adds a new record; nothing is replaced.
    The one thing ever added to an old record is a line in its archive_log (archive / restore).
    Nothing is deleted: the last line of the log decides whether the assessment is hidden."""

    MAX_REASON_LENGTH: int = 200
    MAX_BY_LENGTH: int = 80
    ACTIVE: str = "active"
    ARCHIVED: str = "archived"
    UNREADABLE: str = "unreadable"       # the archive log is damaged, so the state cannot be told
    CHANGED: str = "changed"
    NOT_FOUND: str = "not_found"
    NO_CHANGE: str = "no_change"         # already in the state that was asked for
    NOT_SAVED: str = "not_saved"         # the file could not be written
    __ACTIONS: tuple[str, ...] = ("archived", "restored")

    def __init__(self, path: str = os.path.join(JsonRepository.DATA_DIR, "ai_assessments.json"),
                 key_field: str = "assessment_id") -> None:
        super().__init__(path, key_field)
        # save() and archive()/restore() each read the file, change it and write it back; the lock
        # stops one from overwriting the other's change.
        self.__lock: threading.Lock = threading.Lock()

    def save(self, record: dict) -> bool:
        """Add one assessment. It is given an id if it has none. Returns False (and leaves the
        file untouched) if the saved assessments cannot be read, so they are never overwritten."""
        if not isinstance(record, dict) or "client_ref" not in record:
            return False
        if self._key_field not in record:
            record = {**record, self._key_field: str(uuid.uuid4())}
        with self.__lock:
            try:
                records = self.load()
            except (OSError, ValueError) as error:
                logger.error("AssessmentRepository.save: not saved, the existing records cannot be read: %r", error)
                return False
            return self._write_all(records + [record])

    def for_client(self, client_ref: str, include_archived: bool = False) -> list[dict]:
        """Every assessment of one client, newest first. Archived ones (and ones whose archive log is
        damaged) are left out unless include_archived. Raises OSError or ValueError if the file cannot be read."""
        records = self.__visible(self.load(), include_archived)
        matches = [record for record in records if record.get("client_ref") == client_ref]
        return sorted(matches, key=lambda record: record.get("assessed_at", ""), reverse=True)

    def query(self, outcome: str, include_archived: bool = False) -> list[dict]:
        """The assessments with this outcome; every assessment if no outcome is given.
        Archived ones (and ones whose archive log is damaged) are left out unless include_archived.
        Older records keep their outcome inside "assessment". Raises OSError or ValueError if the file cannot be read."""
        records = self.__visible(self.load(), include_archived)
        if not outcome:
            return records
        return [record for record in records
                if (record.get("outcome") or AssessmentRepository.__old_outcome(record)) == outcome]

    def archive(self, assessment_id: str, reason: str = "", by: str = "") -> str:
        """Hide one assessment from the lists. It is not deleted. by is who did it (written on the
        line). Returns CHANGED, NOT_FOUND, NO_CHANGE (already archived), UNREADABLE (its archive log is
        damaged) or NOT_SAVED (the file could not be written). Raises ValueError if the reason is longer
        than MAX_REASON_LENGTH or not printable text, if by is missing or not printable text of at most
        MAX_BY_LENGTH characters, and OSError or ValueError if the file cannot be read."""
        problem = AssessmentRepository.reason_problem(reason)
        if problem:
            raise ValueError(problem)
        return self.__record_action(assessment_id, "archived", reason.strip(), AssessmentRepository.__checked_by(by))

    @staticmethod
    def reason_problem(reason: object) -> str:
        """What is wrong with an archive reason, in plain words; "" if it is fine (an empty reason is fine)."""
        if not isinstance(reason, str):
            return "The reason must be text."
        reason = reason.strip()
        if len(reason) > AssessmentRepository.MAX_REASON_LENGTH:
            return (f"The reason is too long: at most {AssessmentRepository.MAX_REASON_LENGTH} "
                    f"characters are allowed, not {len(reason)}.")
        if not reason.isprintable():
            return "The reason can only hold printable characters (no line breaks or control characters)."
        return ""

    def restore(self, assessment_id: str, by: str = "") -> str:
        """Bring an archived assessment back into the lists. by is who did it (written on the line).
        Returns CHANGED, NOT_FOUND, NO_CHANGE (not archived), UNREADABLE or NOT_SAVED. Raises ValueError
        if by is missing or not printable text of at most MAX_BY_LENGTH characters, and OSError or
        ValueError if the file cannot be read."""
        return self.__record_action(assessment_id, "restored", "", AssessmentRepository.__checked_by(by))

    @staticmethod
    def __checked_by(by: object) -> str:
        """by, trimmed. Raises ValueError, saying what is allowed, if it is not usable."""
        if not isinstance(by, str):
            raise ValueError("Who did it (by) must be text.")
        by = by.strip()
        if not by or not by.isprintable() or len(by) > AssessmentRepository.MAX_BY_LENGTH:
            raise ValueError(f"Who did it (by) must be printable text of 1 to "
                             f"{AssessmentRepository.MAX_BY_LENGTH} characters.")
        return by

    @staticmethod
    def archive_state(record: dict) -> str:
        """ACTIVE (no archive_log, or an empty list), ARCHIVED, or UNREADABLE (the archive_log is not a
        list of entries that each have an action of "archived" or "restored" and, if given, an "at"
        time, a reason and a "by" as text). The last entry decides. Does not log: it is called for every row."""
        log = record.get("archive_log") if isinstance(record, dict) else None
        if log is None or log == []:
            return AssessmentRepository.ACTIVE
        if not isinstance(log, list) or not all(AssessmentRepository.__good_entry(entry) for entry in log):
            return AssessmentRepository.UNREADABLE
        return AssessmentRepository.ARCHIVED if log[-1]["action"] == "archived" else AssessmentRepository.ACTIVE

    @staticmethod
    def is_archived(record: dict) -> bool:
        """True if the assessment is hidden from the lists: archived, or archive log damaged (decision: hidden)."""
        return AssessmentRepository.archive_state(record) != AssessmentRepository.ACTIVE

    @staticmethod
    def __good_entry(entry: object) -> bool:
        """True if one archive log line has the layout archive() and restore() write."""
        return (isinstance(entry, dict) and entry.get("action") in AssessmentRepository.__ACTIONS
                and isinstance(entry.get("at", ""), str) and isinstance(entry.get("reason", ""), str)
                and isinstance(entry.get("by", ""), str))

    @staticmethod
    def __visible(records: list[dict], include_archived: bool) -> list[dict]:
        """The records to list. Logs one warning naming every record with a damaged archive log."""
        damaged = [str(record.get("assessment_id", "?")) for record in records
                   if AssessmentRepository.archive_state(record) == AssessmentRepository.UNREADABLE]
        if damaged:
            logger.warning("AssessmentRepository: the archive log is damaged for assessment(s) %s; "
                           "they are treated as archived", ", ".join(damaged))
        if include_archived:
            return records
        return [record for record in records if AssessmentRepository.archive_state(record) == AssessmentRepository.ACTIVE]

    def __record_action(self, assessment_id: str, action: str, reason: str, by: str) -> str:
        """Add one line to the assessment's archive log. Nothing else in the record is touched."""
        wanted = str(assessment_id or "").strip().upper()
        if not wanted:
            return AssessmentRepository.NOT_FOUND
        with self.__lock:
            records = self.load()
            for record in records:
                if str(record.get(self._key_field, "")).upper() != wanted:
                    continue
                state = AssessmentRepository.archive_state(record)
                if state == AssessmentRepository.UNREADABLE:
                    logger.warning("AssessmentRepository: the archive log of %s is damaged, so nothing was changed",
                                   record.get(self._key_field))
                    return AssessmentRepository.UNREADABLE
                if (state == AssessmentRepository.ARCHIVED) == (action == "archived"):
                    return AssessmentRepository.NO_CHANGE
                entry = {"action": action, "at": datetime.now(timezone.utc).isoformat(), "by": by}
                if reason:
                    entry["reason"] = reason
                if not record.get("archive_log"):
                    record["archive_log"] = []          # none yet (or an empty one)
                record["archive_log"].append(entry)
                if not self._write_all(records):
                    logger.error("AssessmentRepository: the %s of %s was not saved", action, record.get(self._key_field))
                    return AssessmentRepository.NOT_SAVED
                return AssessmentRepository.CHANGED
        return AssessmentRepository.NOT_FOUND

    @staticmethod
    def __old_outcome(record: dict) -> str | None:
        """The outcome an older record keeps inside "assessment" (None if that part is not a dict)."""
        old = record.get("assessment")
        return old.get("outcome") if isinstance(old, dict) else None
