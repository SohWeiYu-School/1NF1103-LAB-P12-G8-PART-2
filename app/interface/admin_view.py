"""AdminView: how the admin screens look on the terminal (the twin of the admin pages of WebApp)."""

from datetime import datetime, timezone
from typing import Any

from app.interface.console_ui import ConsoleUI
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.audit_page import AuditPage
from app.model.flag_ticket import FlagTicket
from app.model.overview_page import OverviewPage


class AdminView:
    """Turns what App returns for the admin (the overview, a flag, a client's flags, a page of the activity log, the
    result of a chain check) into text. Each format_ method returns the text; each show_ method gives it to the
    ConsoleUI to print, so this class never prints itself. The words are the ones the web pages use. An empty
    result says so plainly; an error is never shown here, the AdminConsole shows it.
    """

    SGT_FORMAT: str = "%Y-%m-%d %H:%M"
    PRESET_NAMES: dict[str, str] = {"today": "Today", "7": "7 days", "30": "30 days", "90": "90 days"}
    LOG_PRESET_NAMES: dict[str, str] = {"1": "Today", "7": "7 days", "30": "30 days", "90": "90 days",
                                        "custom": "Custom dates"}
    RESULT_NAMES: dict[str, str] = {"all": "All", "ok": "OK only", "failed": "Failed only"}
    SORT_NAMES: dict[str, str] = {"desc": "Newest first", "asc": "Oldest first"}
    FAILURE_COLUMN: int = 16                          # width of one failure kind's column in the table

    def __init__(self, ui: ConsoleUI | None = None) -> None:
        """ui is the screen the show_ methods print on. Raises ValueError for anything that is not a ConsoleUI."""
        if ui is not None and not isinstance(ui, ConsoleUI):
            raise ValueError("The admin view needs a ConsoleUI to print on.")
        self.__ui: ConsoleUI = ui if ui is not None else ConsoleUI()

    # ----- small helpers ---------------------------------------------------------------------

    @staticmethod
    def __plural(count: int, word: str, many: str = "") -> str:
        return f"{count} {word if count == 1 else (many or word + 's')}"

    @staticmethod
    def __sgt(text: str) -> str:
        """A time as the log stores it (UTC, ISO with Z or an offset) in Singapore time, "2026-11-02 11:00"; the
        text itself if it cannot be read."""
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return str(text)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(AuditFilter.SINGAPORE).strftime(AdminView.SGT_FORMAT)

    @staticmethod
    def __change(has_previous: bool, change: int | None, diff: int) -> str:
        """How an Actions or Failures figure moved against the earlier range, as the web's pill says it."""
        if not has_previous:
            return "No earlier data"
        if change is None:
            return f"{diff:+d} vs earlier"
        return f"{change:+d}% vs earlier"

    @staticmethod
    def __event_line(event: AuditEvent, marked: bool = False) -> str:
        """One entry of the log: number, time, officer, what it was, client, what happened."""
        client = event.client_ref or "-"
        return (f"  #{event.sequence:<5} {AdminView.__sgt(event.at)}  {event.actor:<14} {event.label:<22} "
                f"{client:<12} {event.summary()}{'  [flagged]' if marked else ''}")

    # ----- the Overview ----------------------------------------------------------------------

    def format_overview(self, page: OverviewPage) -> str:
        """The Overview: the numbers, the failures by day, the flags by type and one page of the flags table."""
        if not isinstance(page, OverviewPage):
            raise ValueError("The overview needs an OverviewPage.")
        days = (page.day_to - page.day_from).days + 1
        lines = [f"OVERVIEW  {AdminView.PRESET_NAMES[page.preset]}: {page.day_from} to {page.day_to}",
                 ConsoleUI.LINE]
        if page.unreadable:
            lines.append(f"! {AdminView.__plural(page.unreadable, 'log entry', 'log entries')} could not be read, "
                         "so the numbers below may be missing "
                         f"{'it' if page.unreadable == 1 else 'them'}. Use Verify the audit log to see which.")
        if page.flags_skipped:
            lines.append(f"! {AdminView.__plural(page.flags_skipped, 'flag')} could not be worked out, so "
                         f"{'it is' if page.flags_skipped == 1 else 'they are'} left out of the numbers and the table.")
        if not page.intact:
            lines.append(f"! Entry #{page.broken_at} was changed outside the app, so the numbers from that entry "
                         "on can't be trusted.")
        previous = f"vs previous {AdminView.__plural(days, 'day')}"
        lines += [
            f"Flags to handle : {page.to_handle}  ({page.not_started} not started, {page.in_progress} in progress)",
            f"Actions         : {page.actions:,}  ({AdminView.__change(page.has_previous, page.actions_change, page.actions_diff)}, {previous})",
            f"Failures        : {page.failures}  ({AdminView.__change(page.has_previous, page.failures_change, page.failures_diff)}, {previous})",
            "Log integrity   : " + (f"Intact ({page.entries:,} entries checked)" if page.intact
                                    else f"Changed outside the app at entry #{page.broken_at}"),
            "", "Failures over time: AI steps, saves, reads and syncs that didn't work"]
        lines += self.__failure_table(page)
        lines += ["", f"Flags by type (not resolved, raised in this range): "
                      f"{AdminView.__plural(sum(page.severity_counts.values()), 'open flag')}"]
        if sum(page.severity_counts.values()):
            lines.append("  By priority: " + ", ".join(f"{name.capitalize()} {page.severity_counts[name]}"
                                                       for name in OverviewPage.SEVERITIES))
            lines += [f"  {name:<28} {count:>3}  ({percent}%)  {page.type_severity[kind].capitalize()} priority"
                      for kind, name, count, percent in page.flags_by_type]
        else:
            lines.append("  No open flags in this range.")
        lines += ["", f"Flags: {OverviewPage.TAB_NAMES[page.tab]}   "
                      + "  ".join(f"{OverviewPage.TAB_NAMES[tab]} {page.tab_counts[tab]}" for tab in OverviewPage.TABS),
                  "Each flag is a ticket. Flags stay here until resolved, whatever the date range."]
        lines += self.__flag_rows(page)
        return ConsoleUI.printable(lines)

    def __failure_table(self, page: OverviewPage) -> list[str]:
        """One line per day that had failures, with the failures of each kind and the day's total, then the
        totals. Days with none are counted in one closing line, so a 90 day range stays readable."""
        days = page.failures_by_day
        if not days:
            return ["  No days to show."]
        kinds = list(days[0][1])
        width = AdminView.FAILURE_COLUMN
        failed = [(day, counts) for day, counts in days if sum(counts.values())]
        if not failed:
            return [f"  No failures in these {AdminView.__plural(len(days), 'day')}."]
        lines = ["  " + f"{'Day':<12}" + "".join(f"{kind:>{width}}" for kind in kinds) + f"{'Total':>8}"]
        for day, counts in failed:
            lines.append("  " + f"{day:<12}" + "".join(f"{counts.get(kind, 0):>{width}}" for kind in kinds)
                         + f"{sum(counts.values()):>8}")
        lines.append("  " + f"{'All days':<12}" + "".join(f"{sum(counts.get(kind, 0) for _, counts in days):>{width}}"
                                                          for kind in kinds) + f"{page.failures:>8}")
        quiet = len(days) - len(failed)
        if quiet:
            lines.append(f"  ({AdminView.__plural(quiet, 'day')} with no failures not listed)")
        return lines

    def __flag_rows(self, page: OverviewPage) -> list[str]:
        """The flags of this page of the table, then "Showing 1-6 of 9" and "Page 1 of 2"."""
        shown_total = page.tab_counts[page.tab]
        if not page.rows:
            empty = ("Nothing resolved yet. Open a flag and set it to Resolved with a note."
                     if page.tab == "resolved" else
                     ("No flags to handle." if page.tab == "handle" else "No flags here."))
            return ["", empty, f"0 flags   Page {page.page} of {page.page_count}"]
        lines = [""]
        for number, ticket in enumerate(page.rows, start=1):
            flag = ticket.flag
            lines.append(f"  {number}. {flag.flag_id}  [{flag.severity_name}] {flag.name}")
            lines.append(f"     {'Client ' + flag.client_ref if flag.client_ref else 'System'} | {ticket.status_name} | "
                         f"raised {AdminView.__sgt(flag.raised_at)}")
            lines.append(f"     {flag.headline}")
        first = (page.page - 1) * OverviewPage.PAGE_SIZE + 1
        last = min(page.page * OverviewPage.PAGE_SIZE, shown_total)
        lines.append(f"Showing {first}-{last} of {shown_total}   Page {page.page} of {page.page_count}")
        return lines

    def show_overview(self, page: OverviewPage) -> None:
        self.__ui.show("\n" + self.format_overview(page))

    # ----- a flag ----------------------------------------------------------------------------

    def format_flag(self, ticket: FlagTicket, evidence: list[AuditEvent], entries: int) -> str:
        """One flag as a ticket: what happened, the evidence (the log entries behind it) and its activity.
        entries is how many entries the whole log holds, so a missing one can be told from a short log."""
        if not isinstance(ticket, FlagTicket):
            raise ValueError("A flag needs a FlagTicket.")
        flag = ticket.flag
        lines = [f"{flag.flag_id}  {flag.name}", ConsoleUI.LINE, flag.headline,
                 f"Priority : {flag.severity_name}", f"Status   : {ticket.status_name}",
                 f"Client   : {flag.client_ref or 'System'}",
                 f"Raised   : {AdminView.__sgt(flag.raised_at)} (Singapore time)"]
        if ticket.assignee:
            lines.append(f"Handled by: {ticket.assignee}")
        if ticket.waiting_on:
            lines.append(f"Waiting on: {ticket.waiting_on}")
        if ticket.outcome:
            lines.append(f"Outcome  : {FlagTicket.OUTCOMES.get(ticket.outcome, ticket.outcome)}")
        lines += ["", "What happened"]
        if flag.meaning:
            lines.append(f"  {flag.meaning}")
        for change in flag.changes:
            lines.append(f"  {change.get('field')}: {change.get('before')} -> {change.get('after')}")
        lines += ["", "Evidence"]
        if flag.sequences:
            count = len(flag.sequences)
            lines.append(f"  The {count} log {'entries' if count > 1 else 'entry'} behind this flag "
                         f"({' '.join('#' + str(number) for number in flag.sequences[:4])}"
                         f"{' ...' if count > 4 else ''}):")
        found = {event.sequence for event in evidence}
        lines += [AdminView.__event_line(event) for event in evidence]
        missing = [number for number in flag.sequences if number not in found]
        if missing:
            lines.append(f"  ! {AdminView.__plural(len(missing), 'entry', 'entries')} behind this flag could not be "
                         f"read ({entries:,} entries in the log).")
        elif not evidence:
            lines.append("  There are no log entries behind this flag.")
        if ticket.skipped_count:
            lines.append(f"  ! {AdminView.__plural(ticket.skipped_count, 'update')} to this flag could not be read "
                         "and are left out.")
        lines += ["", "Activity (newest first)"]
        for item in reversed(ticket.history):
            moved = (f" {FlagTicket.STATUSES.get(item['from'], item['from'])} -> "
                     f"{FlagTicket.STATUSES.get(item['to'], item['to'])}"
                     if item.get("from") and item["from"] != item["to"] else "")
            extra = ""
            if item.get("waiting_on"):
                extra += f" (waiting on {item['waiting_on']})"
            if item.get("outcome"):
                extra += f" (outcome: {FlagTicket.OUTCOMES.get(item['outcome'], item['outcome'])})"
            lines.append(f"  {AdminView.__sgt(item['at'])}  {item['by']}{moved}{extra}")
            lines += [f"      {part}" for part in str(item.get("note") or "").splitlines() if part.strip()]
        return ConsoleUI.printable(lines)

    def show_flag(self, ticket: FlagTicket, evidence: list[AuditEvent], entries: int) -> None:
        self.__ui.show("\n" + self.format_flag(ticket, evidence, entries))

    # ----- a client's flags ------------------------------------------------------------------

    def format_client_flags(self, client_ref: str, tickets: list[FlagTicket]) -> str:
        """The flags of one client that are not resolved. An empty list says there are none (it is never an error)."""
        if not isinstance(client_ref, str) or not isinstance(tickets, list):
            raise ValueError("The client's flags need a client reference and a list of flags.")
        if not tickets:
            return ConsoleUI.printable([f"No flags to handle for {client_ref}."])
        lines = [f"FLAGS FOR {client_ref.upper()}  ({AdminView.__plural(len(tickets), 'flag')} not resolved)",
                 ConsoleUI.LINE]
        for ticket in tickets:
            flag = ticket.flag
            lines.append(f"  {flag.flag_id}  [{flag.severity_name}] {flag.name} | {ticket.status_name} | "
                         f"raised {AdminView.__sgt(flag.raised_at)}")
            lines.append(f"     {flag.headline}")
        return ConsoleUI.printable(lines)

    def show_client_flags(self, client_ref: str, tickets: list[FlagTicket]) -> None:
        self.__ui.show("\n" + self.format_client_flags(client_ref, tickets))

    # ----- the activity log ------------------------------------------------------------------

    def format_filter(self, audit_filter: AuditFilter, now: datetime) -> str:
        """The filter in one or two lines: the dates, then each filter that is not the default."""
        if not isinstance(audit_filter, AuditFilter):
            raise ValueError("The filter summary needs an AuditFilter.")
        chips = [text for _, text in audit_filter.chips()]
        order = AdminView.SORT_NAMES[audit_filter.sort]
        return (f"Showing: {AdminView.LOG_PRESET_NAMES[audit_filter.preset]} ({audit_filter.range_text(now)}); "
                f"{order}" + ("; " + "; ".join(chips) if chips else ""))

    def format_log_page(self, page: AuditPage, audit_filter: AuditFilter, now: datetime) -> str:
        """One page of the activity log: the filter, the summary line, the events and "Page x of y"."""
        if not isinstance(page, AuditPage) or not isinstance(audit_filter, AuditFilter):
            raise ValueError("The activity log needs an AuditPage and the AuditFilter it was asked with.")
        lines = ["ACTIVITY LOG", ConsoleUI.LINE, self.format_filter(audit_filter, now)]
        lines += [f"! {problem}" for problem in audit_filter.problems()]
        if page.unreadable:
            lines.append(f"! {AdminView.__plural(page.unreadable, 'entry', 'entries')} in the audit log can't be "
                         "read. Use Verify the audit log to see which.")
        if not page.flags_ok:
            lines.append("! The flags could not be worked out right now. The events below are still complete.")
        if page.flags_skipped:
            lines.append(f"! {AdminView.__plural(page.flags_skipped, 'flag')} could not be worked out, so "
                         f"{'it is' if page.flags_skipped == 1 else 'they are'} not marked or counted here.")
        flags = ("flags unknown" if not page.flags_ok
                 else AdminView.__plural(page.open_flags or 0, "open flag") if page.open_flags else "no open flags")
        lines.append(f"{audit_filter.period_text(now)}: {AdminView.__plural(page.total, 'event')} by "
                     f"{AdminView.__plural(page.officers, 'officer')}; {page.failed} failed; {flags}")
        if page.events:
            lines.append(f"  {'#':<6} {'Time (SGT)':<16}  {'Officer':<14} {'Action':<22} {'Client':<12} What happened")
            lines += [AdminView.__event_line(event, event.sequence in page.flagged) for event in page.events]
        elif page.everything == 0 and not page.unreadable:
            lines.append("No activity recorded yet.")
        elif page.everything == 0:
            lines.append("No activity can be shown.")
        else:
            lines.append("No events match these filters. Try a longer date range or clear the filters.")
        pages = audit_filter.page_count(page.total)
        number = audit_filter.page_for(page.total)
        first = (number - 1) * AuditFilter.PAGE_SIZE + 1 if page.total else 0
        lines.append(f"Showing {first}-{min(number * AuditFilter.PAGE_SIZE, page.total)} of {page.total}   "
                     f"Page {number} of {pages}")
        return ConsoleUI.printable(lines)

    def show_log_page(self, page: AuditPage, audit_filter: AuditFilter, now: datetime) -> None:
        self.__ui.show("\n" + self.format_log_page(page, audit_filter, now))

    # ----- the chain check -------------------------------------------------------------------

    def format_chain(self, chain: Any) -> str:
        """What Verify the audit log found. chain is the AuditChain App returns; only its answers are used
        (summary() and intact(); the summary names the entries that do not match), so this class needs nothing from the Logic Manager."""
        lines = ["VERIFY THE AUDIT LOG", ConsoleUI.LINE,
                 ("OK: " if chain.intact() else "WARNING: ") + chain.summary()]
        return ConsoleUI.printable(lines)

    def show_chain(self, chain: Any) -> None:
        self.__ui.show("\n" + self.format_chain(chain))
