"""AuditInsights: runs the six flag rules over the audit log."""

import math
from datetime import date, datetime, timedelta, timezone

from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.audit_policy import AuditPolicy
from app.model.flag import Flag
from app.model.verdict import Verdict


class AuditInsights:
    """Finds suspicious patterns in a list of audit events. Pure: the same events, policy and chain
    result always give the same flags, in the same order, with the same ids.

    The six rules (the numbers come from AuditPolicy):
      shop      a watched field is edited, and the client's next assessment moves the verdict
                jump_levels or more compared with the assessment before the edit (high)
      other     a client is edited by someone who is not the officer who created it (high if a watched
                field changed, else medium)
      repeat    more than repeat_assessments assessments of one client within window_days (medium)
      hours     an edit or assessment outside the working hours, Singapore time (low)
      spike     a day with at least spike_min failures and at least spike_multiplier times the median of
                the days before it (medium)
      integrity the chain check found a broken entry (high)

    Only events that succeeded (result "ok") count for the first four rules: a failed save changed
    nothing. Flags come back newest first (by the time of the last event behind them, then by id).
    """

    MONTHS: tuple[str, ...] = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    VERDICT_LABELS: dict[str, str] = {"PASSED": "Passed", "MANUAL_REVIEW": "Manual review", "RISKY": "Risky",
                                      "SERIOUS_RISK": "Serious risk"}
    FIELD_NAMES: dict[str, str] = {
        "claims.declared_net_worth": "Declared net worth",
        "claims.expected_aum": "Expected AUM", "claims.asset_composition": "Asset composition",
        "claims.pep_status": "PEP status", "sow_declaration": "Source of wealth story",
        "career.employer_name": "Employer", "career.occupation": "Occupation", "nationality": "Nationality",
        "claims.wealth_countries": "Wealth countries"}
    ACTION_NAMES: dict[str, str] = {"client_edited": "Edited client", "assessment_run": "Assessed"}
    FAILURE_KINDS: tuple[str, ...] = ("AI step not run", "Save failed", "Read failed", "Sync failed")
    __DAY: timedelta = timedelta(days=1)

    def __init__(self, events: list[AuditEvent] | None = None, policy: AuditPolicy | None = None,
                 broken_at: int = 0, now: datetime | None = None) -> None:
        """events are the log's events in any order (they are put in sequence order); broken_at is the
        position of the first broken entry from AuditChain (0 = the chain is intact); now is only used to
        date a log-changed flag when the log holds no events. Raises ValueError for a wrong type."""
        events = [] if events is None else events
        policy = AuditPolicy() if policy is None else policy
        if not isinstance(events, list) or any(not isinstance(event, AuditEvent) for event in events):
            raise ValueError("The events must be a list of audit events.")
        if not isinstance(policy, AuditPolicy):
            raise ValueError("The policy must be an AuditPolicy.")
        if isinstance(broken_at, bool) or not isinstance(broken_at, int) or broken_at < 0:
            raise ValueError(f"broken_at must be a whole number, 0 or more (got {broken_at!r}).")
        if now is not None and (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None):
            raise ValueError("now must be a time that carries a timezone.")
        self.__events: list[AuditEvent] = sorted(events, key=lambda event: event.sequence)
        self.__policy: AuditPolicy = policy
        self.__broken_at: int = broken_at
        self.__now: datetime | None = now

    @staticmethod
    def failure_kind(event: AuditEvent) -> str:
        """What kind of failure an event records: "AI step not run", "Save failed", "Read failed" or
        "Sync failed"; "" if the event is not a failure. An assessment that stopped while saving is a save
        failure; one that stopped at any other step, or finished with a step that did not run, is an
        AI step not run."""
        if event.action == "assessment_failed":
            return "Save failed" if event.details.get("step") == AuditEvent.SAVE_STEP else "AI step not run"
        if event.action == "assessment_run" and event.result == "ok" and event.details.get("not_run"):
            return "AI step not run"
        if event.action == "data_unavailable":
            return "Read failed"
        if event.action == "cloud_sync" and event.result == "failed":
            return "Sync failed"
        if event.action in ("client_created", "client_edited", "assessment_run") and event.result == "failed":
            return "Save failed"
        return ""

    def flags(self) -> list[Flag]:
        """Every flag the rules find, newest first (same time: by id)."""
        found: list[Flag] = []
        by_client: dict[str, list[AuditEvent]] = {}
        for event in self.__events:
            if event.client_ref:
                by_client.setdefault(event.client_ref, []).append(event)
        owners = {reference: AuditInsights.__owner(history) for reference, history in by_client.items()}
        for reference, history in by_client.items():
            found += self.__client_flags(reference, history)
        found += self.__hours_flags(owners)
        found += self.__spike_flags()
        found += self.__integrity_flags()
        found.sort(key=lambda flag: flag.flag_id)
        found.sort(key=lambda flag: -AuditInsights.__moment(flag.raised_at).timestamp())
        return found

    # ---- small helpers ----

    @staticmethod
    def __moment(text: str) -> datetime:
        return datetime.fromisoformat(text)

    @staticmethod
    def __local(event: AuditEvent) -> datetime:
        """The event's time in Singapore."""
        return AuditInsights.__moment(event.at).astimezone(AuditFilter.SINGAPORE)

    @staticmethod
    def __short_day(day: date) -> str:
        return f"{day.day} {AuditInsights.MONTHS[day.month - 1]}"

    @staticmethod
    def __clock(moment: datetime) -> str:
        return f"{moment.hour:02d}:{moment.minute:02d}"

    @staticmethod
    def __round(value: float) -> int:
        """Round half up, the way people count (Python's round() goes to the nearest even number)."""
        return math.floor(value + 0.5)

    @staticmethod
    def __number(value: object) -> str:
        """A figure for a sentence: 1,500,000 (not 1500000.0); text and other values as they are."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value:,}" if isinstance(value, int) else f"{value:,.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def __level(event: AuditEvent) -> int:
        """How serious the assessment's outcome is, 0 (PASSED) to 3; -1 if the outcome is not known."""
        outcome = event.details.get("outcome")
        return Verdict.OUTCOMES.index(outcome) if outcome in Verdict.OUTCOMES else -1

    @staticmethod
    def __changes(event: AuditEvent) -> list[dict]:
        """The field changes of an edit (only well-formed ones)."""
        changes = event.details.get("changes")
        return [change for change in changes if isinstance(change, dict)] if isinstance(changes, list) else []

    def __watched(self, event: AuditEvent) -> list[dict]:
        return [change for change in AuditInsights.__changes(event) if self.__policy.watching(change.get("field"))]

    @staticmethod
    def __field_name(field: object) -> str:
        return AuditInsights.FIELD_NAMES.get(field, str(field))

    def __moved_name(self, change: dict) -> str:
        """The changed field in words, under its watched parent: "asset composition (cash)"."""
        field = str(change.get("field"))
        root = self.__policy.watching(field) or field
        name = AuditInsights.__field_name(root).lower()
        tail = field[len(root):].lstrip(".") if field != root else ""
        return f"{name} ({tail})" if tail else name

    @staticmethod
    def __verdict_label(event: AuditEvent) -> str:
        return AuditInsights.VERDICT_LABELS.get(event.details.get("outcome"), "Unknown")

    @staticmethod
    def __owner(history: list[AuditEvent]) -> str:
        """Who created the client: the actor of its first saved client_created line; "" if not in the log."""
        for event in history:
            if event.action == "client_created" and event.result == "ok":
                return event.actor
        return ""

    @staticmethod
    def __amount(count: int, singular: str) -> str:
        return f"{count} {singular}" + ("" if count == 1 else "s")

    # ---- rules that follow one client ----

    def __client_flags(self, reference: str, history: list[AuditEvent]) -> list[Flag]:
        """shop, other and repeat for one client's events (in sequence order)."""
        owner = AuditInsights.__owner(history)
        window = timedelta(days=self.__policy.window_days)
        found: list[Flag] = []
        last_assessment: AuditEvent | None = None
        pending: AuditEvent | None = None            # the latest watched edit since the last assessment
        for event in history:
            if event.result != "ok":
                continue
            if event.action == "client_edited":
                watched = self.__watched(event)
                if watched and last_assessment:
                    pending = event
                if owner and event.actor != owner:
                    found.append(self.__other_flag(reference, event, owner, watched))
            elif event.action == "assessment_run":
                if (last_assessment and pending and AuditInsights.__level(event) >= 0
                        and AuditInsights.__level(last_assessment) >= 0
                        and abs(AuditInsights.__level(event) - AuditInsights.__level(last_assessment))
                        >= self.__policy.jump_levels
                        and AuditInsights.__moment(event.at) - AuditInsights.__moment(last_assessment.at) <= window):
                    found.append(self.__shop_flag(reference, owner, last_assessment, pending, event))
                last_assessment, pending = event, None
        found += self.__repeat_flags(reference, owner, [e for e in history if e.action == "assessment_run"
                                                        and e.result == "ok"])
        return found

    def __other_flag(self, reference: str, edit: AuditEvent, owner: str, watched: list[dict]) -> Flag:
        return Flag(Flag.make_id("other", reference, edit.sequence), "other", "high" if watched else "medium",
                    reference, f"Edited by {edit.actor}, not the client's owner ({owner})", "", (edit.sequence,),
                    edit.at, owner, AuditInsights.__changes(edit))

    def __shop_flag(self, reference: str, owner: str, before: AuditEvent, edit: AuditEvent,
                    after: AuditEvent) -> Flag:
        gap = AuditInsights.__level(after) - AuditInsights.__level(before)
        minutes = AuditInsights.__round((AuditInsights.__moment(after.at) - AuditInsights.__moment(edit.at))
                                        .total_seconds() / 60)
        how_long = (AuditInsights.__amount(minutes, "minute") if minutes < 60
                    else AuditInsights.__amount(AuditInsights.__round(minutes / 60), "hour"))
        watched = self.__watched(edit)
        moved = " and ".join(f"{self.__moved_name(change)} went "
                             f"{AuditInsights.__number(change.get('before'))} → "
                             f"{AuditInsights.__number(change.get('after'))}" for change in watched)
        meaning = (f"The result went from {AuditInsights.__verdict_label(before)} to "
                   f"{AuditInsights.__verdict_label(after)} {how_long} after {moved}. Raising declared "
                   "figures until a case passes is the pattern regulators look for.")
        headline = (f"Verdict {'improved' if gap < 0 else 'worsened'} by {abs(gap)} levels after declared "
                    "figures were edited")
        return Flag(Flag.make_id("shop", reference, after.sequence), "shop", "high", reference, headline, meaning,
                    (before.sequence, edit.sequence, after.sequence), after.at, owner, watched)

    def __repeat_flags(self, reference: str, owner: str, runs: list[AuditEvent]) -> list[Flag]:
        """One flag per burst. A burst starts with a run and takes in every later run within window_days of
        that first run; the next run after that starts a new burst. A burst of more than repeat_assessments
        runs is flagged, with the id of its first run, so the id stays the same while the burst grows."""
        window = timedelta(days=self.__policy.window_days)
        bursts: list[list[AuditEvent]] = []
        for run in runs:
            if bursts and AuditInsights.__moment(run.at) - AuditInsights.__moment(bursts[-1][0].at) <= window:
                bursts[-1].append(run)
            else:
                bursts.append([run])
        found: list[Flag] = []
        for within in bursts:
            if len(within) <= self.__policy.repeat_assessments:
                continue
            run = within[-1]
            labels = [AuditInsights.__verdict_label(other) for other in within]
            days = max(1, AuditInsights.__round((AuditInsights.__moment(run.at)
                                                 - AuditInsights.__moment(within[0].at)).total_seconds() / 86400))
            same = ("Nothing changed between runs, so re-running is not moving the case forward."
                    if len(set(labels)) == 1 else "The result changed between runs.")
            meaning = (f"Results: {', '.join(labels)}. {same} Repeated runs can also be a way of hoping for a "
                       "better answer.")
            found.append(Flag(Flag.make_id("repeat", reference, within[0].sequence), "repeat", "medium", reference,
                              f"Assessed {len(within)} times in {AuditInsights.__amount(days, 'day')}", meaning,
                              tuple(other.sequence for other in within), run.at, owner))
        return found

    # ---- rules that look at single events or whole days ----

    def __hours_flags(self, owners: dict[str, str]) -> list[Flag]:
        policy = self.__policy
        found: list[Flag] = []
        for event in self.__events:
            if event.action not in AuditInsights.ACTION_NAMES or event.result != "ok":
                continue
            local = AuditInsights.__local(event)
            minutes = local.hour * 60 + local.minute
            if policy.work_start_minutes <= minutes < policy.work_end_minutes:
                continue
            clock = AuditInsights.__clock(local)
            worked_on = event.client_ref or "a client"
            meaning = (f"{event.actor} worked on {worked_on} at {clock} on {AuditInsights.__short_day(local.date())}. "
                       f"Working hours are {policy.work_start} to {policy.work_end}. Out-of-hours changes are "
                       "less likely to be seen by a colleague.")
            found.append(Flag(Flag.make_id("hours", event.client_ref, event.sequence), "hours", "low",
                              event.client_ref,
                              f"{AuditInsights.ACTION_NAMES[event.action]} at {clock}, outside working hours",
                              meaning, (event.sequence,), event.at, owners.get(event.client_ref, "")))
        return found

    def __spike_flags(self) -> list[Flag]:
        policy = self.__policy
        failures: dict[date, list[AuditEvent]] = {}
        for event in self.__events:
            if AuditInsights.failure_kind(event):
                failures.setdefault(AuditFilter.event_day(event), []).append(event)
        found: list[Flag] = []
        for day in sorted(failures):
            events = failures[day]
            count = len(events)
            if count < policy.spike_min:
                continue
            before = sorted(len(failures.get(day - AuditInsights.__DAY * back, []))
                            for back in range(1, policy.spike_baseline_days + 1))
            middle = len(before) // 2
            usual = before[middle] if len(before) % 2 else (before[middle - 1] + before[middle]) / 2
            if count < policy.spike_multiplier * usual:
                continue
            usual_text = AuditInsights.__number(usual)
            found.append(Flag(Flag.make_id("spike", "", events[0].sequence), "spike", "medium", "",
                              f"{count} failures on {AuditInsights.__short_day(day)} (usually {usual_text})",
                              AuditInsights.__spike_meaning(events), tuple(event.sequence for event in events),
                              events[-1].at, day=day.isoformat(), usual=usual))
        return found

    @staticmethod
    def __spike_meaning(events: list[AuditEvent]) -> str:
        """What the day's failures were, by kind, and what that may mean."""
        counts = {kind: 0 for kind in AuditInsights.FAILURE_KINDS}
        finished = 0                                   # assessments that finished with a step not run
        for event in events:
            counts[AuditInsights.failure_kind(event)] += 1
            finished += event.action == "assessment_run"
        stopped = counts["AI step not run"] - finished
        parts = []
        if stopped:
            parts.append(f"{AuditInsights.__amount(stopped, 'assessment')} stopped because the "
                         "AI service did not answer")
        if finished:
            parts.append(f"{AuditInsights.__amount(finished, 'assessment')} finished with a step that did not run")
        if counts["Read failed"]:
            parts.append(f"the database could not be read {AuditInsights.__amount(counts['Read failed'], 'time')}")
        if counts["Save failed"]:
            parts.append(f"{AuditInsights.__amount(counts['Save failed'], 'save')} failed")
        if counts["Sync failed"]:
            parts.append(f"{AuditInsights.__amount(counts['Sync failed'], 'cloud sync')} failed")
        text = parts[0] + (", and " + ", and ".join(parts[1:]) if len(parts) > 1 else "")
        text = text[0].upper() + text[1:] + "."
        return text + (" Cases assessed that day may be missing steps." if counts["AI step not run"]
                       else " Work done that day may not have been saved or read.")

    def __integrity_flags(self) -> list[Flag]:
        entry = self.__broken_at
        if not entry:
            return []
        raised = next((event.at for event in self.__events if event.sequence == entry), "")
        if not raised and self.__events:
            raised = self.__events[-1].at
        if not raised:
            raised = (self.__now or datetime(1970, 1, 1, tzinfo=timezone.utc)).astimezone(timezone.utc) \
                .strftime(AuditEvent.TIME_FORMAT)
        meaning = (f"Entry #{entry} no longer matches the fingerprint stored in entry #{entry + 1}. Someone "
                   "edited or removed it directly in the file. Entries from "
                   f"#{entry} on can't be trusted until this is explained.")
        return [Flag(Flag.make_id("integrity", "", entry), "integrity", "high", "",
                     f"Audit log changed outside the app at entry #{entry}", meaning, (), raised,
                     broken_at=entry)]
