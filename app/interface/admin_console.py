"""AdminConsole: the admin's session on the terminal (the twin of the admin pages of WebApp)."""

import logging
from datetime import datetime, timezone

from app.application.app import App
from app.interface.admin_view import AdminView
from app.interface.console_ui import ConsoleUI
from app.model.account import Account
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.flag_ticket import FlagTicket
from app.model.overview_page import OverviewPage

logger = logging.getLogger(__name__)


class AdminConsole:
    """What a signed-in admin can do on the terminal: the Overview, one flag (and updating it, as on the web), a
    client's flags, the activity log and the check of the audit log. Updating a flag is the only thing that writes
    (one flag_updated line in the audit log, in the admin's name). TerminalApp signs the admin in, hands over the
    Account and signs out when run() ends, however it ends.

    Every pass of the menu is a new request (begin_request with the admin's name), and every App call that takes an
    actor is given the admin's name, so each audit line written here is the admin's. A step that cannot run says so in
    plain words and returns to the menu; an empty answer ("No flags to handle.") is never used for an error.
    """

    SAFE_ERRORS: tuple[str, ...] = (App.AUDIT_UNAVAILABLE, App.AUDIT_KEY_MISSING, App.FLAGS_UNAVAILABLE,
                                    App.FLAG_ADMIN_ONLY)
    NOT_SAVED: str = "Your update was not saved."
    MENU: tuple[str, ...] = ("Overview", "Open a flag", "A client's flags", "Activity log",
                             "Verify the audit log")

    def __init__(self, app: App, ui: ConsoleUI, view: AdminView, account: Account) -> None:
        """Raises ValueError for anything of the wrong kind, and for an account that is not an admin."""
        if not isinstance(app, App):
            raise ValueError("The admin console needs the App it asks for everything.")
        if not isinstance(ui, ConsoleUI):
            raise ValueError("The admin console needs a ConsoleUI to ask and show on.")
        if not isinstance(view, AdminView):
            raise ValueError("The admin console needs an AdminView to show the pages.")
        if not isinstance(account, Account) or not account.is_admin():
            raise ValueError("Only an admin account can open the admin console.")
        self.__app: App = app
        self.__ui: ConsoleUI = ui
        self.__view: AdminView = view
        self.__account: Account = account
        self.__listed: list[FlagTicket] = []             # the flags of the Overview shown last, to pick one by number

    # ----- the menu --------------------------------------------------------------------------

    def run(self) -> None:
        """Show the admin menu until the admin signs out. The end of input (Ctrl-D) is not caught here: TerminalApp
        leaves cleanly and signs the admin out."""
        self.__ui.show_message(f"\nSigned in as {self.__account.name} (admin).")
        while True:
            self.__app.begin_request(self.__account.name)           # each pass of the menu is a new request
            self.__ui.show_message("\n--- ADMIN: AUDIT AND FLAGS ---")
            picked = self.__ui.ask_choice("What would you like to see?", list(AdminConsole.MENU), allow_back=True,
                                          back_label="Sign out")
            if picked is None:
                return
            try:
                (self.__overview, self.__open_flag, self.__client_flags, self.__activity_log,
                 self.__verify)[picked]()
            except ValueError as error:
                self.__show_error(error, AdminConsole.MENU[picked])

    def __show_error(self, error: ValueError, where: str, not_saved: bool = False) -> None:
        """Tell the admin which kind of problem it is. Only the messages App chose for the admin (SAFE_ERRORS) are
        shown as they are; any other ValueError is not an audit log problem, so it is logged with its details and
        shown as an unexpected error, never as "the audit log is unavailable". not_saved adds that the admin's update
        was not saved."""
        tail = f" {AdminConsole.NOT_SAVED}" if not_saved else ""
        if str(error) in AdminConsole.SAFE_ERRORS:
            logger.error("AdminConsole: %s %s: %s", where, "failed" if not_saved else "could not be shown", error)
            self.__ui.show_error(str(error) + tail)
        else:
            logger.error("AdminConsole: %s failed with an unexpected error: %r", where, error)
            self.__ui.show_unexpected_error()
            if not_saved:
                self.__ui.show_error(AdminConsole.NOT_SAVED)

    def __show_audit_warning(self) -> None:
        """If the last action's audit line could not be written, say so."""
        message = self.__app.audit_failure_message()
        if message:
            self.__ui.show_error(message)

    @staticmethod
    def __now() -> datetime:
        return datetime.now(timezone.utc)

    # ----- 1. the Overview -------------------------------------------------------------------

    def __overview(self) -> None:
        """Ask the range and the tab, then show the Overview a page at a time."""
        names = [AdminView.PRESET_NAMES[preset] for preset in OverviewPage.PRESETS]
        picked = self.__ui.ask_choice("Date range", names, allow_back=True, back_label="Back to the admin menu")
        if picked is None:
            return
        preset = OverviewPage.PRESETS[picked]
        picked = self.__ui.ask_choice("Show which flags?", [OverviewPage.TAB_NAMES[tab] for tab in OverviewPage.TABS],
                                      allow_back=True, back_label="Back to the admin menu")
        if picked is None:
            return
        tab, number, shown = OverviewPage.TABS[picked], 1, ""      # shown: the error just told, if any
        while True:
            try:
                page = self.__app.audit_overview(preset, tab, number, self.__now())
            except ValueError as error:
                if shown and str(error) == shown:      # the same problem again: told once, back to the menu
                    logger.error("AdminConsole: the Overview cannot be reloaded either: %s", error)
                    return
                raise
            shown = ""
            self.__listed = page.rows
            self.__view.show_overview(page)
            options, actions = [], []
            if page.page < page.page_count:
                options.append("Next page")
                actions.append("next")
            if page.page > 1:
                options.append("Previous page")
                actions.append("previous")
            if page.rows:
                options.append("Open a flag from this list")
                actions.append("open")
            action = "back"
            picked = self.__ui.ask_choice("What next?", options, allow_back=True,
                                          back_label="Back to the admin menu") if options else None
            if picked is not None:
                action = actions[picked]
            if action == "next":
                number = page.page + 1
            elif action == "previous":
                number = page.page - 1
            elif action == "open":
                try:
                    self.__open_flag()
                except ValueError as error:            # stay on this page: the range, tab and page are kept
                    self.__show_error(error, "Open a flag")
                    shown = str(error)
                number = page.page
            else:
                return

    # ----- 2. one flag -----------------------------------------------------------------------

    def __open_flag(self) -> None:
        """Ask for a flag and show it with its evidence."""
        flag_id = self.__pick_flag()
        if flag_id is None:
            return
        ticket = self.__show_flag(flag_id)
        while ticket is not None:
            if self.__ui.ask_choice("What next?", ["Update this flag"], allow_back=True, back_label="Back") is None:
                return
            ticket = self.__update_flag(ticket)

    def __update_flag(self, ticket: FlagTicket) -> FlagTicket | None:
        """Ask for an update of this flag and save it. Returns the flag to offer next: the flag fetched fresh after a
        save, the same one if nothing was saved, None if the flag is gone."""
        asked = self.__ask_update(ticket)
        if asked is None:
            self.__ui.show_message("Nothing was changed.")
            return ticket
        status, waiting_on, outcome, note = asked
        flag_id = ticket.flag.flag_id
        result: tuple[FlagTicket | None, list[str], int] | None = None
        failure: ValueError | None = None
        try:
            result = self.__app.update_flag(
                flag_id, self.__account.name, status, note, waiting_on, outcome, self.__now())
        except ValueError as error:
            failure = error
        if result is None or App.FLAG_NOT_SAVED not in result[1]:       # that answer already says it
            self.__show_audit_warning()                 # the line may be missing whether or not the update ran
        if result is None:
            self.__show_error(failure, "Update a flag", not_saved=True)
            return ticket
        updated, problems, sequence = result
        if updated is None or problems:
            text = " ".join(problems) if problems else "That flag could not be found."
            self.__ui.show_error(text if App.FLAG_NOT_SAVED in problems else f"{text} {AdminConsole.NOT_SAVED}")
            if updated is None or App.FLAG_NOT_SAVED in problems:
                return updated                              # gone (None), or not written: the flag has not changed
            return self.__show_again(flag_id, "")           # not valid: it changed meanwhile, show it as it is now
        self.__view.show_update_saved(updated, sequence, status != ticket.status)
        return self.__show_again(flag_id, "Your update was saved, but the flag can't be shown again right now.")

    def __show_again(self, flag_id: str, lead: str) -> FlagTicket | None:
        """Show the flag fresh after an update. If that cannot be done, say so (lead first, then the safe message) and
        return None, so the admin goes back; the real error is logged."""
        try:
            return self.__show_flag(flag_id)
        except ValueError as error:
            logger.error("AdminConsole: the flag could not be shown again after the update: %s", error)
            safe = str(error) if str(error) in AdminConsole.SAFE_ERRORS else ""
            self.__ui.show_error(" ".join(part for part in (lead or "The flag can't be shown again right now.",
                                                            safe) if part))
            return None

    def __ask_update(self, ticket: FlagTicket) -> tuple[str, str, str, str] | None:
        """Ask the status, who the flag waits on (moving to Following up), the outcome (moving to Resolved) and the
        note, in that order. FlagTicket checks the answers; the note is asked again until it does. None if the admin
        backs out (0, or a blank note)."""
        statuses = list(FlagTicket.STATUSES)
        self.__ui.show_message("Pick the status the flag is in now to add a note without moving it.")
        picked = self.__ui.ask_choice("New status", [FlagTicket.STATUSES[key] + (" (current)" if key == ticket.status else "")
                                                     for key in statuses], allow_back=True, back_label="Back")
        if picked is None:
            return None
        status, waiting_on, outcome = statuses[picked], "", ""
        if ticket.needs_waiting_on(status):
            picked = self.__ui.ask_choice("Waiting on", list(FlagTicket.WAITING_ON), allow_back=True, back_label="Back")
            if picked is None:
                return None
            waiting_on = FlagTicket.WAITING_ON[picked]
        if ticket.needs_outcome(status):
            outcomes = list(FlagTicket.OUTCOMES)
            picked = self.__ui.ask_choice("Outcome", [FlagTicket.OUTCOMES[key] for key in outcomes], allow_back=True,
                                          back_label="Back")
            if picked is None:
                return None
            outcome = outcomes[picked]
        while True:
            label = "Why" if status != ticket.status else "Note"
            note = self.__ui.ask_optional_text(f"{label} (required, {FlagTicket.NOTE_MIN}-{FlagTicket.NOTE_MAX} "
                                               "characters; blank or 0 to cancel)")
            if note in ("", "0"):
                return None
            problems = ticket.check_update(status, note, waiting_on, outcome)
            if not problems:
                return status, waiting_on, outcome, note
            for problem in problems:
                self.__ui.show_error(problem)

    def __pick_flag(self) -> str | None:
        """Ask for a flag: its number in the Overview list above, or its id. None if the admin goes back (0)."""
        while True:
            question = ("Flag number from the list, or a flag id (0 to go back)" if self.__listed
                        else "Flag id (0 to go back)")
            answer = self.__ui.ask_text(question)
            if answer == "0":
                return None
            if answer.isascii() and answer.isdigit() and not self.__listed:
                self.__ui.show_error("Show the Overview first to pick a flag by number, or type a flag id.")
                continue
            if answer.isascii() and answer.isdigit():
                if 1 <= int(answer) <= len(self.__listed):
                    return self.__listed[int(answer) - 1].flag.flag_id
                self.__ui.show_error(f"Choose a number from 1 to {len(self.__listed)}, or type a flag id.")
                continue
            return answer

    def __show_flag(self, flag_id: str) -> FlagTicket | None:
        """Fetch the flag fresh and show it with its evidence. None (after saying the flag is gone) if the rules find
        no flag with that id now."""
        ticket, evidence, entries = self.__app.flag_evidence(flag_id, self.__now())
        if ticket is None:
            self.__ui.show_message(f"\n{App.FLAG_GONE}")
            return None
        self.__view.show_flag(ticket, evidence, entries)
        return ticket

    # ----- 3. a client's flags ---------------------------------------------------------------

    def __client_flags(self) -> None:
        ref = self.__ui.ask_client_ref()
        if ref is None:
            return
        tickets = self.__app.client_flags(ref, self.__now())
        self.__view.show_client_flags(ref, tickets)

    # ----- 4. the activity log ---------------------------------------------------------------

    def __activity_log(self) -> None:
        """Ask the filters, then show the log 25 events at a time."""
        audit_filter = self.__ask_filter()
        if audit_filter is None:
            return
        while True:
            now = self.__now()
            log = self.__app.audit_log(audit_filter, now)
            number = audit_filter.page_for(log.total)
            self.__view.show_log_page(log, audit_filter, now)
            options, actions = [], []
            if number < audit_filter.page_count(log.total):
                options.append("Next page")
                actions.append("next")
            if number > 1:
                options.append("Previous page")
                actions.append("previous")
            options.append("Change the filters")
            actions.append("filters")
            picked = self.__ui.ask_choice("What next?", options, allow_back=True, back_label="Back to the admin menu")
            if picked is None:
                return
            if actions[picked] == "filters":
                audit_filter = self.__ask_filter()
                if audit_filter is None:
                    return
            else:
                audit_filter = audit_filter.with_page(number + (1 if actions[picked] == "next" else -1))

    @staticmethod
    def __rejected(**values: object) -> str:
        """What AuditFilter says is wrong with these values ("" if they are fine): the filter owns the rules."""
        try:
            AuditFilter(**values)
        except ValueError as error:
            return str(error)
        return ""

    def __ask_filter(self) -> AuditFilter | None:
        """Ask the eight filters, each again until the filter accepts it. None if the admin goes back."""
        ui = self.__ui
        picked = ui.ask_choice("Date range", [AdminView.LOG_PRESET_NAMES[code] for code in AuditFilter.PRESETS],
                               allow_back=True,
                               back_label="Back to the admin menu")
        if picked is None:
            return None
        preset, date_from, date_to = AuditFilter.PRESETS[picked], "", ""
        if preset == "custom":
            date_from, date_to = self.__ask_dates()
        groups = self.__ask_groups()
        result = AuditFilter.RESULT_CHOICES[ui.ask_choice(
            "Result", [AdminView.RESULT_NAMES[code] for code in AuditFilter.RESULT_CHOICES])]
        actor = self.__ask_officer()
        client_ref = self.__ask_text("Client reference (blank for every client)", "client_ref")
        query = self.__ask_text(f"Search text (blank for none, at most {AuditFilter.MAX_QUERY} characters)", "query")
        sort = AuditFilter.SORT_CHOICES[ui.ask_choice(
            "Order", [AdminView.SORT_NAMES[code] for code in AuditFilter.SORT_CHOICES])]
        flagged_only = ui.ask_yes_no("Only events behind a flag that is not resolved?")
        return AuditFilter(preset, date_from, date_to, groups, result, actor, client_ref, query, sort, 1, flagged_only)

    def __ask_officer(self) -> str:
        """The officer to show: one of the accounts, the terminal or an unknown name (the list the web offers), or
        everyone."""
        names = [account.name for account in self.__app.accounts()] + [App.TERMINAL, App.UNKNOWN]
        picked = self.__ui.ask_choice("Officer", names, allow_back=True, back_label="Everyone (no filter)")
        return "" if picked is None else names[picked]

    def __ask_text(self, question: str, field: str) -> str:
        """A text filter, asked again with the filter's own message until it is accepted."""
        while True:
            answer = self.__ui.ask_optional_text(question)
            problem = AdminConsole.__rejected(**{field: answer})
            if not problem:
                return answer
            self.__ui.show_error(problem)

    def __ask_dates(self) -> tuple[str, str]:
        """A custom range: both dates (YYYY-MM-DD), or neither for all dates."""
        today = AuditFilter.singapore_day(self.__now())
        while True:
            date_from = self.__ui.ask_optional_text("From date (YYYY-MM-DD, blank for all dates)")
            date_to = self.__ui.ask_optional_text("To date (YYYY-MM-DD, blank for all dates)")
            problem = (AdminConsole.__rejected(preset="custom", date_from=date_from, date_to=date_to)
                       or AuditFilter.range_problem(date_from, date_to, today))
            if not problem:
                return date_from, date_to
            self.__ui.show_error(problem)

    def __ask_groups(self) -> list[str] | None:
        """The groups of actions to show: numbers separated by commas, or Enter for all of them."""
        names = list(AuditEvent.GROUPS)
        self.__ui.show_message("Action groups: " + ", ".join(f"{number}. {name}" for number, name in enumerate(names, 1)))
        while True:
            answer = self.__ui.ask_optional_text("Groups to show (numbers separated by commas, blank for all)")
            if not answer:
                return None
            numbers = [part.strip() for part in answer.split(",")]
            if not all(part.isascii() and part.isdigit() and 1 <= int(part) <= len(names) for part in numbers):
                self.__ui.show_error(f"Enter numbers from 1 to {len(names)} separated by commas, or press Enter for all.")
                continue
            return [names[int(part) - 1] for part in numbers]

    # ----- 5. verify -------------------------------------------------------------------------

    def __verify(self) -> None:
        """Check the hash chain of the whole log. The check writes a line in the log, so a line that could not be
        written is reported, whether or not the check itself ran."""
        try:
            chain = self.__app.verify_audit_log(self.__account.name)
        finally:
            self.__show_audit_warning()
        self.__view.show_chain(chain)
