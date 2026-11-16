"""AuditEvent: one line of the audit log, sealed into a hash chain."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone


class AuditEvent:
    """Who did what, when, to which client, and how it went.

    A new event is unsealed (sequence 0, no hash). The repository seals it onto the end of the
    chain with seal(): that fixes its place (sequence), the hash of the line before it, and its own
    hash, which covers every other field. Change any field later and hash_matches() turns False.

    The hash covers the fields as this class normalises them (text trimmed, details rewritten as
    plain JSON), not the raw bytes in the file. The chain can only show that the log is consistent
    with itself: it cannot detect rows removed from the end, or a file that was emptied or rewritten
    from the start with a fresh, valid chain.
    """

    TERMINAL: str = "terminal"
    GENESIS: str = "0" * 64                  # the "previous hash" of the first entry
    RESULTS: tuple[str, ...] = ("ok", "failed")
    GROUPS: dict[str, tuple[str, ...]] = {
        "Sign-in": ("signed_in", "signed_out"),
        "Client": ("client_created", "client_edited"),
        "Documents": ("autofill_used", "document_uploaded", "document_downloaded"),
        "Assessment": ("assessment_run", "assessment_failed", "assessment_archived", "assessment_restored"),
        "System": ("cloud_sync", "audit_verified", "access_refused"),
    }
    ACTIONS: tuple[str, ...] = tuple(action for actions in GROUPS.values() for action in actions)
    LABELS: dict[str, str] = {
        "signed_in": "Signed in", "signed_out": "Signed out",
        "client_created": "Client created", "client_edited": "Client edited",
        "autofill_used": "Used document auto-fill", "document_uploaded": "Document uploaded",
        "document_downloaded": "Document downloaded",
        "assessment_run": "Assessed", "assessment_failed": "Assessment failed",
        "assessment_archived": "Archived an assessment", "assessment_restored": "Restored an assessment",
        "cloud_sync": "Cloud sync", "audit_verified": "Verified the audit log",
        "access_refused": "Access refused",
    }
    MAX_ACTOR: int = 80
    MAX_CLIENT_REF: int = 40
    MAX_EVENT_ID: int = 64
    TIME_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"
    __HASH_PATTERN: str = r"^[0-9a-f]{64}$"
    __TIME_PATTERN: str = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"

    def __init__(self, event_id: str = "", sequence: int = 0, at: str = "", actor: str = "terminal",
                 action: str = "", client_ref: str = "", result: str = "ok", details: dict | None = None,
                 previous_hash: str = "", hash: str = "") -> None:
        """Raises ValueError, saying what is wrong and what is allowed, for any impossible value.
        An empty action is allowed only for the all-defaults object (an unset event)."""
        details = {} if details is None else details
        text_fields = {"event_id": event_id, "at": at, "actor": actor, "action": action,
                       "client_ref": client_ref, "result": result, "previous_hash": previous_hash, "hash": hash}
        for name, value in text_fields.items():
            if not isinstance(value, str):
                raise ValueError(f"The audit event's {name} must be text.")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:        # a lone surrogate such as "\ud800" cannot be saved
                raise ValueError(f"The audit event's {name} holds a character that cannot be saved "
                                 "as text.") from error
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError(f"The audit event's sequence must be a whole number, 0 or more (got {sequence!r}).")
        actor, client_ref, event_id = actor.strip(), client_ref.strip(), event_id.strip()
        if not actor or not actor.isprintable() or len(actor) > AuditEvent.MAX_ACTOR:
            raise ValueError(f"The actor must be printable text of 1 to {AuditEvent.MAX_ACTOR} characters.")
        if not client_ref.isprintable() or len(client_ref) > AuditEvent.MAX_CLIENT_REF:
            raise ValueError(f"The client reference must be printable text of at most "
                             f"{AuditEvent.MAX_CLIENT_REF} characters.")
        if not event_id.isprintable() or len(event_id) > AuditEvent.MAX_EVENT_ID:
            raise ValueError(f"The event id must be printable text of at most {AuditEvent.MAX_EVENT_ID} characters.")
        if result not in AuditEvent.RESULTS:
            raise ValueError(f"The result must be one of {', '.join(AuditEvent.RESULTS)} (got {result!r}).")
        if not isinstance(details, dict):
            raise ValueError("The details must be an object (a dict).")
        try:
            text = json.dumps(details, allow_nan=False, ensure_ascii=False)
            text.encode("utf-8")                       # refuses a lone surrogate, which the file cannot hold
            details = json.loads(text)                 # a private copy that JSON can hold
        except (TypeError, ValueError) as error:
            raise ValueError(f"The details must hold only plain JSON values: {error}") from error
        if at and not AuditEvent.__good_time(at):
            raise ValueError("The time must look like 2026-11-15T06:02:11Z (UTC, to the second) "
                             f"(got {at!r}).")
        for name, value in (("previous_hash", previous_hash), ("hash", hash)):
            if value and not re.match(AuditEvent.__HASH_PATTERN, value):
                raise ValueError(f"The {name} must be empty or 64 lowercase hex characters.")
        if action not in AuditEvent.ACTIONS:
            unset = (action == "" and not event_id and not sequence and not at and actor == AuditEvent.TERMINAL
                     and not client_ref and result == "ok" and not details and not previous_hash and not hash)
            if not unset:
                raise ValueError(f"The action must be one of {', '.join(AuditEvent.ACTIONS)} (got {action!r}).")
        self.__event_id: str = event_id or str(uuid.uuid4())
        self.__sequence: int = sequence
        self.__at: str = at or datetime.now(timezone.utc).strftime(AuditEvent.TIME_FORMAT)
        self.__actor: str = actor
        self.__action: str = action
        self.__client_ref: str = client_ref
        self.__result: str = result
        self.__details: dict = details
        self.__previous_hash: str = previous_hash
        self.__hash: str = hash

    @staticmethod
    def __good_time(text: str) -> bool:
        """True if text is a real UTC time in the exact layout."""
        if not re.match(AuditEvent.__TIME_PATTERN, text):
            return False
        try:
            datetime.strptime(text, AuditEvent.TIME_FORMAT)
        except ValueError:
            return False
        return True

    @property
    def event_id(self) -> str:
        return self.__event_id

    @property
    def sequence(self) -> int:
        return self.__sequence

    @property
    def at(self) -> str:
        return self.__at

    @property
    def actor(self) -> str:
        return self.__actor

    @property
    def action(self) -> str:
        return self.__action

    @property
    def client_ref(self) -> str:
        return self.__client_ref

    @property
    def result(self) -> str:
        return self.__result

    @property
    def details(self) -> dict:
        return self.__details

    @property
    def previous_hash(self) -> str:
        return self.__previous_hash

    @property
    def hash(self) -> str:
        return self.__hash

    @property
    def group(self) -> str:
        """The group the action belongs to ("Client", "System", ...); "" for an unset event."""
        for name, actions in AuditEvent.GROUPS.items():
            if self.__action in actions:
                return name
        return ""

    @property
    def label(self) -> str:
        """A short plain label for the action ("Client edited"); "" for an unset event."""
        return AuditEvent.LABELS.get(self.__action, "")

    def compute_hash(self) -> str:
        """The SHA-256 of every field except the hash, written as sorted, compact JSON. The same
        fields always give the same hash. Raises ValueError for an unset event (no action)."""
        data = self.to_dict()
        del data["hash"]
        text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def seal(self, sequence: int, previous_hash: str) -> None:
        """Fix this event's place in the chain and set its hash. Raises ValueError for a sequence
        below 1, a previous hash that is not 64 lowercase hex characters, or an event with no action."""
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError(f"A sealed event needs a sequence of 1 or more (got {sequence!r}).")
        if not isinstance(previous_hash, str) or not re.match(AuditEvent.__HASH_PATTERN, previous_hash):
            raise ValueError("The previous hash must be 64 lowercase hex characters "
                             "(the first entry uses 64 zeros).")
        if not self.__action:
            raise ValueError("An event with no action cannot be sealed.")
        self.__sequence = sequence
        self.__previous_hash = previous_hash
        self.__hash = self.compute_hash()

    def is_sealed(self) -> bool:
        """True once seal() has given it a sequence and a hash."""
        return self.__sequence >= 1 and bool(self.__hash)

    def hash_matches(self) -> bool:
        """True if the stored hash is the hash of the fields as they are now."""
        return bool(self.__hash) and self.__hash == self.compute_hash()

    def summary(self) -> str:
        """One plain line for the log and the client's history, e.g. "Edited client C-0007 (2 fields
        changed)". A failed event ends with " — failed"."""
        details = self.__details
        who = f"client {self.__client_ref}" if self.__client_ref else "a client"
        action = self.__action
        if action == "signed_in":
            text = "Signed in"
        elif action == "signed_out":
            text = "Signed out"
        elif action == "client_created":
            text = f"Created {who}"
        elif action == "client_edited":
            changes = details.get("changes")
            count = len(changes) if isinstance(changes, list) else 0
            text = f"Edited {who} ({count} field{'' if count == 1 else 's'} changed)"
        elif action == "autofill_used":
            text = (f"Used document auto-fill ({AuditEvent.__count(details.get('documents'), 'document')}, "
                    f"{AuditEvent.__count(details.get('fields'), 'field')} found)")
        elif action == "document_uploaded":
            text = AuditEvent.__words("Uploaded document", AuditEvent.__plain(details.get("file_id")))
        elif action == "document_downloaded":
            text = AuditEvent.__words("Downloaded document", AuditEvent.__plain(details.get("file_id")))
        elif action == "assessment_run":
            outcome = details.get("outcome")
            text = f"Assessment saved for {who}" + (f": {outcome}" if isinstance(outcome, str) and outcome else "")
        elif action == "assessment_failed":
            text = f"Assessment for {who} could not be completed"
        elif action == "assessment_archived":
            reason = details.get("reason")
            text = AuditEvent.__words("Archived assessment", AuditEvent.__short(details.get("assessment_id")),
                                      f"(reason: {reason})" if isinstance(reason, str) and reason else "")
        elif action == "assessment_restored":
            text = AuditEvent.__words("Restored assessment", AuditEvent.__short(details.get("assessment_id")))
        elif action == "cloud_sync":
            text = f"Cloud sync ({AuditEvent.__count(details.get('synced'), 'record')} synced)"
        elif action == "audit_verified":
            text = "Verified the audit log"
        elif action == "access_refused":
            what = details.get("what")
            text = "Access refused" + (f": {what}" if isinstance(what, str) and what else "")
        else:
            text = "(no action)"
        return text + (" — failed" if self.__result == "failed" else "")

    @staticmethod
    def __words(*parts: str) -> str:
        """The non-empty parts joined by single spaces (no double or trailing spaces)."""
        return " ".join(part for part in parts if part)

    @staticmethod
    def __short(value: object) -> str:
        """An id shortened to 8 characters and an ellipsis; "" if there is none."""
        if not isinstance(value, str) or not value:
            return ""
        return value if len(value) <= 8 else value[:8] + "…"

    @staticmethod
    def __plain(value: object) -> str:
        """A file id as text, cut at 60 characters; "" if there is none."""
        return value[:60] if isinstance(value, str) else ""

    @staticmethod
    def __count(value: object, noun: str) -> str:
        """"3 documents" for a whole number (a bad or missing value counts as 0)."""
        number = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
        return f"{number} {noun}{'' if number == 1 else 's'}"

    def to_dict(self) -> dict:
        """The saved layout, in this key order. Raises ValueError for an unset event (no action)."""
        if not self.__action:
            raise ValueError("An event with no action cannot be saved.")
        return {"event_id": self.__event_id, "sequence": self.__sequence, "at": self.__at,
                "actor": self.__actor, "action": self.__action, "client_ref": self.__client_ref,
                "result": self.__result, "details": json.loads(json.dumps(self.__details)),
                "previous_hash": self.__previous_hash, "hash": self.__hash}

    @staticmethod
    def from_dict(data: dict) -> "AuditEvent":
        """Build an event from its saved layout (an unsealed one is fine). Unknown keys are dropped.
        Raises ValueError if data is not an object, has no valid action, or any value is impossible."""
        if not isinstance(data, dict):
            raise ValueError("An audit event must be an object.")
        if not data.get("action"):
            raise ValueError(f"An audit event needs an action, one of {', '.join(AuditEvent.ACTIONS)}.")
        return AuditEvent(data.get("event_id", ""), data.get("sequence", 0), data.get("at", ""),
                          data.get("actor", AuditEvent.TERMINAL), data["action"], data.get("client_ref", ""),
                          data.get("result", "ok"), data.get("details", {}), data.get("previous_hash", ""),
                          data.get("hash", ""))
