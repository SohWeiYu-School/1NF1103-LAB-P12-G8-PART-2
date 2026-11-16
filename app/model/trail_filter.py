"""TrailFilter: which events of one client's History to show."""

from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone

from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter


class TrailFilter:
    """The Show and When choices above a client's History.

    Built directly, an impossible value raises ValueError. Built from a web address with from_query(), each bad
    value falls back to its default and problems() says why, so the page still shows.
    """

    SHOW: dict[str, tuple[str, ...]] = {          # the choice -> the audit groups it shows
        "all": tuple(AuditEvent.GROUPS), "edits": ("Client",), "assessments": ("Assessment",),
        "documents": ("Documents",)}
    SHOW_LABELS: dict[str, str] = {"all": "All", "edits": "Edits", "assessments": "Assessments",
                                   "documents": "Documents"}
    WHEN: tuple[str, ...] = ("all", "7", "30", "90", "custom")
    WHEN_LABELS: dict[str, str] = {"all": "All time", "7": "Last 7 days", "30": "Last 30 days",
                                   "90": "Last 90 days", "custom": "Pick dates…"}

    def __init__(self, show: str = "all", when: str = "all", date_from: str = "", date_to: str = "") -> None:
        """Raises ValueError, saying what is wrong and what is allowed, for any impossible value. Like
        AuditFilter, a custom range with a missing date means all dates; a start after the end is refused."""
        if show not in TrailFilter.SHOW:
            raise ValueError(f"The show choice must be one of {', '.join(TrailFilter.SHOW)} (got {show!r}).")
        if when not in TrailFilter.WHEN:
            raise ValueError(f"The when choice must be one of {', '.join(TrailFilter.WHEN)} (got {when!r}).")
        if not isinstance(date_from, str) or not isinstance(date_to, str):
            raise ValueError("The dates must be text.")
        first, last = date_from.strip(), date_to.strip()
        for text in (first, last):
            if text and AuditFilter.parse_day(text) is None:
                raise ValueError(f"The dates must look like 2026-11-15 (year-month-day) (got {text!r}).")
        if first and last and first > last:
            raise ValueError("The start date must be on or before the end date.")
        self.__show: str = show
        self.__when: str = when
        self.__date_from: str = first if when == "custom" else ""
        self.__date_to: str = last if when == "custom" else ""
        self.__dates_ignored: bool = False
        self.__problems: list[str] = []

    @property
    def show(self) -> str:
        return self.__show

    @property
    def when(self) -> str:
        return self.__when

    @property
    def date_from(self) -> str:
        return self.__date_from

    @property
    def date_to(self) -> str:
        return self.__date_to

    def problems(self) -> list[str]:
        """Plain lines saying which values from the address were ignored, and why. Empty if all were fine."""
        return list(self.__problems)

    @staticmethod
    def from_query(args: Mapping, now: datetime | None = None) -> "TrailFilter":
        """Build a filter from the values in a web address ("show", "when", "from", "to"). Never raises for
        bad values; raises ValueError only if args is not a mapping or now has no timezone."""
        if not isinstance(args, Mapping):
            raise ValueError("The filter values must come as a mapping of names to text.")
        today = AuditFilter.singapore_day(now or datetime.now(timezone.utc))
        problems: list[str] = []

        def given(name: str) -> str | None:
            value = args.get(name)
            if value is None:
                return None
            return value.strip() or None if isinstance(value, str) else "\0"

        show, when = "all", "all"
        text = given("show")
        if text is not None:
            if text.lower() in TrailFilter.SHOW:
                show = text.lower()
            else:
                problems.append(f"'show' must be one of {', '.join(TrailFilter.SHOW)}; showing all.")
        text = given("when")
        if text is not None:
            if text.lower() in TrailFilter.WHEN:
                when = text.lower()
            else:
                problems.append(f"'when' must be one of {', '.join(TrailFilter.WHEN)}; showing all time.")
        date_from, date_to, ignored = "", "", False
        if when == "custom":
            date_from, date_to = given("from") or "", given("to") or ""
            first, last = AuditFilter.parse_day(date_from), AuditFilter.parse_day(date_to)
            if (date_from and first is None) or (date_to and last is None):
                problems.append(AuditFilter.PROBLEM_DATE_FORMAT)
                date_from, date_to, ignored = "", "", True
            elif first is None or last is None:
                problems.append(AuditFilter.PROBLEM_BOTH_DATES)
                ignored = True
            elif first > last:
                problems.append(AuditFilter.PROBLEM_DATE_ORDER)
                ignored = True
            elif last > today:
                problems.append(AuditFilter.PROBLEM_FUTURE)
                ignored = True
        trail_filter = TrailFilter(show, when, "" if ignored else date_from, "" if ignored else date_to)
        if ignored and when == "custom":
            trail_filter.__date_from, trail_filter.__date_to = date_from, date_to
        trail_filter.__dates_ignored = ignored
        trail_filter.__problems = problems
        return trail_filter

    def day_range(self, now: datetime) -> tuple[date, date] | None:
        """(first day, last day) in Singapore days, or None for all time (or dates that were ignored)."""
        today = AuditFilter.singapore_day(now)
        if self.__when == "all":
            return None
        if self.__when != "custom":
            return today - timedelta(days=int(self.__when) - 1), today
        first, last = AuditFilter.parse_day(self.__date_from), AuditFilter.parse_day(self.__date_to)
        if self.__dates_ignored or first is None or last is None:
            return None
        return first, last

    def matches(self, event: AuditEvent, now: datetime) -> bool:
        """True if the event is of a group chosen by Show and on a day chosen by When. now must carry a
        timezone (ValueError if it does not)."""
        if event.group not in TrailFilter.SHOW[self.__show]:
            return False
        days = self.day_range(now)
        return days is None or days[0] <= AuditFilter.event_day(event) <= days[1]

    def to_query(self) -> dict[str, str]:
        """Only the values that are not the default, as text for a web address."""
        query: dict[str, str] = {}
        if self.__show != "all":
            query["show"] = self.__show
        if self.__when != "all":
            query["when"] = self.__when
        if self.__when == "custom":
            for name, value in (("from", self.__date_from), ("to", self.__date_to)):
                if value:
                    query[name] = value
        return query
