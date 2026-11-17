"""AuditPage: one page of the audit log, with the counts the log page needs."""

from app.model.audit_event import AuditEvent


class AuditPage:
    """The events of one page (in the order they are shown), how many events match the filter in all, how
    many rows of the log cannot be read, how many readable events the whole log holds (so a page can tell
    an empty log from a filter that matches nothing), and, over every match (not only this page), how many
    different people did them and how many failed. open_flags is how many flags are still to handle (whatever the
    filter), for the "N open flags" part of the summary line. flagged names the events of this page that are
    behind a flag that is not resolved, so the page can mark their rows."""

    def __init__(self, events: list[AuditEvent] | None = None, total: int = 0, unreadable: int = 0,
                 everything: int = 0, officers: int = 0, failed: int = 0, open_flags: int = 0,
                 flagged: tuple[int, ...] | list[int] | set[int] | frozenset[int] = ()) -> None:
        """Raises ValueError for events that are not AuditEvents, a count that is not a whole number, 0 or more,
        or a flagged number that is not the entry number of one of the page's events."""
        events = [] if events is None else events
        if not isinstance(events, list) or not all(isinstance(event, AuditEvent) for event in events):
            raise ValueError("The page's events must be a list of AuditEvent objects.")
        counts = {"total": total, "unreadable": unreadable, "everything": everything,
                  "officers": officers, "failed": failed, "open_flags": open_flags}
        for name, value in counts.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"The {name} count must be a whole number, 0 or more (got {value!r}).")
        if total < len(events) or everything < total or failed > total or officers > total:
            raise ValueError("The counts do not fit together: the page cannot hold more events than match, "
                             "the match cannot be bigger than the log, and the officers and failures "
                             "cannot be more than the matches.")
        if isinstance(flagged, (str, bytes)) or not isinstance(flagged, (tuple, list, set, frozenset)):
            raise ValueError("The flagged entries must be a list of entry numbers.")
        if any(isinstance(n, bool) or not isinstance(n, int) for n in flagged) \
                or not set(flagged) <= {event.sequence for event in events}:
            raise ValueError("Every flagged entry number must be the number of an event on the page.")
        self.__events: list[AuditEvent] = list(events)
        self.__flagged: frozenset[int] = frozenset(flagged)
        self.__total: int = total
        self.__unreadable: int = unreadable
        self.__everything: int = everything
        self.__officers: int = officers
        self.__failed: int = failed
        self.__open_flags: int = open_flags

    @property
    def events(self) -> list[AuditEvent]:
        return list(self.__events)

    @property
    def total(self) -> int:
        return self.__total

    @property
    def unreadable(self) -> int:
        return self.__unreadable

    @property
    def everything(self) -> int:
        return self.__everything

    @property
    def officers(self) -> int:
        return self.__officers

    @property
    def failed(self) -> int:
        return self.__failed

    @property
    def open_flags(self) -> int:
        return self.__open_flags

    @property
    def flagged(self) -> frozenset[int]:
        """The entry numbers of this page's events that are behind a flag that is not resolved."""
        return self.__flagged
