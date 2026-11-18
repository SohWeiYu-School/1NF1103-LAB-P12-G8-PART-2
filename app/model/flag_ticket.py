"""FlagTicket: a flag's status, assignee and history, rebuilt from its flag_updated log lines."""

from app.model.audit_event import AuditEvent
from app.model.flag import Flag


class FlagTicket:
    """The work done on one flag. Nothing is stored here: the ticket is replayed from the
    "flag_updated" lines of the audit log each time, so a status change is protected by the hash chain.

    Lines for other flags, lines that failed to save, and lines whose details cannot be read (an unknown
    status) are left out; skipped_count says how many of the lines for this flag were left out for being
    unreadable. A flag with no lines is Open. Moving a flag out of Resolved is allowed (a reopen).
    """

    STATUSES: dict[str, str] = {"open": "Open", "review": "In review", "followup": "Following up",
                                "resolved": "Resolved"}
    OUTCOMES: dict[str, str] = {"legit": "No issue: the activity was legitimate",
                                "fixed": "Fixed: the problem was corrected",
                                "escalated": "Escalated to compliance"}
    WAITING_ON: tuple[str, ...] = ("Owner officer", "Officer who made the change", "IT support", "Compliance")
    NOTE_MIN: int = 5
    NOTE_MAX: int = 500
    OPENED_NOTE: str = "Opened automatically by the rule."

    def __init__(self, flag: Flag | None = None, events: list[AuditEvent] | None = None) -> None:
        """flag is the flag; events are the log's events, oldest first (only the flag_updated lines for
        this flag's id matter). Raises ValueError if flag is not a Flag or events is not a list of events."""
        flag = Flag() if flag is None else flag
        events = [] if events is None else events
        if not isinstance(flag, Flag):
            raise ValueError("A ticket needs a flag.")
        if not isinstance(events, list) or any(not isinstance(event, AuditEvent) for event in events):
            raise ValueError("The ticket's events must be a list of audit events.")
        self.__flag: Flag = flag
        self.__status: str = "open"
        self.__assignee: str = ""
        self.__waiting_on: str = ""
        self.__outcome: str = ""
        self.__skipped: int = 0
        self.__history: list[dict] = [{"by": "System", "at": flag.raised_at, "from": "", "to": "open",
                                       "note": FlagTicket.OPENED_NOTE}]
        for event in events:
            if (event.action == "flag_updated" and event.result == "ok"
                    and event.details.get("flag_id") == flag.flag_id):
                self.__apply(event)

    def __apply(self, event: AuditEvent) -> None:
        """Replay one line, or count it as skipped if its details cannot be read."""
        details = event.details
        target = details.get("to")
        note, waiting_on, outcome = details.get("note", ""), details.get("waiting_on", ""), details.get("outcome", "")
        if (target not in FlagTicket.STATUSES or not isinstance(note, str) or not isinstance(waiting_on, str)
                or not isinstance(outcome, str)):
            self.__skipped += 1
            return
        before = self.__status
        if before == "open" and target != "open" and not self.__assignee:
            self.__assignee = event.actor
        self.__status = target
        if target == "followup":
            self.__waiting_on = waiting_on or self.__waiting_on
        else:
            self.__waiting_on = ""
        if target == "resolved":
            self.__outcome = outcome or self.__outcome
        else:
            self.__outcome = ""
        self.__history.append({"by": event.actor, "at": event.at, "from": before, "to": target, "note": note,
                               "waiting_on": waiting_on, "outcome": outcome, "sequence": event.sequence})

    @property
    def flag(self) -> Flag:
        return self.__flag

    @property
    def status(self) -> str:
        """"open", "review", "followup" or "resolved"."""
        return self.__status

    @property
    def status_name(self) -> str:
        """The status for people, e.g. "In review"."""
        return FlagTicket.STATUSES[self.__status]

    @property
    def assignee(self) -> str:
        """The first person to move the flag out of Open; "" while it is still Open."""
        return self.__assignee

    @property
    def waiting_on(self) -> str:
        """Who the flag is waiting on while it is Following up; "" otherwise."""
        return self.__waiting_on

    @property
    def outcome(self) -> str:
        """The outcome key ("legit", "fixed", "escalated") while Resolved; "" otherwise."""
        return self.__outcome

    @property
    def skipped_count(self) -> int:
        """How many log lines for this flag could not be read and were left out."""
        return self.__skipped

    @property
    def history(self) -> list[dict]:
        """Plain dicts, oldest first. The first is the rule opening the flag; then one per update."""
        return [dict(entry) for entry in self.__history]

    def needs_waiting_on(self, status: str) -> bool:
        """True if moving to this status needs "waiting on": moving to Following up from another status."""
        return status == "followup" and status != self.__status

    def needs_outcome(self, status: str) -> bool:
        """True if moving to this status needs an outcome: moving to Resolved from another status."""
        return status == "resolved" and status != self.__status

    def check_update(self, status: str, note: str, waiting_on: str = "", outcome: str = "") -> list[str]:
        """What is wrong with an update, as messages for the officer (an empty list when it is fine).
        The same status as now means "add a note": only the note is needed."""
        problems: list[str] = []
        if status not in FlagTicket.STATUSES:
            problems.append("Choose a status: Open, In review, Following up or Resolved.")
        text = note.strip() if isinstance(note, str) else ""
        if len(text) < FlagTicket.NOTE_MIN:
            problems.append(f"Please write a note of at least {FlagTicket.NOTE_MIN} characters saying what "
                            "you found or did.")
        elif len(text) > FlagTicket.NOTE_MAX:
            problems.append(f"Please keep the note to {FlagTicket.NOTE_MAX} characters or fewer.")
        if self.needs_waiting_on(status) and waiting_on not in FlagTicket.WAITING_ON:
            problems.append("Choose who you are waiting on.")
        if self.needs_outcome(status) and outcome not in FlagTicket.OUTCOMES:
            problems.append("Choose an outcome before resolving.")
        return problems

    def update_details(self, actor: str, status: str, note: str, waiting_on: str = "",
                       outcome: str = "") -> dict:
        """The details of the flag_updated line that records this update. "Waiting on" and "outcome" are
        kept only when they apply (moving to Following up, moving to Resolved). Raises ValueError, with
        the problems joined, if check_update finds any or actor is empty."""
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("An update needs the name of the person making it.")
        problems = self.check_update(status, note, waiting_on, outcome)
        if problems:
            raise ValueError(" ".join(problems))
        return {"flag_id": self.__flag.flag_id, "from": self.__status, "to": status,
                "waiting_on": waiting_on if self.needs_waiting_on(status) else "",
                "outcome": outcome if self.needs_outcome(status) else "", "note": note.strip()}
