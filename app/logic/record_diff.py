"""RecordDiff: what changed between two saved versions of a client record."""

import copy
import re


class RecordDiff:
    """Compares a client record before and after an edit and lists the fields that changed.

    Only the officer's own edits count: the review-status fields that an assessment writes back
    (and the current date) are left out, so an assessment never looks like an edit.
    """

    IGNORED: tuple[str, ...] = ("outcome", "routing", "next_review_date", "last_assessed_on",
                                "forecasting_case", "current_date")

    def __init__(self, before: dict | None = None, after: dict | None = None) -> None:
        """before and after are records as ClientRecord.to_dict() gives them. before=None means a
        new client; after=None is an empty record. Raises ValueError if either is something other than a dict or None."""
        if before is not None and not isinstance(before, dict):
            raise ValueError("The record before the change must be a dict, or None for a new client.")
        if after is not None and not isinstance(after, dict):
            raise ValueError("The record after the change must be a dict (or None for empty).")
        self.__is_new: bool = before is None
        self.__before: dict = copy.deepcopy(before) if before is not None else {}
        self.__after: dict = copy.deepcopy(after) if after is not None else {}

    def changes(self) -> list[dict]:
        """One row per changed field: {"field": "claims.declared_net_worth", "before": 2000000,
        "after": 3500000}. Dicts are walked into dotted paths and lists by index
        ("investments[0].amount"); an item added to a list has before None, one removed has after None.
        For a new client every field with a value is listed, with before None. Sorted by field."""
        old = RecordDiff.__flatten(self.__before)
        new = RecordDiff.__flatten(self.__after)
        rows = []
        for field in set(old) | set(new):
            before, after = old.get(field), new.get(field)
            if self.__is_new and (after is None or after == ""):
                continue                                          # nothing was entered, so nothing to report
            if not RecordDiff.__same(before, after):
                rows.append({"field": field, "before": before, "after": after})
        return sorted(rows, key=lambda row: RecordDiff.__natural(row["field"]))

    def touches(self, fields: list[str]) -> bool:
        """True if any change is to one of these fields or inside it ("investments" matches
        "investments[0].amount"). Raises ValueError if fields is not a list of text."""
        if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
            raise ValueError("The fields to look for must be a list of text.")
        for row in self.changes():
            for field in fields:
                if row["field"] == field or row["field"].startswith((field + ".", field + "[")):
                    return True
        return False

    @staticmethod
    def __flatten(value: object, path: str = "") -> dict:
        """Every value in a nested record by its path. Empty dicts and lists hold nothing, so they give no path."""
        found: dict = {}
        if isinstance(value, dict):
            for key, item in value.items():
                if not path and key in RecordDiff.IGNORED:
                    continue
                found.update(RecordDiff.__flatten(item, f"{path}.{key}" if path else str(key)))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                found.update(RecordDiff.__flatten(item, f"{path}[{index}]"))
        else:
            found[path] = value
        return found

    @staticmethod
    def __same(before: object, after: object) -> bool:
        """Equal values; True and 1 are different."""
        return before == after and isinstance(before, bool) == isinstance(after, bool)

    @staticmethod
    def __natural(field: str) -> list:
        """A sort key that puts investments[2] before investments[10]."""
        return [(0, int(part), "") if part.isdigit() else (1, 0, part) for part in re.split(r"(\d+)", field)]
