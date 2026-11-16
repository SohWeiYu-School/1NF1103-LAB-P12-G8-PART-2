"""AuditChain: checks that the audit log is still the chain the app wrote."""

import re

from app.model.audit_event import AuditEvent


class AuditChain:
    """Reads the rows of the audit log and finds where the hash chain breaks.

    A row breaks the chain when its hash does not match its content, its previous_hash is not the
    hash of the row before it (the all-zero start hash for the first), or its sequence is not the
    one before plus 1. A row that cannot be read as an event is itself a break. The work is done
    once, when the object is made.

    Breaks are named by the row's 1-based position in the file, not by the sequence stored in it,
    because a changed row's own sequence cannot be trusted. The hash covers the fields as AuditEvent
    normalises them, and the check proves only that the log agrees with itself: it cannot detect rows
    removed from the end, or a file that was emptied or rewritten from the start with a new valid chain.
    """

    REQUIRED_KEYS: tuple[str, ...] = ("event_id", "sequence", "at", "action", "previous_hash", "hash")
    MAX_NAMED: int = 5            # how many entry numbers the summary names before "and N more"
    __HASH_PATTERN: str = r"^[0-9a-f]{64}$"

    def __init__(self, rows: list[dict] | None = None) -> None:
        """rows are the saved rows in file order. Raises ValueError if rows is not a list."""
        rows = [] if rows is None else rows
        if not isinstance(rows, list):
            raise ValueError("The audit rows must be a list.")
        self.__rows: list[dict] = list(rows)
        self.__events: list[AuditEvent] = []
        self.__unreadable: list[int] = []         # 1-based row numbers
        self.__breaks: list[int] = []             # 1-based row positions
        self.__broken_ids: list[str] = []         # event ids of the readable rows that break the chain
        self.__mismatches: list[int] = []         # the breaks that are readable rows
        self.__check()

    def __check(self) -> None:
        """Walk the rows once, filling events, unreadable, breaks and mismatches."""
        expected_hash: str | None = AuditEvent.GENESIS      # None = the row before could not be trusted
        expected_sequence = 1
        for position, row in enumerate(self.__rows, start=1):
            try:
                if not isinstance(row, dict) or any(key not in row for key in AuditChain.REQUIRED_KEYS):
                    raise ValueError("a saved row must hold every field")     # never filled in with now or a new id
                if not row["event_id"] or not row["at"]:
                    raise ValueError("a saved row must have an id and a time")
                event = AuditEvent.from_dict(row)
            except ValueError:
                self.__unreadable.append(position)
                self.__breaks.append(position)
                stored = row.get("hash") if isinstance(row, dict) else None
                expected_hash = stored if isinstance(stored, str) and re.match(AuditChain.__HASH_PATTERN, stored) \
                    else None
                sequence = row.get("sequence") if isinstance(row, dict) else None
                expected_sequence = (sequence if isinstance(sequence, int) and not isinstance(sequence, bool)
                                     and sequence >= 1 else expected_sequence) + 1
                continue
            self.__events.append(event)
            broken = (not event.hash_matches()
                      or (expected_hash is not None and event.previous_hash != expected_hash)
                      or event.sequence != expected_sequence)
            if broken:
                self.__breaks.append(position)
                self.__mismatches.append(position)
                self.__broken_ids.append(event.event_id)
            expected_hash = event.hash if re.match(AuditChain.__HASH_PATTERN, event.hash) else None
            expected_sequence = event.sequence + 1

    def events(self) -> list[AuditEvent]:
        """The rows that could be read as events, in file order."""
        return list(self.__events)

    def unreadable_count(self) -> int:
        """How many rows could not be read as events."""
        return len(self.__unreadable)

    def breaks(self) -> list[int]:
        """The 1-based file position of every row where the chain breaks (unreadable rows included)."""
        return list(self.__breaks)

    def broken_ids(self) -> list[str]:
        """The event ids of the readable rows where the chain breaks, so a page can mark those rows
        (an unreadable row has no usable id and is counted by unreadable_count())."""
        return list(self.__broken_ids)

    def intact(self) -> bool:
        """True if no row breaks the chain. An empty log is intact."""
        return not self.__breaks

    def summary(self) -> str:
        """One plain sentence for the Verify log result."""
        total = len(self.__rows)
        if total == 0:
            return "No entries yet."
        if self.intact():
            return "No changes found in the 1 entry." if total == 1 else f"No changes found in the {total} entries."
        parts = []
        if self.__mismatches:
            named = ", ".join(str(number) for number in self.__mismatches[:AuditChain.MAX_NAMED])
            more = len(self.__mismatches) - AuditChain.MAX_NAMED
            if len(self.__mismatches) == 1:
                parts.append(f"entry {named} does not match.")
            else:
                parts.append(f"entries {named}{f' and {more} more' if more > 0 else ''} do not match.")
        count = len(self.__unreadable)
        if count:
            parts.append(f"{count} entry can't be read." if count == 1 else f"{count} entries can't be read.")
        return "The log has been changed outside the app: " + " ".join(parts)
