"""AuditFilter: which audit events to show, and which page of them."""

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from app.model.audit_event import AuditEvent


class AuditFilter:
    """The filter bar of the audit log: period, officer, group, client, result and page.

    Built directly, a bad value raises ValueError. Built from a web address with from_query(),
    each bad value falls back to its default and problems() says why, so the page still shows.
    """

    DEFAULT_DAYS: int = 7
    DAY_CHOICES: tuple[int, ...] = (1, 7, 30, 90, 0)          # 0 = all time
    PAGE_SIZE: int = 50
    RESULT_CHOICES: tuple[str, ...] = ("", "ok", "failed")
    MAX_ACTOR: int = AuditEvent.MAX_ACTOR
    MAX_CLIENT_REF: int = AuditEvent.MAX_CLIENT_REF

    def __init__(self, days: int = 7, actor: str = "", group: str = "", client_ref: str = "",
                 result: str = "", page: int = 1) -> None:
        """Raises ValueError, saying what is wrong and what is allowed, for any impossible value."""
        if isinstance(days, bool) or days not in AuditFilter.DAY_CHOICES:
            raise ValueError("The days must be one of 1, 7, 30, 90 or 0 (0 means all time).")
        for name, value in (("actor", actor), ("group", group), ("client_ref", client_ref), ("result", result)):
            if not isinstance(value, str):
                raise ValueError(f"The {name} must be text.")
        actor, client_ref = actor.strip(), client_ref.strip()
        if len(actor) > AuditFilter.MAX_ACTOR or not actor.isprintable():
            raise ValueError(f"The actor must be printable text of at most {AuditFilter.MAX_ACTOR} characters.")
        if len(client_ref) > AuditFilter.MAX_CLIENT_REF or not client_ref.isprintable():
            raise ValueError(f"The client reference must be printable text of at most "
                             f"{AuditFilter.MAX_CLIENT_REF} characters.")
        if group and group not in AuditEvent.GROUPS:
            raise ValueError(f"The group must be empty or one of {', '.join(AuditEvent.GROUPS)} (got {group!r}).")
        if result not in AuditFilter.RESULT_CHOICES:
            raise ValueError("The result must be empty, ok or failed.")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError(f"The page must be a whole number, 1 or more (got {page!r}).")
        self.__days: int = days
        self.__actor: str = actor
        self.__group: str = group
        self.__client_ref: str = client_ref
        self.__result: str = result
        self.__page: int = page
        self.__problems: list[str] = []

    @property
    def days(self) -> int:
        return self.__days

    @property
    def actor(self) -> str:
        return self.__actor

    @property
    def group(self) -> str:
        return self.__group

    @property
    def client_ref(self) -> str:
        return self.__client_ref

    @property
    def result(self) -> str:
        return self.__result

    @property
    def page(self) -> int:
        return self.__page

    def problems(self) -> list[str]:
        """Plain lines saying which values from the address were ignored, and why. Empty if all were fine."""
        return list(self.__problems)

    @staticmethod
    def from_query(args: dict) -> "AuditFilter":
        """Build a filter from the values in a web address (all text). A missing value is the default;
        a bad value is replaced by the default and explained in problems(). Never raises for bad values;
        raises ValueError only if args is not a mapping."""
        if not isinstance(args, Mapping):
            raise ValueError("The filter values must come as a mapping of names to text.")
        problems: list[str] = []

        def given(name: str) -> str | None:
            """The trimmed text for a name; None if it is missing or empty; "\\0" if it is not text."""
            value = args.get(name)
            if value is None:
                return None
            if not isinstance(value, str):
                return "\0"
            return value.strip() or None

        days = AuditFilter.DEFAULT_DAYS
        text = given("days")
        if text is not None:
            if text.lower() == "all":
                days = 0
            elif text.isascii() and text.isdigit() and len(text) <= 3 and int(text) in AuditFilter.DAY_CHOICES and int(text) != 0:
                days = int(text)
            else:
                problems.append("'days' must be one of 1, 7, 30, 90 or all; "
                                f"showing the last {AuditFilter.DEFAULT_DAYS} days.")
        actor = ""
        text = given("actor")
        if text is not None:
            if len(text) > AuditFilter.MAX_ACTOR or not text.isprintable():
                problems.append(f"'actor' must be printable text of at most {AuditFilter.MAX_ACTOR} characters; "
                                "showing every officer.")
            else:
                actor = text
        group = ""
        text = given("group")
        if text is not None:
            match = next((name for name in AuditEvent.GROUPS if name.lower() == text.lower()), "")
            if match:
                group = match
            else:
                problems.append(f"'group' must be one of {', '.join(AuditEvent.GROUPS)}; showing every group.")
        client_ref = ""
        text = given("client_ref")
        if text is not None:
            if len(text) > AuditFilter.MAX_CLIENT_REF or not text.isprintable():
                problems.append(f"'client_ref' must be printable text of at most {AuditFilter.MAX_CLIENT_REF} "
                                "characters; showing every client.")
            else:
                client_ref = text
        result = ""
        text = given("result")
        if text is not None:
            if text.lower() in AuditFilter.RESULT_CHOICES:
                result = text.lower()
            else:
                problems.append("'result' must be ok or failed; showing both.")
        page = 1
        text = given("page")
        if text is not None:
            if text.isascii() and text.isdigit() and len(text) <= 9 and int(text) >= 1:
                page = int(text)
            else:
                problems.append("'page' must be a whole number, 1 or more; showing page 1.")
        audit_filter = AuditFilter(days, actor, group, client_ref, result, page)
        audit_filter.__problems = problems
        return audit_filter

    def matches(self, event: AuditEvent, now: datetime) -> bool:
        """True if the event passes every active filter. now (passed in, so the answer is repeatable)
        is the end of the period and must carry a timezone (ValueError if it does not)."""
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must carry a timezone")
        if self.__days:
            happened = datetime.strptime(event.at, AuditEvent.TIME_FORMAT).replace(tzinfo=timezone.utc)
            if happened < now - timedelta(days=self.__days):
                return False
        if self.__actor and event.actor.casefold() != self.__actor.casefold():
            return False
        if self.__group and event.group != self.__group:
            return False
        if self.__client_ref and event.client_ref.casefold() != self.__client_ref.casefold():
            return False
        return not self.__result or event.result == self.__result

    def page_count(self, total: int) -> int:
        """How many pages hold this many events (at least 1, so an empty log still has a page 1)."""
        return max(1, -(-max(total, 0) // AuditFilter.PAGE_SIZE))

    def page_for(self, total: int) -> int:
        """The page actually shown for this many events: the chosen page, or the last page if the
        chosen one is past the end."""
        return min(self.__page, self.page_count(total))

    def page_of(self, events: list[AuditEvent]) -> list[AuditEvent]:
        """The events on the page page_for() gives, in the order given (newest first)."""
        page = self.page_for(len(events))
        start = (page - 1) * AuditFilter.PAGE_SIZE
        return events[start:start + AuditFilter.PAGE_SIZE]

    def to_query(self) -> dict[str, str]:
        """Only the values that are not the default, as text for a web address."""
        query: dict[str, str] = {}
        if self.__days != AuditFilter.DEFAULT_DAYS:
            query["days"] = str(self.__days) if self.__days else "all"
        for name, value in (("actor", self.__actor), ("group", self.__group),
                            ("client_ref", self.__client_ref), ("result", self.__result)):
            if value:
                query[name] = value
        if self.__page > 1:
            query["page"] = str(self.__page)
        return query

    def chips(self) -> list[tuple[str, str]]:
        """(label, text) for each active filter that is not the default, for the chips above the table."""
        chips: list[tuple[str, str]] = []
        if self.__days != AuditFilter.DEFAULT_DAYS:
            chips.append(("Period", "All time" if not self.__days else
                          "Last 24 hours" if self.__days == 1 else f"Last {self.__days} days"))
        if self.__actor:
            chips.append(("Officer", self.__actor))
        if self.__group:
            chips.append(("Group", self.__group))
        if self.__client_ref:
            chips.append(("Client", self.__client_ref))
        if self.__result:
            chips.append(("Result", "OK" if self.__result == "ok" else "Failed"))
        return chips
