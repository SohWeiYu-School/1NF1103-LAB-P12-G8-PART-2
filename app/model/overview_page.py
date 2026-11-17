"""OverviewPage: everything the admin Overview page shows, worked out once and checked."""

from datetime import date, datetime

from app.model.flag import Flag
from app.model.flag_ticket import FlagTicket


class OverviewPage:
    """The Overview numbers for one date range, and one page of the flags table. Read-only: App builds it,
    the page only shows it (templates get the object and read its properties).

    The range is a preset ("today", "7", "30" or "90" days back from today) with the Singapore days it
    covers. The flag numbers (to_handle, not_started, in_progress, the tab counts) cover every flag
    whatever the range; the severity counts and flags_by_type cover the unresolved flags raised in the
    range. A change figure is None when it means nothing (nothing to compare with).
    """

    PRESETS: tuple[str, ...] = ("today", "7", "30", "90")
    DEFAULT_PRESET: str = "7"
    TABS: tuple[str, ...] = ("handle", "open", "review", "followup", "resolved", "all")
    TAB_NAMES: dict[str, str] = {"handle": "To handle", "open": "Open", "review": "In review",
                                 "followup": "Following up", "resolved": "Resolved", "all": "All"}
    DEFAULT_TAB: str = "handle"
    PAGE_SIZE: int = 6
    SEVERITIES: tuple[str, ...] = ("high", "medium", "low")

    def __init__(self, preset: str = "7", day_from: date = date(1970, 1, 1), day_to: date = date(1970, 1, 1),
                 to_handle: int = 0, not_started: int = 0, in_progress: int = 0, actions: int = 0,
                 actions_change: int | None = None, failures: int = 0, failures_change: int | None = None,
                 broken_at: int = 0, failures_by_day: list[tuple[str, dict[str, int]]] | None = None,
                 flags_by_type: list[tuple[str, str, int, int]] | None = None,
                 severity_counts: dict[str, int] | None = None, tab: str = "handle",
                 tab_counts: dict[str, int] | None = None, rows: list[FlagTicket] | None = None,
                 page: int = 1, page_count: int = 1, unreadable: int = 0,
                 type_severity: dict[str, str] | None = None) -> None:
        """Raises ValueError, saying what is wrong and what is allowed, for any impossible value."""
        failures_by_day = [] if failures_by_day is None else failures_by_day
        flags_by_type = [] if flags_by_type is None else flags_by_type
        severity_counts = {name: 0 for name in OverviewPage.SEVERITIES} if severity_counts is None else severity_counts
        tab_counts = {name: 0 for name in OverviewPage.TABS} if tab_counts is None else tab_counts
        rows = [] if rows is None else rows
        type_severity = {} if type_severity is None else type_severity
        if preset not in OverviewPage.PRESETS:
            raise ValueError(f"The range must be one of {', '.join(OverviewPage.PRESETS)} (got {preset!r}).")
        if tab not in OverviewPage.TABS:
            raise ValueError(f"The tab must be one of {', '.join(OverviewPage.TABS)} (got {tab!r}).")
        for name, day in (("day_from", day_from), ("day_to", day_to)):
            if isinstance(day, datetime) or not isinstance(day, date):
                raise ValueError(f"The {name} must be a date.")
        if day_to < day_from:
            raise ValueError("The range must not end before it starts.")
        for name, value in (("to_handle", to_handle), ("not_started", not_started), ("in_progress", in_progress),
                            ("actions", actions), ("failures", failures), ("broken_at", broken_at),
                            ("unreadable", unreadable)):
            OverviewPage.__check_count(name, value, 0)
        for name, value in (("actions_change", actions_change), ("failures_change", failures_change)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError(f"The {name} must be a whole number or None (got {value!r}).")
        if to_handle != not_started + in_progress:
            raise ValueError("The flags to handle must be the not started flags plus the in progress ones.")
        OverviewPage.__check_count("page", page, 1)
        OverviewPage.__check_count("page_count", page_count, 1)
        if page > page_count:
            raise ValueError(f"The page ({page}) cannot be past the last page ({page_count}).")
        OverviewPage.__check_days(failures_by_day)
        OverviewPage.__check_types(flags_by_type)
        if (not isinstance(type_severity, dict) or set(type_severity) != {entry[0] for entry in flags_by_type}
                or any(value not in OverviewPage.SEVERITIES for value in type_severity.values())):
            raise ValueError("The type severity must give the priority (high, medium or low) of each kind "
                             "in the flags by type, and of no other kind.")
        OverviewPage.__check_counts("severity_counts", severity_counts, OverviewPage.SEVERITIES)
        OverviewPage.__check_counts("tab_counts", tab_counts, OverviewPage.TABS)
        if not isinstance(rows, list) or not all(isinstance(row, FlagTicket) for row in rows):
            raise ValueError("The rows must be a list of flag tickets.")
        if len(rows) > OverviewPage.PAGE_SIZE:
            raise ValueError(f"A page holds at most {OverviewPage.PAGE_SIZE} flags (got {len(rows)}).")
        self.__preset: str = preset
        self.__day_from: date = day_from
        self.__day_to: date = day_to
        self.__to_handle: int = to_handle
        self.__not_started: int = not_started
        self.__in_progress: int = in_progress
        self.__actions: int = actions
        self.__actions_change: int | None = actions_change
        self.__failures: int = failures
        self.__failures_change: int | None = failures_change
        self.__broken_at: int = broken_at
        self.__failures_by_day: list[tuple[str, dict[str, int]]] = [(day, dict(kinds)) for day, kinds in failures_by_day]
        self.__flags_by_type: list[tuple[str, str, int, int]] = [tuple(entry) for entry in flags_by_type]
        self.__severity_counts: dict[str, int] = dict(severity_counts)
        self.__tab: str = tab
        self.__tab_counts: dict[str, int] = dict(tab_counts)
        self.__rows: list[FlagTicket] = list(rows)
        self.__page: int = page
        self.__page_count: int = page_count
        self.__unreadable: int = unreadable
        self.__type_severity: dict[str, str] = dict(type_severity)

    @staticmethod
    def __check_count(name: str, value: object, low: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < low:
            raise ValueError(f"The {name} must be a whole number, {low} or more (got {value!r}).")

    @staticmethod
    def __check_counts(name: str, counts: object, keys: tuple[str, ...]) -> None:
        if not isinstance(counts, dict) or set(counts) != set(keys):
            raise ValueError(f"The {name} must have exactly these keys: {', '.join(keys)}.")
        for key, value in counts.items():
            OverviewPage.__check_count(f"{name}[{key}]", value, 0)

    @staticmethod
    def __check_days(days: object) -> None:
        if not isinstance(days, list):
            raise ValueError("The failures by day must be a list of (day, counts).")
        for entry in days:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise ValueError("Each failures-by-day entry must be (day, counts).")
            day, kinds = entry
            if not isinstance(day, str) or len(day) != 10 or not day.isascii():
                raise ValueError(f"Each day must be text like 2026-11-15 (got {day!r}).")
            try:
                datetime.strptime(day, "%Y-%m-%d")
            except ValueError as error:
                raise ValueError(f"Each day must be a real date like 2026-11-15 (got {day!r}).") from error
            if not isinstance(kinds, dict) or any(not isinstance(kind, str) for kind in kinds):
                raise ValueError("Each day's failures must be a dict of kind name to count.")
            for kind, count in kinds.items():
                OverviewPage.__check_count(f"failure count for {kind}", count, 0)

    @staticmethod
    def __check_types(entries: object) -> None:
        if not isinstance(entries, list):
            raise ValueError("The flags by type must be a list of (kind, name, count, percent).")
        for entry in entries:
            if not isinstance(entry, (tuple, list)) or len(entry) != 4:
                raise ValueError("Each flags-by-type entry must be (kind, name, count, percent).")
            kind, name, count, percent = entry
            if kind not in Flag.KINDS or not isinstance(name, str) or not name:
                raise ValueError(f"Each flags-by-type entry needs a known kind and a name (got {kind!r}).")
            OverviewPage.__check_count("flag count", count, 1)
            OverviewPage.__check_count("flag percent", percent, 0)
            if percent > 100:
                raise ValueError("A flag percent cannot be more than 100.")

    @property
    def preset(self) -> str:
        return self.__preset

    @property
    def day_from(self) -> date:
        return self.__day_from

    @property
    def day_to(self) -> date:
        return self.__day_to

    @property
    def to_handle(self) -> int:
        return self.__to_handle

    @property
    def open_flags(self) -> int:
        """The number on the header's Overview badge: the flags still to handle."""
        return self.__to_handle

    @property
    def not_started(self) -> int:
        return self.__not_started

    @property
    def in_progress(self) -> int:
        return self.__in_progress

    @property
    def actions(self) -> int:
        return self.__actions

    @property
    def actions_change(self) -> int | None:
        return self.__actions_change

    @property
    def failures(self) -> int:
        return self.__failures

    @property
    def failures_change(self) -> int | None:
        return self.__failures_change

    @property
    def broken_at(self) -> int:
        """The first entry that does not match the chain; 0 when the log is intact."""
        return self.__broken_at

    @property
    def intact(self) -> bool:
        return self.__broken_at == 0

    @property
    def failures_by_day(self) -> list[tuple[str, dict[str, int]]]:
        return [(day, dict(kinds)) for day, kinds in self.__failures_by_day]

    @property
    def flags_by_type(self) -> list[tuple[str, str, int, int]]:
        return list(self.__flags_by_type)

    @property
    def severity_counts(self) -> dict[str, int]:
        return dict(self.__severity_counts)

    @property
    def tab(self) -> str:
        return self.__tab

    @property
    def tab_counts(self) -> dict[str, int]:
        return dict(self.__tab_counts)

    @property
    def rows(self) -> list[FlagTicket]:
        """The tickets on this page (each holds its flag as .flag), in the order shown."""
        return list(self.__rows)

    @property
    def page(self) -> int:
        return self.__page

    @property
    def page_count(self) -> int:
        return self.__page_count

    @property
    def unreadable(self) -> int:
        """How many log lines could not be read, so the numbers may be missing them."""
        return self.__unreadable

    @property
    def type_severity(self) -> dict[str, str]:
        """The priority ("high", "medium" or "low") of each kind in flags_by_type."""
        return dict(self.__type_severity)
