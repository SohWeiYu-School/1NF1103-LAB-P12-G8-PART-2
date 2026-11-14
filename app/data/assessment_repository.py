"""AssessmentRepository: every assessment that was run, several per client."""

import os
import uuid
from datetime import datetime, timezone

from app.data.json_repository import JsonRepository

class AssessmentRepository(JsonRepository):
    """Assessments in ai_assessments.json. Saving always adds a new record; nothing is replaced.
    The one thing that is ever written to an old record is a line in its archive log."""

    def __init__(self, path: str = os.path.join(JsonRepository.DATA_DIR, "ai_assessments.json"),
                 key_field: str = "assessment_id") -> None:
        super().__init__(path, key_field)

    def save(self, record: dict) -> bool:
        """Add one assessment. It is given an id if it has none."""
        if not isinstance(record, dict) or "client_ref" not in record:
            return False
        if self._key_field not in record:
            record = {**record, self._key_field: str(uuid.uuid4())}
        return self._write_all(self.load() + [record])

    def for_client(self, client_ref: str, include_archived: bool = False) -> list[dict]:
        """Every assessment of one client, newest first. Archived ones are left out unless asked for."""
        matches = [record for record in self.load() if record.get("client_ref") == client_ref
                   and (include_archived or not AssessmentRepository.is_archived(record))]
        return sorted(matches, key=lambda record: record.get("assessed_at", ""), reverse=True)

    def query(self, outcome: str, include_archived: bool = False) -> list[dict]:
        """The assessments with this outcome; every assessment if no outcome is given.
        Archived ones are left out unless asked for. Older records keep their outcome inside "assessment"."""
        records = [record for record in self.load()
                   if include_archived or not AssessmentRepository.is_archived(record)]
        if not outcome:
            return records
        return [record for record in records
                if (record.get("outcome") or (record.get("assessment") or {}).get("outcome")) == outcome]

    def archive(self, assessment_id: str, reason: str = "") -> bool:
        """Hide one assessment from the lists. It is not deleted. False if there is no such
        assessment or it is already archived."""
        return self.__record_archive_action(assessment_id, "archived", reason)

    def restore(self, assessment_id: str) -> bool:
        """Bring an archived assessment back into the lists. False if there is no such
        assessment or it is not archived."""
        return self.__record_archive_action(assessment_id, "restored", "")

    @staticmethod
    def is_archived(record: dict) -> bool:
        """True if the last thing done to this assessment was to archive it."""
        log = record.get("archive_log") or []
        return bool(log) and log[-1].get("action") == "archived"

    def __record_archive_action(self, assessment_id: str, action: str, reason: str) -> bool:
        """Add one line to the assessment's archive log. Nothing else in the record is touched."""
        records = self.load()
        for record in records:
            if record.get(self._key_field) != assessment_id:
                continue
            if AssessmentRepository.is_archived(record) == (action == "archived"):
                return False
            entry = {"action": action, "at": datetime.now(timezone.utc).isoformat()}
            if reason:
                entry["reason"] = reason
            record.setdefault("archive_log", []).append(entry)
            return self._write_all(records)
        return False
