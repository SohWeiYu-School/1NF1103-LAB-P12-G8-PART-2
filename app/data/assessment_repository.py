"""AssessmentRepository: every assessment that was run, several per client."""

import logging
import os
import uuid

from app.data.json_repository import JsonRepository

logger = logging.getLogger(__name__)


class AssessmentRepository(JsonRepository):
    """Assessments in ai_assessments.json. Saving always adds a new record; nothing is replaced."""

    def __init__(self, path: str = os.path.join(JsonRepository.DATA_DIR, "ai_assessments.json"),
                 key_field: str = "assessment_id") -> None:
        super().__init__(path, key_field)

    def save(self, record: dict) -> bool:
        """Add one assessment. It is given an id if it has none. Returns False (and leaves the
        file untouched) if the saved assessments cannot be read, so they are never overwritten."""
        if not isinstance(record, dict) or "client_ref" not in record:
            return False
        if self._key_field not in record:
            record = {**record, self._key_field: str(uuid.uuid4())}
        try:
            records = self.load()
        except (OSError, ValueError) as error:
            logger.error("AssessmentRepository.save: not saved, the existing records cannot be read: %r", error)
            return False
        return self._write_all(records + [record])

    def for_client(self, client_ref: str) -> list[dict]:
        """Every assessment of one client, newest first. Raises OSError or ValueError if the file cannot be read."""
        matches = [record for record in self.load() if record.get("client_ref") == client_ref]
        return sorted(matches, key=lambda record: record.get("assessed_at", ""), reverse=True)

    def query(self, outcome: str) -> list[dict]:
        """The assessments with this outcome; every assessment if no outcome is given.
        Older records keep their outcome inside "assessment". Raises OSError or ValueError if the file cannot be read."""
        records = self.load()
        if not outcome:
            return records
        return [record for record in records
                if (record.get("outcome") or AssessmentRepository.__old_outcome(record)) == outcome]

    @staticmethod
    def __old_outcome(record: dict) -> str | None:
        """The outcome an older record keeps inside "assessment" (None if that part is not a dict)."""
        old = record.get("assessment")
        return old.get("outcome") if isinstance(old, dict) else None
