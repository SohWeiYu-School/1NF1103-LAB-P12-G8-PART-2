"""TerminalApp: the command line front end, the twin of WebApp."""

import functools
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.application.app import App
from app.interface.case_builder import CaseBuilder
from app.interface.client_form import ClientForm
from app.interface.console_ui import ConsoleUI
from app.interface.report_view import ReportView
from app.model.audit_filter import AuditFilter
from app.model.client_record import ClientRecord
from app.model.trail_filter import TrailFilter
from app.model.verdict import Verdict

logger = logging.getLogger(__name__)


class TerminalApp:
    """The menu and every screen of the command line app. It asks the officer, shows the answers and calls
    App's public methods for everything else: the rules (assessing, saving, archiving, the audit log) are App's,
    so the web app and the terminal always agree. Like WebApp, it is the only front end that may call App;
    it never works a manager's object itself.
    """

    GOODBYE: str = "Thank you for using Orbit. Goodbye."      # shown for 0. Quit and for the end of input (Ctrl-D)

    def __init__(self, app: App, ui: ConsoleUI | None = None) -> None:
        """app is the App to ask. ui is the screen to use (App passes its own, so there is one screen)."""
        if not isinstance(app, App):
            raise ValueError("The terminal needs the App it asks for everything.")
        self.__app: App = app
        self.__ui: ConsoleUI = ui or ConsoleUI()
        self.__report_view: ReportView = ReportView(self.__ui)
        self.__client_form: ClientForm = ClientForm(self.__ui, self.__report_view)
        self.__case_builder: CaseBuilder = CaseBuilder(self.__ui, app.case_schema())

    # ----- starting ------------------------------------------------------------------------

    def start(self, arguments: list[str]) -> int:
        """Run the command line app after App has checked the options and the settings. Returns the exit
        code (0 = fine).

            (no arguments)          the menu
            --case FILE             assess one case file
            --all-samples           assess every sample case
        """
        if not self.__app.ai_available():
            self.__ui.show_error("No OPENAI_API_KEY set: only saved AI replies can be used.")
        try:
            if "--all-samples" in arguments:
                paths = self.__app.sample_case_files()
                results = [self.run_case_file(path) for path in paths]
                return 0 if paths and all(results) else 1
            if "--case" in arguments:
                position = arguments.index("--case")
                if position + 1 >= len(arguments):
                    self.__ui.show_error("--case needs a file path")
                    return 1
                return 0 if self.run_case_file(arguments[position + 1]) else 1
            self.run_menu()
            return 0
        except EOFError:                          # Ctrl-D: nobody can answer any more, so leave cleanly
            logger.info("TerminalApp: the end of input was reached, leaving the app")
            self.__ui.show_message("\n" + TerminalApp.GOODBYE)
            return 0
        except KeyboardInterrupt:
            self.__ui.show_message("\nStopped.")
            return 130
        except Exception:
            logger.exception("Unexpected error in the command line app")
            self.__ui.show_unexpected_error()
            return 1

    def run_menu(self) -> None:
        """Show the main menu until the officer chooses to leave."""
        app = self.__app
        app.begin_request(App.TERMINAL)
        try:
            self.__ui.show_message(f"{len(app.all_assessments(include_archived=True))} saved assessment(s) loaded.")
        except ValueError as error:            # App has logged the real error and written the audit line
            self.__ui.show_error(str(error))
        while True:
            app.begin_request(App.TERMINAL)          # each pass of the menu is a new request
            choice = self.__ui.show_app_menu()
            if choice == "1":
                record = self.__client_form.create_new_client(
                    save_fn=functools.partial(app.save_client, new_client=True),
                    upload_fn=app.upload_document, is_taken_fn=app.client_ref_taken)
                if record is not None:
                    self.__maybe_assess(record)
            elif choice == "2":
                record = self.__new_client_from_documents()
                if record is not None:
                    self.__maybe_assess(record)
            elif choice == "3":
                self.__client_form.find_existing_client(
                    find_fn=app.find_client, save_fn=app.save_client,
                    download_fn=app.download_document, upload_fn=app.upload_document)
            elif choice == "4":
                ref = self.__ui.ask_client_ref()
                if ref is None:
                    continue
                try:
                    record = app.find_client(ref)
                except ValueError as error:
                    self.__ui.show_error(str(error))
                    continue
                if record is None:
                    self.__ui.show_error(f"No client found with reference {ref}.")
                    continue
                self.__maybe_assess(record)
            elif choice == "5":
                self.list_assessments()
            elif choice == "6":
                try:
                    clients = app.all_clients()
                except ValueError as error:
                    self.__ui.show_error(str(error))
                    continue
                activity, note = None, ""
                if clients:                            # with no clients there is nothing to show activity for
                    try:
                        activity = app.last_activity()
                    except ValueError as error:        # the client list still shows, without the column
                        logger.error("TerminalApp.run_menu: the last activity of the clients cannot be shown: %r",
                                     error)
                        note = f"{App.AUDIT_UNAVAILABLE} The last activity of each client cannot be shown."
                self.__report_view.show_client_list(clients, activity, note)
                self.__ui.read_answer("Press Enter to continue...")
            elif choice == "7":
                self.__ui.show_message("\n--- Synchronizing Local Data to Cloud Database ---")
                self.__ui.show_sync_result(app.sync_to_cloud())
            elif choice == "8":
                self.__client_history()
            elif choice == "0":
                self.__ui.show_message("\n" + TerminalApp.GOODBYE)
                break

    # ----- assessing ---------------------------------------------------------------------------

    def __require_settings(self) -> None:
        """Raises RuntimeError(SETTINGS_UNAVAILABLE) instead of running on empty rules."""
        if not self.__app.settings_ok():
            raise RuntimeError(App.SETTINGS_UNAVAILABLE)

    def __prepare_case(self, record: ClientRecord) -> dict | None:
        """The case to assess, built from a saved client record. The officer is only asked for
        what cannot be read from the record. None if no usable case could be made."""
        case, missing = self.__app.read_case(record)
        if case is None:
            self.__ui.show_error("Needed before the assessment can run: " + ", ".join(missing))
            case = self.__case_builder.build(record)
            if case is None:
                return None
        problems = self.__case_builder.validate_case(case)
        if problems:
            self.__case_builder.show_case_problems(case["client_ref"], problems)
            return None
        return case

    def assess_client_record(self, record: ClientRecord) -> Verdict | None:
        """The command line's assessment of a saved client: prepare, run, save, show.
        Returns the Verdict, or None if no assessment could be made."""
        self.__require_settings()
        app = self.__app
        case = self.__prepare_case(record)
        if case is None:
            return None
        self.__ui.show_message(f"\nAssessing {case['client_ref']}: documents, crime scan, forecast "
                               "and benchmark together.")
        result = app.assess(case, record.documents(), on_step=self.__show_step)
        if result is None:
            self.__ui.show_error("The assessment was stopped. Nothing was saved.")
            return None
        saved = app.save_assessment(result, record, on_step=self.__show_step)
        verdict = result["verdict"]
        self.__report_view.show_verdict_report(verdict, crime_result=result.get("crime_result"),
                                               typologies=result.get("typologies"))
        if saved:
            self.__ui.show_message("Assessment saved.")
            if app.client_outcome_failed():
                self.__ui.show_error(App.OUTCOME_NOT_UPDATED)
        else:
            self.__ui.show_error("Could not save the assessment.")
        return verdict

    def run_case_file(self, path: str) -> bool:
        """Assess a case file (the same assessment as the menu). False if it could not be assessed."""
        self.__require_settings()
        app = self.__app
        case = app.load_case_file(path)
        if case is not None and not app.is_forecasting_case(case):
            self.__ui.show(f"\n{os.path.basename(path)}: not in the forecasting format "
                           "(it's a client record), skipped. Use the menu to assess it.")
            return True
        problems = self.__case_builder.validate_case(case)
        if problems:
            self.__case_builder.show_case_problems(path, problems)
            return False
        self.__ui.show_message(f"\nAssessing {case['client_ref']} ({os.path.basename(path)}).")
        result = app.assess(case, on_step=self.__show_step)
        if result is None:
            self.__ui.show_error("The assessment was stopped. Nothing was saved.")
            return False
        if not app.save_assessment(result, on_step=self.__show_step):
            self.__ui.show_error("Could not save the assessment.")
        self.__report_view.show_verdict_report(result["verdict"], ask_for_evidence=False,
                                               crime_result=result.get("crime_result"),
                                               typologies=result.get("typologies"))
        return result["forecast"] is not None

    def __maybe_assess(self, record: ClientRecord) -> None:
        """Check the rate limit; if clear, run the assessment."""
        limiter = self.__app.rate_limiter()
        allowed, wait = limiter.check("cli")
        if not allowed:
            self.__ui.show_rate_limit_error(wait)
            return
        limiter.record("cli")
        self.assess_client_record(record)

    def __show_step(self, number: int, label: str) -> None:
        self.__ui.show_step(number, len(self.__app.steps()), label)

    # ----- a new client from documents -----------------------------------------------------------

    def __new_client_from_documents(self) -> ClientRecord | None:
        """Read a folder of documents, pre-fill the client, ask for what is missing, show a
        summary to check, then save. Returns the saved record (to assess) or None."""
        app = self.__app
        # 1. Which folder
        while True:
            folder = self.__client_form.ask_document_folder()
            if folder is None:
                return None
            paths = app.list_document_folder(folder)
            if paths is None:
                self.__ui.show_error(f"Folder not found: {folder}")
            elif not paths:
                self.__ui.show_error("No PDF, Word, Excel, text or image files in that folder.")
            else:
                break
        self.__ui.show_documents_found(paths)

        # 2. Read the documents and let the AI pull out the details
        self.__ui.show_message(f"\nReading {len(paths)} document(s) with AI... this can take up to a minute.")
        extracted, warnings = app.read_documents([app.read_document_for_extraction(path) for path in paths])
        if extracted is None:
            self.__ui.show_ai_unavailable("Document reading")
            if not self.__ui.ask_yes_no("Type the details in yourself?"):
                return None
            extracted = {}

        # 3. Build the record and ask for anything missing
        builder = app.record_builder()
        try:
            client_ref = app.new_client_ref()
        except ValueError as error:
            self.__ui.show_error(str(error))
            return None
        try:
            document_record, _, dropped = builder.build(extracted, client_ref)
        except ValueError as error:
            logger.error("TerminalApp.__new_client_from_documents: the AI's reading is not a possible record: %r",
                         error)
            self.__ui.show_error(f"The details read from the documents cannot be used because {error}.")
            if not self.__ui.ask_yes_no("Type the details in yourself?"):
                return None
            extracted = {}
            document_record, _, dropped = builder.build(extracted, client_ref)
        if dropped:
            messages = [entry["message"] for entry in dropped]
            logger.warning("TerminalApp.__new_client_from_documents: left out of the AI's reading: %s",
                           " | ".join(messages))
            self.__ui.show_dropped_fields(messages)
        record = document_record
        missing = builder.missing_fields(record)
        self.__ui.show_missing_intro(len(missing))
        for field in missing:
            record = self.__fill_field(builder, record, field)
        # a dropped detail the form does not insist on is asked for too: the message said to enter it
        optional = [entry["optional_field"] for entry in dropped if entry["optional_field"]]
        if optional:
            self.__ui.show_optional_intro(len(optional))
            for field in optional:
                record = self.__fill_field(builder, record, field, optional=True)

        # 4. Summary to check, edit until right, then save or discard
        notes = list(extracted.get("notes") or []) + list(warnings)
        while True:
            self.__report_view.show_document_summary(builder.summarise(record, document_record), paths, notes,
                                                     builder.check(record))
            action = self.__ui.ask_document_record_action()
            if action == "discard":
                self.__ui.show_message("\nClient discarded. Nothing was saved.")
                return None
            if action == "edit":
                record = builder.finish(self.__client_form.edit_existing_client(record, app.upload_document))
                for field in builder.missing_fields(record):
                    record = self.__fill_field(builder, record, field)
                continue
            break

        # 5. Keep the documents with the client, then save
        for path in paths:
            stored = app.upload_document(path)
            if stored is None:
                self.__ui.show_error(f"Could not keep a copy of {os.path.basename(path)}.")
            else:
                record.add_document({"file_name": os.path.basename(path), "file_path": stored})
        if not app.save_client(record, new_client=True):
            self.__ui.show_error("The client could not be saved.")
            return None
        self.__ui.show_message(f"\nClient saved. Reference: {record.client_ref} "
                               f"({len(record.documents())} document(s) attached).")
        return record if self.__client_form.ask_after_save(record) else None

    def __fill_field(self, builder: Any, record: ClientRecord, field: dict, optional: bool = False) -> ClientRecord:
        """Ask the officer for one missing detail until the record accepts it. An optional detail
        may be left empty by pressing Enter (the record is then unchanged)."""
        while True:
            try:
                if optional:
                    answer = self.__client_form.ask_optional_field(field)
                    return record if answer in (None, []) else builder.set_path(record, field["path"], answer)
                return builder.set_path(record, field["path"], self.__client_form.ask_missing_field(field))
            except ValueError as error:
                logger.warning("TerminalApp: %s was not accepted: %r", field["label"], error)
                self.__ui.show_error(f"That value cannot be used because {error}. Please try again.")

    # ----- saved assessments ---------------------------------------------------------------------

    def list_assessments(self) -> None:
        """List saved assessments (filtered by outcome) and optionally open one."""
        outcomes = ["(all)", *Verdict.OUTCOMES, "(include archived)"]
        choice = self.__ui.ask_choice("Show which outcome?", outcomes, allow_back=True)
        if choice is None:
            return          # 0 = back to the main menu
        picked = outcomes[choice]
        with_archived = picked == "(include archived)"      # every outcome, archived ones too
        try:
            matches = self.__app.all_assessments(include_archived=with_archived,
                                                 outcome="" if picked == "(all)" or with_archived else picked)
        except ValueError as error:                         # App has logged the real error
            self.__ui.show_error(str(error))
            return
        # One state per record (not per id: old records may share a missing id).
        states = [App.archive_state(match) for match in matches] if with_archived else None
        self.__report_view.show_assessment_list(matches, states)
        if not matches:
            return
        actions = ["Open one in full", "Archive or restore one"]
        action = self.__ui.ask_choice("What next?", actions, allow_back=True)
        if action == 0:
            index = self.__pick_assessment(matches, states, "Which one?")
            if index is not None:
                self.__open_assessment(matches[index])
        elif action == 1:
            self.__change_archive(matches)

    def __pick_assessment(self, records: list[dict], states: list[str] | None, question: str,
                          back_label: str = "Back") -> int | None:
        """Ask which of the listed assessments (states: one per record, or None for all active); its position
        in records, or None if the officer goes back."""
        states = states or [""] * len(records)
        labels = [ReportView.format_assessment_row(record, state, labelled=True).rstrip()
                  for record, state in zip(records, states)]
        return self.__ui.ask_choice(question, labels, allow_back=True, back_label=back_label)

    def __open_assessment(self, chosen: dict) -> None:
        """Show one saved assessment in full: the combined report, or a forecast-only one saved before it."""
        unreadable = ("This saved assessment could not be read, so its report cannot be "
                      "shown. The other saved assessments are not affected.")
        if chosen.get("report"):                                         # the combined assessment
            verdict = self.__app.saved_verdict(chosen)
            if verdict is None:
                self.__ui.show_error(unreadable)
            else:
                try:
                    self.__report_view.show_verdict_report(verdict)
                except (KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
                    logger.error("TerminalApp.__open_assessment: the saved report %s cannot be shown: %r",
                                 chosen.get("assessment_id"), error, exc_info=True)
                    self.__ui.show_error(unreadable)
            return
        try:
            self.__report_view.show_onboarding(chosen["assessment"])     # saved before the combined verdict
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
            logger.error("TerminalApp.__open_assessment: the saved assessment %s cannot be shown: %r",
                         chosen.get("assessment_id"), error, exc_info=True)
            self.__ui.show_error(unreadable)

    def __change_archive(self, records: list[dict]) -> None:
        """Ask which of these assessments to archive or restore, ask for the reason (archive only) and do it.
        Every result is told to the officer in the words the web app uses (App.archive_message); a result that
        did nothing is never shown as done."""
        states = [App.archive_state(record) for record in records]
        index = self.__pick_assessment(records, states, "Archive or restore which one?", "Cancel")
        if index is None:
            return
        chosen, state = records[index], states[index]
        assessment_id = str(chosen.get("assessment_id") or "").strip()
        if not assessment_id:
            self.__ui.show_error("This saved assessment has no id, so it cannot be archived or restored.")
            return
        if state == App.ARCHIVE_UNREADABLE:
            self.__ui.show_error(App.archive_message(App.ARCHIVE_UNREADABLE, True))
            return
        archive = state == App.ARCHIVE_ACTIVE
        reason = ""
        if not self.__ui.ask_yes_no("Archive this assessment? It is hidden from the lists, not deleted."
                                    if archive else "Restore this assessment to the lists?"):
            return
        while archive:
            reason = self.__ui.ask_optional_text(
                f"Reason (optional, up to {App.MAX_ARCHIVE_REASON} characters, Enter to skip)")
            problem = App.archive_reason_problem(reason)
            if not problem:
                break
            self.__ui.show_error(problem)
        try:
            result = (self.__app.archive_assessment(assessment_id, reason, App.TERMINAL) if archive
                      else self.__app.restore_assessment(assessment_id, App.TERMINAL))
        except ValueError as error:
            logger.error("TerminalApp.__change_archive: the saved assessments cannot be read: %r", error)
            self.__ui.show_error(App.ASSESSMENTS_UNAVAILABLE)
            return
        message = App.archive_message(result, archive, reason)
        if result in App.ARCHIVE_DONE_RESULTS:
            self.__ui.show_message(message)
        else:
            self.__ui.show_error(message)

    # ----- a client's history ---------------------------------------------------------------------

    def __client_history(self) -> None:
        """Menu 8: one client's assessments (archive marks), archive/restore, open one in full and the audit
        trail with its Show / When filter."""
        ref = self.__ui.ask_client_ref()
        if ref is None:
            return
        try:
            record = self.__app.find_client(ref)
        except ValueError as error:
            self.__ui.show_error(str(error))
            return
        if record is None:
            self.__ui.show_error(f"No client found with reference {ref}.")
            return
        client_ref = record.client_ref
        self.__ui.show_message(f"\nClient {client_ref}  {record.profile.name}")
        assessments = self.__show_client_assessments(client_ref)
        trail_filter = TrailFilter()
        options = ["Show history (audit trail)", "Change the history filter", "Open an assessment in full",
                   "Archive or restore an assessment"]
        while True:
            choice = self.__ui.ask_choice("What next?", options, allow_back=True)
            if choice is None:
                return
            if choice == 1:
                trail_filter = self.__ask_trail_filter()
            if choice in (0, 1):
                self.__show_trail(client_ref, trail_filter)
                continue
            if assessments is None:                  # it could not be read before: try again
                assessments = self.__show_client_assessments(client_ref)
            if not assessments:
                if assessments is not None:
                    self.__ui.show_message("This client has no saved assessments.")
                continue
            if choice == 2:
                index = self.__pick_assessment(assessments, [App.archive_state(a) for a in assessments],
                                               "Which one?")
                if index is not None:
                    self.__open_assessment(assessments[index])
            else:
                self.__change_archive(assessments)
                assessments = self.__show_client_assessments(client_ref)

    def __show_client_assessments(self, client_ref: str) -> list[dict] | None:
        """Show the client's saved assessments (archived ones marked) and return them; None, after saying so,
        if the saved assessments cannot be read."""
        try:
            assessments = self.__app.client_assessments(client_ref, include_archived=True)
        except (OSError, ValueError) as error:
            logger.error("TerminalApp.__show_client_assessments: the saved assessments cannot be read: %r", error)
            self.__app.read_failed("assessments", App.TERMINAL)
            self.__ui.show_error(App.ASSESSMENTS_UNAVAILABLE)
            return None
        self.__ui.show_message("\nSaved assessments")
        self.__report_view.show_assessment_list(assessments, [App.archive_state(a) for a in assessments])
        return assessments

    def __ask_trail_filter(self) -> TrailFilter:
        """Ask for the Show and When choices (and the dates, for a custom range) of the history. A date the
        model refuses is shown with its own message and asked again."""
        shows, whens = list(TrailFilter.SHOW_LABELS), list(TrailFilter.WHEN)
        show = shows[self.__ui.ask_choice("Show which events?", list(TrailFilter.SHOW_LABELS.values()))]
        while True:
            when = whens[self.__ui.ask_choice("Which period?", [TrailFilter.WHEN_LABELS[w] for w in whens])]
            while True:
                first = last = ""
                if when == "custom":
                    first = self.__ui.ask_optional_text("From date (YYYY-MM-DD, 0 to go back)")
                    if first == "0":
                        break                                # back to "Which period?"
                    last = self.__ui.ask_optional_text("To date (YYYY-MM-DD)")
                    if last == "0" or (not first and not last):
                        break
                try:
                    trail_filter = TrailFilter(show, when, first, last)
                except ValueError as error:
                    self.__ui.show_error(str(error))
                    continue
                if when != "custom":
                    return trail_filter
                rule = AuditFilter.range_problem(first, last, AuditFilter.singapore_day(datetime.now(timezone.utc)))
                if rule:
                    self.__ui.show_error(rule)
                else:
                    return trail_filter

    def __show_trail(self, client_ref: str, trail_filter: TrailFilter) -> None:
        """Show the client's audit trail, newest first, through the filter. An audit log that cannot be read
        is said so; it is never shown as "no history"."""
        try:
            events, unreadable = self.__app.audit_trail(client_ref)
        except ValueError as error:
            logger.error("TerminalApp.__show_trail: the audit log cannot be read: %r", error)
            self.__ui.show_error(App.AUDIT_UNAVAILABLE)
            return
        now = datetime.now(timezone.utc)
        shown = [event for event in events if trail_filter.matches(event, now)]
        dates = f" ({trail_filter.date_from or '...'} to {trail_filter.date_to or '...'})" \
            if trail_filter.when == "custom" else ""
        self.__ui.show_message(f"\nShowing: {TrailFilter.SHOW_LABELS[trail_filter.show]}, "
                               f"{TrailFilter.WHEN_LABELS[trail_filter.when]}{dates}")
        self.__report_view.show_client_history(shown, len(events), unreadable)
