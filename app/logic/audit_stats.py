"""AuditStats: the counts behind the Overview page (actions, failures, flags to handle, flags by type)."""

import math
from datetime import date, datetime, timedelta

from app.logic.audit_insights import AuditInsights
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.flag import Flag
from app.model.flag_ticket import FlagTicket


class AuditStats:
    """Counts for one date range (Singapore days, both ends included) and the range of the same length
    just before it. Pure: nothing is read or written here, and the same inputs give the same numbers.

    "Flags to handle", "not started" and "in progress" count every flag whatever the date range (a flag
    stays until it is resolved). "Flags by type" counts the unresolved flags raised in the range.
    A flag with no ticket in the tickets dict has no updates yet, so it is Open.
    """

    SEVERITY_ORDER: tuple[str, ...] = ("high", "medium", "low")

    def __init__(self, events: list[AuditEvent] | None = None, flags: list[Flag] | None = None,
                 tickets: dict[str, FlagTicket] | None = None, day_from: date | None = None,
                 day_to: date | None = None, now: datetime | None = None) -> None:
        """events are the log's events; flags are the rules' flags; tickets map a flag id to its ticket.
        With no day_from and day_to the range is the one Singapore day of now (or 1 Jan 1970 if there is
        no now). Raises ValueError for a wrong type or a range that ends before it starts."""
        events = [] if events is None else events
        flags = [] if flags is None else flags
        tickets = {} if tickets is None else tickets
        if not isinstance(events, list) or any(not isinstance(event, AuditEvent) for event in events):
            raise ValueError("The events must be a list of audit events.")
        if not isinstance(flags, list) or any(not isinstance(flag, Flag) for flag in flags):
            raise ValueError("The flags must be a list of flags.")
        if (not isinstance(tickets, dict)
                or any(not isinstance(key, str) or not isinstance(ticket, FlagTicket) for key, ticket in tickets.items())):
            raise ValueError("The tickets must be a dict of flag id to ticket.")
        if now is not None and (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None):
            raise ValueError("now must be a time that carries a timezone.")
        fallback = AuditFilter.singapore_day(now) if now else date(1970, 1, 1)
        day_from = fallback if day_from is None else day_from
        day_to = fallback if day_to is None else day_to
        for name, day in (("day_from", day_from), ("day_to", day_to)):
            if isinstance(day, datetime) or not isinstance(day, date):
                raise ValueError(f"{name} must be a date.")
        if day_to < day_from:
            raise ValueError("The range must not end before it starts.")
        self.__events: list[AuditEvent] = list(events)
        self.__flags: list[Flag] = list(flags)
        self.__tickets: dict[str, FlagTicket] = dict(tickets)
        self.__day_from: date = day_from
        self.__day_to: date = day_to
        self.__length: int = (day_to - day_from).days + 1
        self.__before_from: date = day_from - timedelta(days=self.__length)
        self.__before_to: date = day_from - timedelta(days=1)
        self.__days: list[date] = [AuditFilter.event_day(event) for event in self.__events]

    @property
    def day_from(self) -> date:
        return self.__day_from

    @property
    def day_to(self) -> date:
        return self.__day_to

    @property
    def length(self) -> int:
        """How many days the range has (the earlier range has the same number)."""
        return self.__length

    @property
    def has_previous(self) -> bool:
        """True if the log reaches back before the earlier range starts, so comparing with it is fair.
        False when the earlier range begins before the first event (or there are no events)."""
        return bool(self.__days) and min(self.__days) <= self.__before_from

    def __count(self, first: date, last: date, failures_only: bool) -> int:
        return sum(1 for event, day in zip(self.__events, self.__days)
                   if first <= day <= last and (not failures_only or AuditInsights.failure_kind(event)))

    @property
    def actions(self) -> int:
        """How many log lines fall in the range."""
        return self.__count(self.__day_from, self.__day_to, False)

    @property
    def actions_before(self) -> int:
        """How many log lines fall in the range just before."""
        return self.__count(self.__before_from, self.__before_to, False)

    @property
    def failures(self) -> int:
        """How many failures (see AuditInsights.failure_kind) fall in the range."""
        return self.__count(self.__day_from, self.__day_to, True)

    @property
    def failures_before(self) -> int:
        return self.__count(self.__before_from, self.__before_to, True)

    def change_percent(self, now_count: int, before_count: int) -> int | None:
        """The change from before_count to now_count as a whole percent of before_count (rounded half
        up away from zero; negative for a fall), or None when it means nothing: there is no earlier
        range to compare with (has_previous is False) or before_count is 0."""
        for count in (now_count, before_count):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("Counts must be whole numbers, 0 or more.")
        if not self.has_previous or before_count == 0:
            return None
        size = math.floor(abs(now_count - before_count) / before_count * 100 + 0.5)
        return -size if now_count < before_count else size

    def failures_by_day(self) -> list[tuple[date, dict[str, int]]]:
        """Every day of the range, in order, with the failures of that day by kind (every kind present,
        0 when none)."""
        by_day = {day: {kind: 0 for kind in AuditInsights.FAILURE_KINDS} for day in
                  (self.__day_from + timedelta(days=offset) for offset in range(self.__length))}
        for event, day in zip(self.__events, self.__days):
            kind = AuditInsights.failure_kind(event)
            if kind and day in by_day:
                by_day[day][kind] += 1
        return list(by_day.items())

    def __status(self, flag: Flag) -> str:
        ticket = self.__tickets.get(flag.flag_id)
        return ticket.status if ticket else "open"

    @property
    def to_handle(self) -> int:
        """Flags that are not resolved, whatever the date range."""
        return sum(1 for flag in self.__flags if self.__status(flag) != "resolved")

    @property
    def not_started(self) -> int:
        """Flags still Open."""
        return sum(1 for flag in self.__flags if self.__status(flag) == "open")

    @property
    def in_progress(self) -> int:
        """Flags In review or Following up."""
        return sum(1 for flag in self.__flags if self.__status(flag) in ("review", "followup"))

    def __open_in_range(self) -> list[Flag]:
        return [flag for flag in self.__flags if self.__status(flag) != "resolved"
                and self.__day_from <= AuditFilter.singapore_day(datetime.fromisoformat(flag.raised_at))
                <= self.__day_to]

    @property
    def open_flags_in_range(self) -> int:
        """Unresolved flags raised in the range."""
        return len(self.__open_in_range())

    def flags_by_type(self) -> list[tuple[str, str, int, int]]:
        """The unresolved flags raised in the range, counted by kind: (kind, name, count, percent of
        those flags, rounded half up), most first; kinds with the same count go in order of the
        priority of their first flag (high first), then in the order of Flag.KINDS. Empty if none."""
        open_flags = self.__open_in_range()
        counts: dict[str, int] = {}
        for flag in open_flags:
            counts[flag.kind] = counts.get(flag.kind, 0) + 1
        severity = self.type_severity()
        ordered = sorted(counts, key=lambda kind: (-counts[kind], AuditStats.SEVERITY_ORDER.index(severity[kind]),
                                                   Flag.KINDS.index(kind)))
        return [(kind, Flag.NAMES[kind], counts[kind], math.floor(counts[kind] / len(open_flags) * 100 + 0.5))
                for kind in ordered]

    def type_severity(self) -> dict[str, str]:
        """The priority of each kind among the unresolved flags in the range, taken from the first flag
        of that kind in the list given."""
        found: dict[str, str] = {}
        for flag in self.__open_in_range():
            found.setdefault(flag.kind, flag.severity)
        return found

    def severity_counts(self) -> dict[str, int]:
        """The unresolved flags raised in the range by priority: {"high": n, "medium": n, "low": n}."""
        counts = {severity: 0 for severity in AuditStats.SEVERITY_ORDER}
        for flag in self.__open_in_range():
            counts[flag.severity] += 1
        return counts
