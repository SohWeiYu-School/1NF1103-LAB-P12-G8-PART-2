"""AuditFilter: which audit events to show, and which page of them."""

from collections.abc import Collection, Iterable, Mapping
from datetime import date, datetime, timedelta, timezone

from app.model.audit_event import AuditEvent


class AuditFilter:
    """The filter bar of the activity log: dates, officer, actions, result, client, search text, order and page.

    Dates are Singapore days (UTC+8, which has no daylight saving). Built directly, an impossible value
    raises ValueError. Built from a web address with from_query(), each bad value falls back to its default and
    problems() says why, so the page still shows.
    """

    PRESETS: tuple[str, ...] = ("1", "7", "30", "90", "custom")      # days back from today ("1" = today), or a chosen range
    DEFAULT_PRESET: str = "7"
    RESULT_CHOICES: tuple[str, ...] = ("all", "ok", "failed")
    SORT_CHOICES: tuple[str, ...] = ("desc", "asc")                    # newest first, oldest first
    TRUE_TEXTS: tuple[str, ...] = ("1", "on", "true", "yes")       # a ticked checkbox sends "on"
    FALSE_TEXTS: tuple[str, ...] = ("0", "off", "false", "no")
    PAGE_SIZE: int = 25
    MAX_QUERY: int = 80
    MAX_ACTOR: int = AuditEvent.MAX_ACTOR
    MAX_CLIENT_REF: int = AuditEvent.MAX_CLIENT_REF
    DATE_FORMAT: str = "%Y-%m-%d"
    SINGAPORE: timezone = timezone(timedelta(hours=8))
    # The rules of a custom date range, in words. The web app shows them with SHOWING_ALL added (the page falls
    # back to all dates); the terminal asks again and shows them as they are.
    RULE_BOTH_DATES: str = "Pick both a start and an end date."
    RULE_FUTURE: str = "The dates cannot be in the future."
    SHOWING_ALL: str = " Showing all dates for now."
    PROBLEM_BOTH_DATES: str = RULE_BOTH_DATES + SHOWING_ALL
    PROBLEM_DATE_ORDER: str = "The start date must be on or before the end date." + SHOWING_ALL
    PROBLEM_FUTURE: str = RULE_FUTURE + SHOWING_ALL
    PROBLEM_DATE_FORMAT: str = "The dates must look like 2026-11-15 (year-month-day)." + SHOWING_ALL

    def __init__(self, preset: str = "7", date_from: str = "", date_to: str = "",
                 groups: Iterable[str] | None = None, result: str = "all", actor: str = "",
                 client_ref: str = "", query: str = "", sort: str = "desc", page: int = 1,
                 flagged_only: bool = False) -> None:
        """Raises ValueError, saying what is wrong and what is allowed, for any impossible value. groups
        is None for every group. flagged_only keeps only the events behind a flag (matches() is then told
        which events those are). A custom range with a missing date is allowed and means all dates (the
        web address route turns that into a problem line); a start after the end is not."""
        if preset not in AuditFilter.PRESETS:
            raise ValueError(f"The preset must be one of {', '.join(AuditFilter.PRESETS)} (got {preset!r}).")
        for name, value in (("date_from", date_from), ("date_to", date_to), ("result", result), ("actor", actor),
                            ("client_ref", client_ref), ("query", query), ("sort", sort)):
            if not isinstance(value, str):
                raise ValueError(f"The {name} must be text.")
        first, last = AuditFilter.__check_day(date_from, "start"), AuditFilter.__check_day(date_to, "end")
        if first is not None and last is not None and first > last:
            raise ValueError("The start date must be on or before the end date.")
        chosen = tuple(AuditEvent.GROUPS) if groups is None else AuditFilter.__check_groups(groups)
        if result not in AuditFilter.RESULT_CHOICES:
            raise ValueError(f"The result must be one of {', '.join(AuditFilter.RESULT_CHOICES)} (got {result!r}).")
        if sort not in AuditFilter.SORT_CHOICES:
            raise ValueError(f"The sort must be one of {', '.join(AuditFilter.SORT_CHOICES)} (got {sort!r}).")
        actor, client_ref, query = actor.strip(), client_ref.strip(), " ".join(query.split())
        if len(actor) > AuditFilter.MAX_ACTOR or not actor.isprintable():
            raise ValueError(f"The actor must be printable text of at most {AuditFilter.MAX_ACTOR} characters.")
        if len(client_ref) > AuditFilter.MAX_CLIENT_REF or not client_ref.isprintable():
            raise ValueError(f"The client reference must be printable text of at most "
                             f"{AuditFilter.MAX_CLIENT_REF} characters.")
        if len(query) > AuditFilter.MAX_QUERY or not query.isprintable():
            raise ValueError(f"The search text must be printable text of at most {AuditFilter.MAX_QUERY} characters.")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError(f"The page must be a whole number, 1 or more (got {page!r}).")
        if not isinstance(flagged_only, bool):
            raise ValueError(f"flagged_only must be True or False (got {flagged_only!r}).")
        self.__preset: str = preset
        self.__date_from: str = date_from.strip() if preset == "custom" else ""
        self.__date_to: str = date_to.strip() if preset == "custom" else ""
        self.__dates_ignored: bool = False
        self.__groups: tuple[str, ...] = chosen
        self.__result: str = result
        self.__actor: str = actor
        self.__client_ref: str = client_ref
        self.__query: str = query
        self.__sort: str = sort
        self.__page: int = page
        self.__flagged_only: bool = flagged_only
        self.__problems: list[str] = []

    @staticmethod
    def parse_day(text: str) -> date | None:
        """The date in text (YYYY-MM-DD, exactly), or None if text is not such a date."""
        if not isinstance(text, str) or len(text) != 10 or not text.isascii():
            return None
        try:
            return datetime.strptime(text, AuditFilter.DATE_FORMAT).date()
        except ValueError:
            return None

    @staticmethod
    def range_problem(date_from: str, date_to: str, today: date) -> str:
        """RULE_BOTH_DATES if only one of the two dates is given, RULE_FUTURE if the end is after today (the
        Singapore day), else "". A date that is not YYYY-MM-DD, two blank dates and a start after the end are
        not judged here: the date check and the filter's constructor own those."""
        first, last = AuditFilter.parse_day(date_from), AuditFilter.parse_day(date_to)
        if (date_from and first is None) or (date_to and last is None) or (not date_from and not date_to):
            return ""
        if first is None or last is None:
            return AuditFilter.RULE_BOTH_DATES
        if first <= last and last > today:
            return AuditFilter.RULE_FUTURE
        return ""

    @staticmethod
    def singapore_day(moment: datetime) -> date:
        """The Singapore calendar day of a moment that carries a timezone (ValueError if it does not)."""
        if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("The time must carry a timezone")
        return moment.astimezone(AuditFilter.SINGAPORE).date()

    @staticmethod
    def event_day(event: AuditEvent) -> date:
        """The Singapore day an event happened on."""
        happened = datetime.strptime(event.at, AuditEvent.TIME_FORMAT).replace(tzinfo=timezone.utc)
        return AuditFilter.singapore_day(happened)

    @staticmethod
    def __check_day(text: str, which: str) -> date | None:
        """The date in text, None if it is empty. Raises ValueError if it is not a real YYYY-MM-DD date."""
        text = text.strip()
        if not text:
            return None
        found = AuditFilter.parse_day(text)
        if found is None:
            raise ValueError(f"The {which} date must look like 2026-11-15 (year-month-day) (got {text!r}).")
        return found

    @staticmethod
    def __check_groups(groups: Iterable[str]) -> tuple[str, ...]:
        """The groups in the order AuditEvent lists them. Raises ValueError for none, or one that does not exist."""
        if isinstance(groups, str) or not isinstance(groups, Iterable):
            raise ValueError("The groups must be a list of group names.")
        wanted = list(groups)
        for name in wanted:
            if name not in AuditEvent.GROUPS:
                raise ValueError(f"The group must be one of {', '.join(AuditEvent.GROUPS)} (got {name!r}).")
        if not wanted:
            raise ValueError("At least one group must be chosen.")
        return tuple(name for name in AuditEvent.GROUPS if name in wanted)

    @property
    def preset(self) -> str:
        return self.__preset

    @property
    def date_from(self) -> str:
        return self.__date_from

    @property
    def date_to(self) -> str:
        return self.__date_to

    @property
    def groups(self) -> tuple[str, ...]:
        return self.__groups

    @property
    def result(self) -> str:
        return self.__result

    @property
    def actor(self) -> str:
        return self.__actor

    @property
    def client_ref(self) -> str:
        return self.__client_ref

    @property
    def query(self) -> str:
        return self.__query

    @property
    def sort(self) -> str:
        return self.__sort

    @property
    def page(self) -> int:
        return self.__page

    @property
    def flagged_only(self) -> bool:
        return self.__flagged_only

    def all_groups(self) -> bool:
        """True if every group is chosen (the default)."""
        return len(self.__groups) == len(AuditEvent.GROUPS)

    def problems(self) -> list[str]:
        """Plain lines saying which values from the address were ignored, and why. Empty if all were fine."""
        return list(self.__problems)

    def day_range(self, now: datetime) -> tuple[date, date] | None:
        """(first day, last day) in Singapore days that the dates cover, or None for all dates (a custom
        range that is missing or was ignored). now carries a timezone (ValueError if it does not)."""
        today = AuditFilter.singapore_day(now)
        if self.__preset != "custom":
            return today - timedelta(days=int(self.__preset) - 1), today
        first, last = AuditFilter.parse_day(self.__date_from), AuditFilter.parse_day(self.__date_to)
        if self.__dates_ignored or first is None or last is None:
            return None
        return first, last

    def range_text(self, now: datetime) -> str:
        """The dates covered, for the line before the chips: "9 November 2026 – 15 November 2026"."""
        days = self.day_range(now)
        if days is None:
            return "All dates"
        long = [f"{day.day} {day:%B %Y}" for day in days]
        return long[0] if days[0] == days[1] else f"{long[0]} – {long[1]}"

    def period_text(self, now: datetime) -> str:
        """The start of the headline sentence: "Today", "In the last 7 days", "9 Nov to 15 Nov" or "On all dates"."""
        if self.__preset == "1":
            return "Today"
        if self.__preset != "custom":
            return f"In the last {self.__preset} days"
        days = self.day_range(now)
        if days is None:
            return "On all dates"
        short = [f"{day.day} {day:%b}" for day in days]
        return short[0] if days[0] == days[1] else f"{short[0]} to {short[1]}"

    @staticmethod
    def from_query(args: Mapping, now: datetime | None = None) -> "AuditFilter":
        """Build a filter from the values in a web address (all text; "group" may be given several times).
        A missing value is the default; a bad value is replaced by the default and explained in problems().
        Never raises for bad values; raises ValueError only if args is not a mapping or now has no timezone.
        now (the moment used to refuse dates in the future) is the current time if not given."""
        if not isinstance(args, Mapping):
            raise ValueError("The filter values must come as a mapping of names to text.")
        now = now or datetime.now(timezone.utc)
        today = AuditFilter.singapore_day(now)
        problems: list[str] = []

        def given(name: str) -> str | None:
            """The trimmed text for a name; None if it is missing or empty; "\\0" if it is not text."""
            value = args.get(name)
            if value is None:
                return None
            if not isinstance(value, str):
                return "\0"
            return value.strip() or None

        def many(name: str) -> list[str]:
            """Every value given for a name (the web address may repeat it)."""
            values = args.getlist(name) if hasattr(args, "getlist") else args.get(name)
            if values is None:
                return []
            if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
                values = [values]
            return [value.strip() if isinstance(value, str) else "\0" for value in values]

        preset = AuditFilter.DEFAULT_PRESET
        text = given("preset")
        if text is not None:
            if text.lower() in AuditFilter.PRESETS:
                preset = text.lower()
            else:
                problems.append(f"'preset' must be one of {', '.join(AuditFilter.PRESETS)}; "
                                f"showing the last {AuditFilter.DEFAULT_PRESET} days.")
        date_from, date_to, ignored = "", "", False
        if preset == "custom":
            first_text, last_text = given("from") or "", given("to") or ""
            date_from, date_to = first_text, last_text
            first, last = AuditFilter.parse_day(first_text), AuditFilter.parse_day(last_text)
            if (first_text and first is None) or (last_text and last is None):
                problems.append(AuditFilter.PROBLEM_DATE_FORMAT)
                date_from, date_to, ignored = "", "", True
            elif not first_text and not last_text:
                ignored = True                     # Custom was just picked: all dates until both are chosen
            elif (rule := AuditFilter.range_problem(date_from, date_to, today)) == AuditFilter.RULE_BOTH_DATES:
                problems.append(rule + AuditFilter.SHOWING_ALL)
                ignored = True
            elif first > last:
                problems.append(AuditFilter.PROBLEM_DATE_ORDER)
                ignored = True
            elif rule:
                problems.append(rule + AuditFilter.SHOWING_ALL)
                ignored = True
        groups: list[str] = []
        for text in many("group"):
            match = next((name for name in AuditEvent.GROUPS if name.lower() == text.lower()), "")
            if match:
                groups.append(match)
            elif text:
                problems.append(f"'group' must be one of {', '.join(AuditEvent.GROUPS)}; ignoring that value.")
        actor = ""
        text = given("actor")
        if text is not None:
            if len(text) > AuditFilter.MAX_ACTOR or not text.isprintable():
                problems.append(f"'actor' must be printable text of at most {AuditFilter.MAX_ACTOR} characters; "
                                "showing every officer.")
            else:
                actor = text
        client_ref = ""
        text = given("client_ref")
        if text is not None:
            if len(text) > AuditFilter.MAX_CLIENT_REF or not text.isprintable():
                problems.append(f"'client_ref' must be printable text of at most {AuditFilter.MAX_CLIENT_REF} "
                                "characters; showing every client.")
            else:
                client_ref = text
        query = ""
        text = given("q")
        if text is not None:
            text = " ".join(text.split())
            if len(text) > AuditFilter.MAX_QUERY or not text.isprintable():
                problems.append(f"'q' must be printable text of at most {AuditFilter.MAX_QUERY} characters; "
                                "not searching.")
            else:
                query = text
        result = "all"
        text = given("result")
        if text is not None:
            if text.lower() in AuditFilter.RESULT_CHOICES:
                result = text.lower()
            else:
                problems.append("'result' must be all, ok or failed; showing all.")
        sort = "desc"
        text = given("sort")
        if text is not None:
            if text.lower() in AuditFilter.SORT_CHOICES:
                sort = text.lower()
            else:
                problems.append("'sort' must be desc (newest first) or asc (oldest first); showing newest first.")
        page = 1
        text = given("page")
        if text is not None:
            if text.isascii() and text.isdigit() and len(text) <= 9 and int(text) >= 1:
                page = int(text)
            else:
                problems.append("'page' must be a whole number, 1 or more; showing page 1.")
        flagged_only = False
        text = given("flagged")
        if text is not None:
            if text.lower() in AuditFilter.TRUE_TEXTS:
                flagged_only = True
            elif text.lower() not in AuditFilter.FALSE_TEXTS:
                problems.append("'flagged' must be 1 or 0; showing all events.")
        # A start after the end cannot be built; it is kept for the page's date boxes and ignored when matching.
        audit_filter = AuditFilter(preset, "" if ignored else date_from, "" if ignored else date_to,
                                   groups or None, result, actor, client_ref, query, sort, page, flagged_only)
        if ignored and preset == "custom":
            audit_filter.__date_from, audit_filter.__date_to = date_from, date_to
        audit_filter.__dates_ignored = ignored
        audit_filter.__problems = problems
        return audit_filter

    def matches(self, event: AuditEvent, now: datetime, flagged: Collection[int] | None = None) -> bool:
        """True if the event passes every active filter. now (passed in, so the answer is repeatable)
        must carry a timezone (ValueError if it does not). flagged is the set of entry numbers that are
        behind a flag; only the model's caller can know it. It is needed when flagged_only is on (ValueError
        if it is missing, so "flagged only" never quietly shows everything) and ignored otherwise."""
        if self.__flagged_only:
            if flagged is None:
                raise ValueError("The flagged entries must be given when only flagged events are wanted.")
            if event.sequence not in flagged:
                return False
        days = self.day_range(now)
        if days is not None and not days[0] <= AuditFilter.event_day(event) <= days[1]:
            return False
        if self.__actor and event.actor.casefold() != self.__actor.casefold():
            return False
        if event.group not in self.__groups:
            return False
        if self.__result != "all" and event.result != self.__result:
            return False
        if self.__client_ref and event.client_ref.casefold() != self.__client_ref.casefold():
            return False
        return not self.__query or self.__query.casefold() in AuditFilter.__searchable(event)

    @staticmethod
    def __searchable(event: AuditEvent) -> str:
        """The text the search box looks in, in lower case: who, which client, the label, the summary, the
        file and the names of the fields that changed."""
        details = event.details
        parts = [event.actor, event.client_ref, event.label, event.summary()]
        file_id = details.get("file_id")
        if isinstance(file_id, str):
            parts.append(file_id)
        changes = details.get("changes")
        if isinstance(changes, list):
            parts.extend(change.get("field", "") for change in changes
                         if isinstance(change, dict) and isinstance(change.get("field", ""), str))
        return " ".join(parts).casefold()

    def page_count(self, total: int) -> int:
        """How many pages hold this many events (at least 1, so an empty log still has a page 1)."""
        return max(1, -(-max(total, 0) // AuditFilter.PAGE_SIZE))

    def page_for(self, total: int) -> int:
        """The page actually shown for this many events: the chosen page, or the last page if the
        chosen one is past the end."""
        return min(self.__page, self.page_count(total))

    def page_of(self, events: list[AuditEvent]) -> list[AuditEvent]:
        """The events on the page page_for() gives, in the order given."""
        page = self.page_for(len(events))
        start = (page - 1) * AuditFilter.PAGE_SIZE
        return events[start:start + AuditFilter.PAGE_SIZE]

    def to_query(self) -> dict[str, str | list[str]]:
        """Only the values that are not the default, as text for a web address (groups as a list)."""
        query: dict[str, str | list[str]] = {}
        if self.__preset != AuditFilter.DEFAULT_PRESET:
            query["preset"] = self.__preset
        if self.__preset == "custom":
            if self.__date_from:
                query["from"] = self.__date_from
            if self.__date_to:
                query["to"] = self.__date_to
        if not self.all_groups():
            query["group"] = list(self.__groups)
        for name, value in (("actor", self.__actor), ("client_ref", self.__client_ref), ("q", self.__query)):
            if value:
                query[name] = value
        if self.__result != "all":
            query["result"] = self.__result
        if self.__sort != "desc":
            query["sort"] = self.__sort
        if self.__flagged_only:
            query["flagged"] = "1"
        if self.__page > 1:
            query["page"] = str(self.__page)
        return query

    def chips(self) -> list[tuple[str, str]]:
        """(the web address name that removes it, text) for each active filter that is not the default, for
        the chips above the table. The dates have no chip: the line before the chips says them."""
        chips: list[tuple[str, str]] = []
        if self.__actor:
            chips.append(("actor", f"Officer: {self.__actor}"))
        if not self.all_groups():
            chips.append(("group", f"Actions: {', '.join(self.__groups)}"))
        if self.__client_ref:
            chips.append(("client_ref", f"Client: {self.__client_ref.upper()}"))
        if self.__result != "all":
            chips.append(("result", "Failed only" if self.__result == "failed" else "OK only"))
        if self.__flagged_only:
            chips.append(("flagged", "Flagged only"))
        if self.__query:
            chips.append(("q", f"Search: “{self.__query}”"))
        return chips
