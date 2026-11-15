"""Check: one finding from one feature, in the shape every feature shares."""


class Check:
    """One finding. A Verdict is made up of Checks.

    status: failed, weak (points the wrong way, not enough alone), explained (another
    feature explains it, so it doesn't count), passed, skipped (couldn't run), info.
    """

    STATUSES: tuple[str, ...] = ("passed", "failed", "weak", "explained", "skipped", "info")
    # The fields every check has, in their saved order.
    FIELDS: tuple[str, ...] = ("feature", "check", "label", "theme", "status", "detail", "explanation", "group",
                               "sources", "supports")

    def __init__(self, feature: str = "", check: str = "", label: str = "", theme: str = "", status: str = "passed",
                 detail: str = "", explanation: str = "", group: str = "",
                 sources: list[str] | None = None, supports: list[str] | None = None,
                 extra: dict | None = None) -> None:
        self.__check_status(status)
        self.__feature: str = feature
        self.__check: str = check
        self.__label: str = label
        self.__theme: str = theme
        self.__status: str = status
        self.__detail: str = detail
        self.__explanation: str = explanation
        self.__group: str = group or label
        self.__sources: list[str] = list(sources or [])
        self.__supports: list[str] = list(supports or [])
        # A list given but empty is still written out when saved, after the extra details, as the
        # saved assessments have always had it.
        self.__empty_lists: list[str] = [name for name, value in (("sources", sources), ("supports", supports))
                                         if value is not None and not value]
        # Details one feature attaches for the report (for example which warning signs fired).
        self.__extra: dict = {}
        for key, value in (extra or {}).items():
            self.set_extra(key, value)

    @property
    def feature(self) -> str:
        return self.__feature

    @property
    def check(self) -> str:
        return self.__check

    @property
    def label(self) -> str:
        return self.__label

    @property
    def theme(self) -> str:
        return self.__theme

    @property
    def status(self) -> str:
        return self.__status

    @status.setter
    def status(self, status: str) -> None:
        self.__check_status(status)
        self.__status = status

    @property
    def detail(self) -> str:
        return self.__detail

    @property
    def explanation(self) -> str:
        return self.__explanation

    @property
    def group(self) -> str:
        return self.__group

    @property
    def sources(self) -> list[str]:
        return list(self.__sources)

    @property
    def supports(self) -> list[str]:
        return list(self.__supports)

    def failed(self) -> bool:
        return self.__status == "failed"

    def extra(self, name: str, default: object = None) -> object:
        """A detail the feature attached (for example "signs" or "independent"), or default."""
        return self.__extra.get(name, default)

    def set_extra(self, name: str, value: object) -> None:
        """Attach a detail for the verdict and the report. The named fields can't be set this way."""
        if not isinstance(name, str) or not name:
            raise ValueError("a check's extra detail needs a name (a non-empty text)")
        if name in Check.FIELDS:
            raise ValueError(f"'{name}' is one of a check's own fields; it can't be set as an extra detail")
        self.__extra[name] = value

    def to_dict(self) -> dict:
        data = {"feature": self.__feature, "check": self.__check, "label": self.__label,
                "theme": self.__theme, "status": self.__status, "detail": self.__detail,
                "explanation": self.__explanation, "group": self.__group}
        if self.__sources:
            data["sources"] = list(self.__sources)
        if self.__supports:
            data["supports"] = list(self.__supports)
        data.update(self.__extra)
        for name in self.__empty_lists:
            data[name] = []
        return data

    @staticmethod
    def from_dict(data: dict) -> "Check":
        """Build a Check from its saved layout. Fields this class has no name for are kept as extra."""
        names = Check.FIELDS[:8]
        known = {name: data.get(name, "") for name in names}
        extra = {key: value for key, value in data.items() if key not in Check.FIELDS}
        return Check(sources=data.get("sources"), supports=data.get("supports"), extra=extra, **known)

    def __check_status(self, status: str) -> None:
        if status not in Check.STATUSES:
            raise ValueError(f"'{status}' is not a check status; use one of {', '.join(Check.STATUSES)}")
