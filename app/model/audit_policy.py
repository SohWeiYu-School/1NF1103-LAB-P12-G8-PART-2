"""AuditPolicy: the settings the audit flag rules use, read from the "audit" part of policy.json."""

import math
import re


class AuditPolicy:
    """The numbers behind the six flag rules (watched fields, windows, limits, working hours).

    Every value is checked when the object is made, so a bad setting stops the app at start-up with a
    clear message instead of making the rules behave strangely later. The defaults are the ones in the
    approved mockup. Read-only once built.
    """

    DEFAULT_WATCHED_FIELDS: tuple[str, ...] = ("claims.declared_net_worth", "career.annual_income",
                                               "claims.expected_aum", "claims.asset_composition",
                                               "claims.pep_status", "sow_declaration")
    KEYS: tuple[str, ...] = ("watched_fields", "window_days", "repeat_assessments", "jump_levels",
                             "work_start", "work_end", "spike_multiplier", "spike_min", "spike_baseline_days")
    MAX_JUMP_LEVELS: int = 3                     # PASSED to SERIOUS_RISK is 3 levels
    MAX_FIELD_LENGTH: int = 80
    __TIME_PATTERN: str = r"^([01]\d|2[0-3]):[0-5]\d$"

    def __init__(self, watched_fields: tuple[str, ...] | list[str] = DEFAULT_WATCHED_FIELDS,
                 window_days: int = 30, repeat_assessments: int = 3, jump_levels: int = 2,
                 work_start: str = "08:00", work_end: str = "20:00", spike_multiplier: float = 3,
                 spike_min: int = 3, spike_baseline_days: int = 14) -> None:
        """Raises ValueError, saying what is wrong and what is allowed, for any impossible value."""
        if isinstance(watched_fields, (str, bytes)) or not isinstance(watched_fields, (tuple, list)):
            raise ValueError("watched_fields must be a list of field names.")
        fields = tuple(watched_fields)
        if not fields:
            raise ValueError("watched_fields must name at least one field.")
        for field in fields:
            if (not isinstance(field, str) or not field.strip() or not field.isprintable()
                    or len(field) > AuditPolicy.MAX_FIELD_LENGTH):
                raise ValueError("Every watched field must be printable text of 1 to "
                                 f"{AuditPolicy.MAX_FIELD_LENGTH} characters (got {field!r}).")
        if len(set(fields)) != len(fields):
            raise ValueError("watched_fields must not name the same field twice.")
        AuditPolicy.__check_count("window_days", window_days, 1)
        AuditPolicy.__check_count("repeat_assessments", repeat_assessments, 1)
        AuditPolicy.__check_count("jump_levels", jump_levels, 1, AuditPolicy.MAX_JUMP_LEVELS)
        AuditPolicy.__check_count("spike_min", spike_min, 1)
        AuditPolicy.__check_count("spike_baseline_days", spike_baseline_days, 1)
        if (isinstance(spike_multiplier, bool) or not isinstance(spike_multiplier, (int, float))
                or not math.isfinite(spike_multiplier) or spike_multiplier <= 0):
            raise ValueError(f"spike_multiplier must be a number above 0 (got {spike_multiplier!r}).")
        start = AuditPolicy.__minutes("work_start", work_start, False)
        end = AuditPolicy.__minutes("work_end", work_end, True)
        if start >= end:
            raise ValueError(f"work_start ({work_start}) must be earlier than work_end ({work_end}).")
        self.__watched_fields: tuple[str, ...] = fields
        self.__window_days: int = window_days
        self.__repeat_assessments: int = repeat_assessments
        self.__jump_levels: int = jump_levels
        self.__work_start: str = work_start
        self.__work_end: str = work_end
        self.__spike_multiplier: float = spike_multiplier
        self.__spike_min: int = spike_min
        self.__spike_baseline_days: int = spike_baseline_days

    @staticmethod
    def __check_count(name: str, value: object, low: int, high: int | None = None) -> None:
        """Raises ValueError unless value is a whole number from low up to high (no upper limit if None)."""
        allowed = f"{low} or more" if high is None else f"from {low} to {high}"
        if isinstance(value, bool) or not isinstance(value, int) or value < low or (high is not None and value > high):
            raise ValueError(f"{name} must be a whole number, {allowed} (got {value!r}).")

    @staticmethod
    def __minutes(name: str, value: object, allow_24: bool) -> int:
        """Minutes after midnight for an "HH:MM" text ("24:00" is allowed for the end of the day only).
        Raises ValueError for anything else."""
        if allow_24 and value == "24:00":
            return 24 * 60
        if not isinstance(value, str) or not re.match(AuditPolicy.__TIME_PATTERN, value):
            raise ValueError(f"{name} must be a time written HH:MM, for example 08:00 (got {value!r}).")
        return int(value[:2]) * 60 + int(value[3:])

    @property
    def watched_fields(self) -> tuple[str, ...]:
        return self.__watched_fields

    @property
    def window_days(self) -> int:
        return self.__window_days

    @property
    def repeat_assessments(self) -> int:
        return self.__repeat_assessments

    @property
    def jump_levels(self) -> int:
        return self.__jump_levels

    @property
    def work_start(self) -> str:
        return self.__work_start

    @property
    def work_end(self) -> str:
        return self.__work_end

    @property
    def work_start_minutes(self) -> int:
        """The start of the working day, in minutes after midnight."""
        return AuditPolicy.__minutes("work_start", self.__work_start, False)

    @property
    def work_end_minutes(self) -> int:
        """The end of the working day, in minutes after midnight (up to 1440)."""
        return AuditPolicy.__minutes("work_end", self.__work_end, True)

    @property
    def spike_multiplier(self) -> float:
        return self.__spike_multiplier

    @property
    def spike_min(self) -> int:
        return self.__spike_min

    @property
    def spike_baseline_days(self) -> int:
        return self.__spike_baseline_days

    def to_dict(self) -> dict:
        """The settings as they are written in policy.json."""
        return {"watched_fields": list(self.__watched_fields), "window_days": self.__window_days,
                "repeat_assessments": self.__repeat_assessments, "jump_levels": self.__jump_levels,
                "work_start": self.__work_start, "work_end": self.__work_end,
                "spike_multiplier": self.__spike_multiplier, "spike_min": self.__spike_min,
                "spike_baseline_days": self.__spike_baseline_days}

    @staticmethod
    def from_dict(data: dict) -> "AuditPolicy":
        """Build the settings from the "audit" object. A missing key keeps its default. Raises ValueError
        if data is not an object, has a key that is not a setting, or any value is impossible."""
        if not isinstance(data, dict):
            raise ValueError("The audit settings must be an object.")
        unknown = sorted(str(key) for key in data if key not in AuditPolicy.KEYS)
        if unknown:
            raise ValueError(f"Unknown audit setting: {', '.join(unknown)}. Allowed: {', '.join(AuditPolicy.KEYS)}.")
        return AuditPolicy(**data)
