"""Flag: one suspicious pattern the audit rules found in the log."""

import copy
import re
from datetime import date, datetime


class Flag:
    """A finding of one of the six audit rules. It is worked out from the log each time and never
    stored, so it is read-only: everything is checked in __init__ and exposed through properties.

    The id is "F-" + the first three letters of the kind + the client reference (if any) + the number of
    a log entry, e.g. F-SHO-SOW-1-484 or F-INT-303. It is made by make_id(). The constructor checks the
    id's shape and that its kind prefix matches the kind; it does not insist on which entry number the
    rule chose, because the rules pick the entry that keeps the id stable (the first failure of a spike
    day, the last run of a burst of assessments).
    """

    KINDS: tuple[str, ...] = ("shop", "other", "repeat", "hours", "spike", "integrity")
    NAMES: dict[str, str] = {"shop": "Verdict jump after edit", "other": "Edited by non-owner",
                             "repeat": "Repeated assessments", "hours": "After-hours activity",
                             "spike": "Failure spike", "integrity": "Log changed outside app"}
    SEVERITIES: tuple[str, ...] = ("high", "medium", "low")
    SEVERITY_NAMES: dict[str, str] = {"high": "High", "medium": "Medium", "low": "Low"}
    MAX_CLIENT_REF: int = 40
    MAX_HEADLINE: int = 300
    MAX_MEANING: int = 800
    MAX_OWNER: int = 80
    __ID_PATTERN: str = r"^F-[A-Z]{3}(-[A-Z0-9]+(-[A-Z0-9]+)*)?-[0-9]+$"

    def __init__(self, flag_id: str = "F-SHO-1", kind: str = "shop", severity: str = "high",
                 client_ref: str = "", headline: str = "Flag", meaning: str = "",
                 sequences: tuple[int, ...] | list[int] = (1,), raised_at: str = "2026-01-01T00:00:00Z",
                 owner: str = "", changes: tuple[dict, ...] | list[dict] = (), day: str = "",
                 usual: float = 0, broken_at: int = 0) -> None:
        """Raises ValueError, saying what is wrong and what is allowed, for any impossible value."""
        for name, value in (("flag_id", flag_id), ("kind", kind), ("severity", severity),
                            ("client_ref", client_ref), ("headline", headline), ("meaning", meaning),
                            ("raised_at", raised_at), ("owner", owner), ("day", day)):
            if not isinstance(value, str):
                raise ValueError(f"The flag's {name} must be text.")
        if kind not in Flag.KINDS:
            raise ValueError(f"The flag kind must be one of {', '.join(Flag.KINDS)} (got {kind!r}).")
        if severity not in Flag.SEVERITIES:
            raise ValueError(f"The flag severity must be one of {', '.join(Flag.SEVERITIES)} (got {severity!r}).")
        client_ref, owner, headline = client_ref.strip(), owner.strip(), headline.strip()
        if not client_ref.isprintable() or len(client_ref) > Flag.MAX_CLIENT_REF:
            raise ValueError(f"The client reference must be printable text of at most {Flag.MAX_CLIENT_REF} characters.")
        if not owner.isprintable() or len(owner) > Flag.MAX_OWNER:
            raise ValueError(f"The owner must be printable text of at most {Flag.MAX_OWNER} characters.")
        if not headline or len(headline) > Flag.MAX_HEADLINE:
            raise ValueError(f"The headline must be 1 to {Flag.MAX_HEADLINE} characters.")
        if len(meaning) > Flag.MAX_MEANING:
            raise ValueError(f"The explanation must be at most {Flag.MAX_MEANING} characters.")
        if (not re.match(Flag.__ID_PATTERN, flag_id)
                or not flag_id.startswith("F-" + kind[:3].upper() + "-")):
            raise ValueError(f"The flag id must look like F-{kind[:3].upper()}-<client>-<entry number> "
                             f"(got {flag_id!r}).")
        if isinstance(sequences, (str, bytes)) or not isinstance(sequences, (tuple, list)):
            raise ValueError("The flag's log entries must be a list of entry numbers.")
        sequences = tuple(sequences)
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in sequences):
            raise ValueError("Every log entry number must be a whole number, 1 or more.")
        if not sequences and kind != "integrity":
            raise ValueError("A flag must name at least one log entry behind it.")
        if isinstance(broken_at, bool) or not isinstance(broken_at, int) or broken_at < 0:
            raise ValueError(f"broken_at must be a whole number, 0 or more (got {broken_at!r}).")
        if kind == "integrity" and broken_at < 1:
            raise ValueError("A log-changed flag must say which entry is broken (broken_at, 1 or more).")
        if kind != "integrity" and broken_at:
            raise ValueError("Only a log-changed flag has a broken_at.")
        if isinstance(usual, bool) or not isinstance(usual, (int, float)) or usual < 0 or usual != usual:
            raise ValueError(f"usual must be a number, 0 or more (got {usual!r}).")
        if isinstance(changes, (str, bytes)) or not isinstance(changes, (tuple, list)):
            raise ValueError("The changes must be a list of changed fields.")
        if any(not isinstance(change, dict) for change in changes):
            raise ValueError("Each change must be an object with field, before and after.")
        Flag.__check_time(raised_at)
        if kind == "spike":
            if Flag.__parse_day(day) is None:
                raise ValueError(f"A failure-spike flag needs its day as YYYY-MM-DD (got {day!r}).")
        elif day:
            raise ValueError("Only a failure-spike flag has a day.")
        self.__flag_id: str = flag_id
        self.__kind: str = kind
        self.__severity: str = severity
        self.__client_ref: str = client_ref
        self.__headline: str = headline
        self.__meaning: str = meaning
        self.__sequences: tuple[int, ...] = sequences
        self.__raised_at: str = raised_at
        self.__owner: str = owner
        self.__changes: tuple[dict, ...] = tuple(copy.deepcopy(change) for change in changes)
        self.__day: str = day
        self.__usual: float = usual
        self.__broken_at: int = broken_at

    @staticmethod
    def __check_time(text: str) -> None:
        """Raises ValueError unless text is an ISO time that carries an offset (Z or +08:00)."""
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            moment = None
        if moment is None or moment.tzinfo is None:
            raise ValueError(f"raised_at must be an ISO time with an offset, like 2026-11-13T06:05:00Z (got {text!r}).")

    @staticmethod
    def __parse_day(text: str) -> date | None:
        try:
            return datetime.strptime(text, "%Y-%m-%d").date() if len(text) == 10 else None
        except ValueError:
            return None

    @staticmethod
    def make_id(kind: str, client_ref: str, sequence: int) -> str:
        """The flag id for a kind, a client reference ("" for none) and a log entry number, e.g.
        F-SHO-SOW-1-484. In the reference, capitals and digits are kept, every other run of
        characters becomes one "-", and leading and trailing "-" are cut."""
        reference = re.sub(r"[^A-Z0-9]+", "-", client_ref.upper()).strip("-")
        return "F-" + kind[:3].upper() + ("-" + reference if reference else "") + "-" + str(sequence)

    @property
    def flag_id(self) -> str:
        return self.__flag_id

    @property
    def kind(self) -> str:
        return self.__kind

    @property
    def severity(self) -> str:
        return self.__severity

    @property
    def client_ref(self) -> str:
        return self.__client_ref

    @property
    def headline(self) -> str:
        return self.__headline

    @property
    def meaning(self) -> str:
        return self.__meaning

    @property
    def sequences(self) -> tuple[int, ...]:
        return self.__sequences

    @property
    def raised_at(self) -> str:
        return self.__raised_at

    @property
    def owner(self) -> str:
        return self.__owner

    @property
    def changes(self) -> tuple[dict, ...]:
        return tuple(copy.deepcopy(change) for change in self.__changes)

    @property
    def day(self) -> str:
        return self.__day

    @property
    def usual(self) -> float:
        return self.__usual

    @property
    def broken_at(self) -> int:
        return self.__broken_at

    @property
    def name(self) -> str:
        """The kind's name for people, e.g. "Verdict jump after edit"."""
        return Flag.NAMES[self.__kind]

    @property
    def severity_name(self) -> str:
        """"High", "Medium" or "Low"."""
        return Flag.SEVERITY_NAMES[self.__severity]
