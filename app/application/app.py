"""App: creates every object of the system and coordinates them."""

import copy
import functools
import logging
import logging.handlers
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from dotenv import load_dotenv

from app.ai.benchmark_ai import BenchmarkAI
from app.ai.document_ai import DocumentAI
from app.ai.forecast_ai import ForecastAI
from app.ai.research_ai import ResearchAI
from app.ai.response_cache import ResponseCache
from app.ai.typology_ai import TypologyAI
from app.application.assessment_runner import AssessmentRunner
from app.data.assessment_repository import AssessmentRepository
from app.data.audit_repository import AuditRepository
from app.data.case_files import CaseFiles
from app.data.client_repository import ClientRepository
from app.data.cloud_sync import CloudSync
from app.data.config_reader import ConfigReader
from app.data.document_store import DocumentStore
from app.data.mongo_repository import MongoRepository
from app.data.repository import Repository
from app.interface.case_builder import CaseBuilder
from app.interface.client_form import ClientForm
from app.interface.console_ui import ConsoleUI
from app.interface.rate_limiter import RateLimiter
from app.interface.report_view import ReportView
from app.logic.case_reader import CaseReader
from app.logic.audit_chain import AuditChain
from app.logic.audit_insights import AuditInsights
from app.logic.audit_stats import AuditStats
from app.logic.case_timeline import CaseTimeline
from app.logic.document_record_builder import DocumentRecordBuilder
from app.logic.record_diff import RecordDiff
from app.model.account import Account
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.audit_page import AuditPage
from app.model.audit_policy import AuditPolicy
from app.model.client_record import ClientRecord
from app.model.config import Config
from app.model.declaration import Declaration
from app.model.flag import Flag
from app.model.flag_ticket import FlagTicket
from app.model.overview_page import OverviewPage
from app.model.trail_filter import TrailFilter
from app.model.verdict import Verdict

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class App:
    """Orbit, the Source of Wealth screening system.

    App is the only place that knows about all four managers. It creates the Data, AI,
    Logic and IO objects, keeps them, and passes data between them; the managers never
    import each other. main.py chooses the AI brand by building an ai_caller and hands it
    to App, so nothing below main.py knows which brand is in use.

    App also decides what happens when a step of an assessment fails: stop, or carry on
    without it (see CRITICAL_STEPS).
    """

    # A step named here stops the assessment when it fails: without it no verdict can be
    # trusted. Any other failed step is shown to the officer, written into the report as
    # "not run", and the assessment carries on.
    CRITICAL_STEPS: tuple[str, ...] = ("Deciding the verdict",)
    # Network libraries that log every connection step; only their warnings are kept.
    NOISY_LOGGERS: tuple[str, ...] = ("httpx", "httpcore", "httpx2", "httpcore2", "openai", "urllib3",
                                      "google_genai", "hpack", "pymongo")
    # What the user is told when the settings files cannot be loaded (the real error goes to the log).
    SETTINGS_UNAVAILABLE: str = "The app's settings could not be loaded. Please contact your administrator."
    AUDIT_KEY_MISSING: str = "The audit log is not set up (its key is missing). Please contact your administrator."
    MIN_AUDIT_KEY: int = 32           # a shorter AUDIT_KEY in .env counts as not set
    LOG_HANDLER_NAME: str = "app_log_file"
    # logs/app.log starts a new file at this size and keeps this many old ones (app.log.1 ... .3)
    LOG_MAX_BYTES: int = 5 * 1024 * 1024
    LOG_BACKUPS: int = 3
    # Who did an action when nobody signed in: the command line.
    TERMINAL: str = AuditEvent.TERMINAL
    UNKNOWN: str = AuditEvent.UNKNOWN
    OFFICER_PORTAL: str = "officer"
    ADMIN_PORTAL: str = "admin"
    SIGN_IN_EMPTY: str = "Please enter your name and password."
    SIGN_IN_WRONG: str = "Name or password is wrong."
    SIGN_IN_OFFICER_AT_ADMIN: str = "This is an officer account. Officers sign in at / (the officer portal)."
    SIGN_IN_ADMIN_AT_OFFICER: str = "This is an admin account. Admins sign in at /admin."
    MAX_SIGN_IN_TEXT: int = 200               # longer names and passwords are refused as wrong, not checked
    CLIENT_COLLECTION: str = "client_cases"
    ASSESSMENT_COLLECTION: str = "ai_assessments"
    # What the user is told when saved records cannot be read (the real error goes to the log).
    CLIENTS_UNAVAILABLE: str = "We can't load the client database right now. Please try again later."
    ASSESSMENTS_UNAVAILABLE: str = "We can't load the saved assessments right now. Please try again later."
    # Shown when an action was done and kept, but its line could not be added to the audit log.
    AUDIT_NOT_WRITTEN: str = "Saved, but this change could not be written to the audit log."
    # Shown instead when the action saved nothing (a refusal, a sign-in, a check, a download, a failed save).
    AUDIT_LINE_NOT_WRITTEN: str = "This action could not be written to the audit log."
    AUDIT_UNAVAILABLE: str = "We can't load the audit log right now. Please try again later."
    # Shown when an admin's update to a flag could not be written to the audit log (so it was NOT saved).
    FLAG_NOT_SAVED: str = "Your update was not saved. The audit log can't be written right now. Please try again later."
    FLAG_GONE: str = ("That flag no longer exists. The rule may no longer match, for example after the log "
                      "was repaired.")
    FLAG_ADMIN_ONLY: str = "Only an administrator can update a flag."
    FLAGS_UNAVAILABLE: str = "The flags could not be worked out right now. Please try again later."
    MAX_REFUSED_TEXT: int = 200
    REFUSAL_REPEAT_SECONDS: int = 60          # the same refusal by the same person is written once in this time
    # Shown when an assessment was saved but the client's outcome could not be written onto the client record.
    OUTCOME_NOT_UPDATED: str = "The assessment was saved, but the client's outcome could not be updated."
    UNEXPECTED_ERROR_STEP: str = "Unexpected error"      # the "step" the audit log gets when a run or save raises

    # The archive states and results of an assessment, so the web app can ask App without
    # reaching into the data manager.
    ARCHIVE_ACTIVE: str = AssessmentRepository.ACTIVE
    ARCHIVE_ARCHIVED: str = AssessmentRepository.ARCHIVED
    ARCHIVE_UNREADABLE: str = AssessmentRepository.UNREADABLE
    ARCHIVE_CHANGED: str = AssessmentRepository.CHANGED
    ARCHIVE_NOT_FOUND: str = AssessmentRepository.NOT_FOUND
    ARCHIVE_NO_CHANGE: str = AssessmentRepository.NO_CHANGE
    ARCHIVE_NOT_SAVED: str = AssessmentRepository.NOT_SAVED
    ARCHIVE_BAD_REASON: str = "bad_reason"
    MAX_ARCHIVE_REASON: int = AssessmentRepository.MAX_REASON_LENGTH

    def __init__(self, ai_caller: Callable[[str, dict, dict], str | None] | None = None,
                 root: str = ROOT_DIR, data_folder: str = "data",
                 rules: type[AuditInsights] = AuditInsights) -> None:
        if not isinstance(rules, type):
            raise ValueError("The flag rules must be a class (AuditInsights or one that works like it).")
        self.__root: str = root
        # The class that works the flags out; a test hands in a made-up one.
        self.__rules: type[AuditInsights] = rules
        # Settings errors are logged while App is built, so the log file must exist before that.
        if not logging.getLogger().handlers:
            self.__configure_logging()
        load_dotenv(os.path.join(root, ".env"))
        data_dir = data_folder if os.path.isabs(data_folder) else os.path.join(root, data_folder)
        database_dir = os.path.join(data_dir, "local database")

        # Settings (read by the Data Manager, held by a Domain Model object)
        self.__config_reader: ConfigReader = ConfigReader(os.path.join(root, "config"))
        self.__settings_ok: bool = True
        try:
            policy_file, vocabulary_file, accounts_file = (self.__config_reader.read(name)
                                                           for name in ConfigReader.FILE_NAMES)
            entries = accounts_file.get("accounts")
            if not isinstance(entries, list):
                raise ValueError("config/accounts.json 'accounts' must be a list")
            accounts = [Account.from_dict(entry) for entry in entries]
        except (OSError, ValueError) as error:
            # App must not crash while it is built, and must not run on empty rules: start() and
            # start_web() see this flag, tell the officer and stop. The reader has logged the details.
            logger.error("App: the settings could not be loaded: %r", error)
            self.__settings_ok = False
            policy_file, vocabulary_file, accounts = {}, {}, []
        self.__config: Config = Config(policy_file, vocabulary_file, accounts)
        policy = self.__config.policy

        # Data Manager
        self.__clients: Repository = ClientRepository(os.path.join(database_dir, "sow_cases.json"))
        self.__assessments: AssessmentRepository = AssessmentRepository(
            os.path.join(database_dir, "ai_assessments.json"))
        # The key signs the audit chain. App must not crash while it is built without one: start() and
        # start_web() see audit_key_ok() and stop. The key itself is never logged or shown.
        self.__audit_key: str = os.getenv("AUDIT_KEY", "").strip()
        if len(self.__audit_key) < App.MIN_AUDIT_KEY:
            logger.error("App: AUDIT_KEY is not set or is shorter than %d characters, so the audit log cannot "
                         "be written or checked", App.MIN_AUDIT_KEY)
            self.__audit_key = ""
        self.__audit: AuditRepository = AuditRepository(os.path.join(database_dir, "audit_log.json"),
                                                        key=self.__audit_key)
        # Whether the last audit line of this thread could not be written (each web request has its own thread).
        self.__audit_note: threading.local = threading.local()
        # The open-flag count with the fingerprint of the log it was worked out from (rows, last row's hash).
        self.__flag_count_lock: threading.Lock = threading.Lock()
        self.__flag_count: tuple[tuple[int, str], int] | None = None
        self.__recent_refusals: dict[tuple[str, str], float] = {}     # (actor, what) -> when it was last written
        self.__refusal_lock: threading.Lock = threading.Lock()
        # Document ids are paths from the folder that holds the data folder ("data/documents/...").
        self.__documents: DocumentStore = DocumentStore(os.path.join(data_dir, "documents"),
                                                        root=os.path.dirname(data_dir))
        self.__case_files: CaseFiles = CaseFiles(os.path.join(root, "data", "sample"))   # shipped with the code
        uri = os.getenv("MONGODB_URI") or ""
        state_path = os.path.join(database_dir, "sync_state.json")
        self.__syncs: list[CloudSync] = [
            CloudSync(self.__clients, MongoRepository(App.CLIENT_COLLECTION, "client_ref", uri), state_path),
            CloudSync(self.__assessments, MongoRepository(App.ASSESSMENT_COLLECTION, "assessment_id", uri),
                      state_path)]

        # AI Manager: every service is handed the same caller; the cache is used by the AssessmentRunner
        self.__ai_caller: Callable | None = ai_caller
        cache_folder = os.getenv("CACHE_DIR") or os.path.join(data_folder, "cache")
        self.__response_cache: ResponseCache = ResponseCache(
            cache_folder if os.path.isabs(cache_folder) else os.path.join(root, cache_folder))
        # Kept by App because the new-client screen also reads documents outside an assessment.
        self.__document_ai: DocumentAI = self.__create_document_ai()
        self.__runner: AssessmentRunner = self.__create_runner(policy)

        # IO Manager
        self.__ui: ConsoleUI = ConsoleUI()
        self.__report_view: ReportView = ReportView(self.__ui)
        self.__client_form: ClientForm = ClientForm(self.__ui, self.__report_view)
        schema = self.__case_files.load(os.path.join(root, "app", "schemas", "case_input.schema.json"), default={})
        self.__case_builder: CaseBuilder = CaseBuilder(self.__ui, schema)
        limits = policy.get("assessment_rate_limit", {})
        if not isinstance(limits, dict):
            # start() reports the setting through ConfigReader.problems() and stops.
            logger.warning("App: 'assessment_rate_limit' in policy.json must be an object, not %r; "
                           "using the default rate limit", limits)
            limits = {}
        try:
            self.__limiter: RateLimiter = RateLimiter(
                limits.get("cooldown_seconds", RateLimiter.DEFAULT_COOLDOWN_SECONDS), limits.get("enabled", True))
        except ValueError as error:
            # start() reports the setting through ConfigReader.problems() and stops; App itself must not crash.
            logger.error("App: the assessment rate limit setting is not valid, using the default: %s", error)
            self.__limiter = RateLimiter()
        audit_settings = policy.get("audit", {})
        if not isinstance(audit_settings, dict):
            # start() reports the setting through ConfigReader.problems() and stops.
            logger.error("App: 'audit' in policy.json must be an object, not %r; using the default audit "
                         "settings", audit_settings)
            audit_settings = {}
        try:
            self.__audit_policy: AuditPolicy = AuditPolicy.from_dict(audit_settings)
        except ValueError as error:
            # start() reports the setting through ConfigReader.problems() and stops; App itself must not crash.
            logger.error("App: the audit settings are not valid, using the defaults: %s", error)
            self.__audit_policy = AuditPolicy()

    # ----- what the front ends are given ----------------------------------------------

    @property
    def audit_policy(self) -> AuditPolicy:
        """The settings the flag rules use (working hours, windows, limits)."""
        return self.__audit_policy

    @property
    def config(self) -> Config:
        return self.__config

    @staticmethod
    def typologies_checked(report: dict | None) -> bool:
        """False when the report says the crime scan's research could not run, so the typologies it
        shows were taken from the AI unchecked. Works for a fresh report and a saved one alike."""
        for section in (report or {}).get("sections", []):
            if section.get("title") == "Could not run":
                if any(item.get("text") == AssessmentRunner.RESEARCH_STEP for item in section.get("items", [])):
                    return False
        return True

    def settings_ok(self) -> bool:
        """False when the settings files could not be loaded: no assessment can then be trusted."""
        return self.__settings_ok

    def audit_key_ok(self) -> bool:
        """False when AUDIT_KEY is missing or too short: the audit log cannot then be trusted."""
        return bool(self.__audit_key)

    def __require_settings(self) -> None:
        """Raises RuntimeError(SETTINGS_UNAVAILABLE) instead of running on empty rules."""
        if not self.__settings_ok:
            raise RuntimeError(App.SETTINGS_UNAVAILABLE)

    def steps(self) -> list[str]:
        """The steps of an assessment, in the order they are announced."""
        return list(AssessmentRunner.STEPS)

    @staticmethod
    def today() -> str:
        """Every assessment is dated today (the command line and the web app both use this)."""
        return datetime.now().date().isoformat()

    def forecast_settings(self) -> dict:
        """The policy's "forecasting" block as the forecast uses it. FORECAST_WEB_SEARCH=on/off in
        .env overrides web_search, so market figures can be checked online without editing policy.json."""
        policy = self.__config.policy
        settings = dict(policy.get("forecasting", {}))
        switch = str(os.getenv("FORECAST_WEB_SEARCH") or "").strip().lower()
        if switch in ("on", "true", "yes", "1"):
            settings["web_search"] = True
        elif switch in ("off", "false", "no", "0"):
            settings["web_search"] = False
        settings["net_worth_documents"] = policy.get("breach_documents", {}).get("NET_WORTH")
        return settings

    def ai_available(self) -> bool:
        """False when the AI caller has no API key: only saved AI replies can then be used."""
        if self.__ai_caller is None:
            return False
        return bool(getattr(self.__ai_caller, "available", lambda: True)())

    # ----- starting ------------------------------------------------------------------------

    def start(self, arguments: list[str]) -> int:
        """Run the command line app. Returns the exit code (0 = fine).

            (no arguments)          the menu
            --case FILE             assess one case file
            --all-samples           assess every sample case
            --web                   start the web app instead of the menu
        """
        self.__configure_logging()
        allowed = ("--web", "--case", "--all-samples")
        unknown = [argument for position, argument in enumerate(arguments)
                   if argument not in allowed and not (position > 0 and arguments[position - 1] == "--case")]
        if unknown:
            self.__ui.show_error(f"Unknown option {unknown[0]}. Allowed: --web, --case FILE, --all-samples "
                                 "(or nothing, for the menu).")
            return 1
        if not self.__settings_ok:
            self.__ui.show_error(App.SETTINGS_UNAVAILABLE)
            return 1
        if not self.__audit_key:
            self.__ui.show_error(App.AUDIT_KEY_MISSING)
            return 1
        problems = self.__config_reader.problems()
        if problems:
            for problem in problems:
                self.__ui.show_error(problem)
            return 1
        if "--web" in arguments:
            return self.start_web()
        if not self.ai_available():
            self.__ui.show_error("No OPENAI_API_KEY set: only saved AI replies can be used.")
        try:
            if "--all-samples" in arguments:
                paths = self.__case_files.list_samples()
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
        except KeyboardInterrupt:
            self.__ui.show_message("\nStopped.")
            return 130
        except Exception:
            logger.exception("Unexpected error in the command line app")
            self.__ui.show_unexpected_error()
            return 1

    def start_web(self, host: str = "", port: int = 0) -> int:
        """Start the web app. HOST and PORT in .env set where it listens (default 127.0.0.1:5000)."""
        from app.interface.web_app import WebApp    # imported here: WebApp itself imports App
        self.__configure_logging()
        if not self.__settings_ok:
            self.__ui.show_error(App.SETTINGS_UNAVAILABLE)
            return 1
        if not self.__audit_key:
            self.__ui.show_error(App.AUDIT_KEY_MISSING)
            return 1
        WebApp(self, self.__limiter).start(host or os.getenv("HOST") or "127.0.0.1", port or int(os.getenv("PORT") or 5000))
        return 0

    def run_menu(self) -> None:
        """Show the main menu until the officer chooses to leave."""
        self.begin_request(App.TERMINAL)
        try:
            self.__ui.show_message(f"{len(self.__assessments.load())} saved assessment(s) loaded.")
        except (OSError, ValueError) as error:
            logger.error("App.run_menu: the saved assessments cannot be read: %r", error)
            self.__read_failed("assessments", App.TERMINAL)
            self.__ui.show_error(App.ASSESSMENTS_UNAVAILABLE)
        while True:
            self.begin_request(App.TERMINAL)         # each pass of the menu is a new request
            choice = self.__ui.show_app_menu()
            if choice == "1":
                record = self.__client_form.create_new_client(save_fn=functools.partial(self.save_client, new_client=True),
                                                             upload_fn=self.upload_document,
                                                             is_taken_fn=self.client_ref_taken)
                if record is not None:
                    self.__maybe_assess(record)
            elif choice == "2":
                record = self.__new_client_from_documents()
                if record is not None:
                    self.__maybe_assess(record)
            elif choice == "3":
                self.__client_form.find_existing_client(
                    find_fn=self.find_client, save_fn=self.save_client,
                    download_fn=self.download_document, upload_fn=self.upload_document)
            elif choice == "4":
                ref = self.__ui.ask_client_ref()
                if ref is None:
                    continue
                try:
                    record = self.find_client(ref)
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
                    clients = self.__clients.load()
                except (OSError, ValueError) as error:
                    logger.error("App.run_menu: the client records cannot be read: %r", error)
                    self.__read_failed("client records", App.TERMINAL)
                    self.__ui.show_error(App.CLIENTS_UNAVAILABLE)
                    continue
                activity, note = None, ""
                if clients:                            # with no clients there is nothing to show activity for
                    try:
                        activity = self.last_activity()
                    except ValueError as error:        # the client list still shows, without the column
                        logger.error("App.run_menu: the last activity of the clients cannot be shown: %r", error)
                        note = f"{App.AUDIT_UNAVAILABLE} The last activity of each client cannot be shown."
                self.__report_view.show_client_list(clients, activity, note)
                self.__ui.read_answer("Press Enter to continue...")
            elif choice == "7":
                self.__ui.show_message("\n--- Synchronizing Local Data to Cloud Database ---")
                self.__ui.show_sync_result(self.sync_to_cloud())
            elif choice == "8":
                self.__client_history()
            elif choice == "0":
                self.__ui.show_message("\nGoodbye.")
                break

    # ----- assessing ---------------------------------------------------------------------------

    def __prepare_case(self, record: ClientRecord) -> dict | None:
        """The case to assess, built from a saved client record. The officer is only asked for
        what cannot be read from the record. None if no usable case could be made."""
        case, missing = self.read_case(record)
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

    def read_case(self, record: ClientRecord) -> tuple[dict | None, list[str]]:
        """(case, []) when the record can be read into a case, otherwise (None, what is missing).
        Nothing is asked and nothing is shown: the web app uses this."""
        return CaseReader(self.today()).forecasting_case(record.to_dict())

    def assess(self, case: dict, supporting_documents: list[dict] | None = None,
               on_step: Callable[[int, str], None] | None = None,
               on_failure: Callable[[str, str], bool] | None = None,
               show_failures: bool = True, actor: str = TERMINAL) -> dict | None:
        """Run one assessment. Returns the result, or None if a critical step failed (the audit log
        then gets an "assessment failed" line for actor).
        on_failure defaults to App's own rule (CRITICAL_STEPS). show_failures=False keeps
        failed steps off the terminal (the web app shows them in the report instead)."""
        self.__require_settings()
        self.__start(actor)
        if on_failure is None:
            on_failure = self.__handle_failure if show_failures else self.__handle_failure_quietly
        decide = on_failure
        stopped_at: list[str] = []

        def watch(step: str, error: str) -> bool:
            carry_on = decide(step, error)
            if not carry_on:
                stopped_at.append(step)
            return carry_on

        ref = str(case.get("client_ref") or "") if isinstance(case, dict) else ""
        try:
            result = self.__runner.run(case, supporting_documents, on_step, watch)
        except Exception:
            # The caller decides what the user sees; the audit log only learns that it failed (no error text).
            self.__record("assessment_failed", actor, ref, "failed", {"step": App.UNEXPECTED_ERROR_STEP})
            raise
        if result is None:
            self.__record("assessment_failed", actor, ref, "failed",
                          {"step": stopped_at[0] if stopped_at else "The assessment"})
        return result

    def assess_client_record(self, record: ClientRecord) -> Verdict | None:
        """The command line's assessment of a saved client: prepare, run, save, show.
        Returns the Verdict, or None if no assessment could be made."""
        self.__require_settings()
        case = self.__prepare_case(record)
        if case is None:
            return None
        self.__ui.show_message(f"\nAssessing {case['client_ref']}: documents, crime scan, forecast "
                               "and benchmark together.")
        result = self.assess(case, record.documents(), on_step=self.__show_step)
        if result is None:
            self.__ui.show_error("The assessment was stopped. Nothing was saved.")
            return None
        saved = self.save_assessment(result, record, on_step=self.__show_step)
        verdict = result["verdict"]
        self.__report_view.show_verdict_report(verdict, crime_result=result.get("crime_result"),
                                               typologies=result.get("typologies"))
        if saved:
            self.__ui.show_message("Assessment saved.")
            if self.client_outcome_failed():
                self.__ui.show_error(App.OUTCOME_NOT_UPDATED)
        else:
            self.__ui.show_error("Could not save the assessment.")
        return verdict

    def save_assessment(self, result: dict, record: ClientRecord | None = None,
                        on_step: Callable[[int, str], None] | None = None, actor: str = TERMINAL) -> str | None:
        """Save the assessment as ONE record, then its outcome on the client record when given.
        Returns the assessment id, or None if the assessment could not be saved (the client
        record is then left as it was). The audit log gets an "assessment run" line, or an
        "assessment failed" line when it was not saved. If saving raises, that line is written too
        and the error is raised again."""
        self.__start(actor)
        try:
            return self.__store_assessment(result, record, on_step, actor)
        except Exception:
            ref = ""
            try:
                ref = str(result["verdict"].client_ref)
            except Exception:
                pass                                    # the result itself was unusable: no client to name
            self.__record("assessment_failed", actor, ref, "failed", {"step": App.UNEXPECTED_ERROR_STEP})
            raise

    def __store_assessment(self, result: dict, record: ClientRecord | None,
                           on_step: Callable[[int, str], None] | None, actor: str) -> str | None:
        """The work of save_assessment."""
        if on_step is not None:
            on_step(len(AssessmentRunner.STEPS), AssessmentRunner.STEPS[-1])
        case = result["case"]
        verdict: Verdict = result["verdict"]
        details = verdict.details()             # the layout saved under "verdict"
        saved = self.__assessments.save({
            "assessment_id": verdict.assessment_id,
            "client_ref": verdict.client_ref,
            "kind": "onboarding",
            "assessed_at": verdict.assessed_at,
            "outcome": verdict.outcome,
            "case": copy.deepcopy(case),            # the client as they were when this was assessed
            "verdict": details,
            "report": verdict.report,
            "crime_scan": {"research": result["research"], "typologies": result["typology_response"],
                           "declaration": App.__crime_declaration_layout(result["crime_declaration"])},
            "crime_result": App.__crime_result_layout(result["crime_result"]),
            "benchmark": result["benchmark"],
            "document_evidence": result["evidence"],
            "forecast": result["forecast_assessment"],
            "assessment": result["forecast_assessment"],
        })
        if not saved:
            # The client record is not touched: its outcome must never point at an assessment
            # that was not saved.
            logger.error("App.save_assessment: the assessment for %s was not saved", verdict.client_ref)
            self.__record("assessment_failed", actor, verdict.client_ref, "failed",
                          {"step": AuditEvent.SAVE_STEP, "assessment_id": verdict.assessment_id})
            return None
        previous_outcome = record.review_status.outcome if record is not None else ""
        run_details = {"assessment_id": verdict.assessment_id, "outcome": verdict.outcome,
                       "previous_outcome": previous_outcome,
                       "not_run": App.__not_run_steps(verdict.report)}
        if record is not None:
            # The record keeps the case's date (assessed_on), not the time the verdict was made
            # (assessed_at), so ClientRecord.record_assessment is not used here.
            record.review_status.update(verdict.outcome, verdict.next_step, verdict.next_review_date,
                                        details["assessed_on"] or self.today(), case)
            run_details["record_saved"] = self.__save_record(record)
            if not run_details["record_saved"]:
                # The assessment itself was saved, so the audit line stays "ok"; record_saved says what is missing.
                self.__audit_note.outcome_failed = True
                logger.error("App.save_assessment: could not save the client record for %s", verdict.client_ref)
        self.__record("assessment_run", actor, verdict.client_ref, "ok", run_details, kept=True)
        return verdict.assessment_id

    @staticmethod
    def __not_run_steps(report: dict | None) -> list[str]:
        """The names of the steps a report lists under "Could not run" (plain step names, no error text)."""
        names: list[str] = []
        for section in (report or {}).get("sections", []):
            if section.get("title") == "Could not run":
                names += [str(item.get("text")) for item in section.get("items", []) if item.get("text")]
        return names

    @staticmethod
    def __crime_declaration_layout(declaration: Declaration | None) -> dict | None:
        """The crime scan's reading of the declaration as it is saved: its rows {"sources": [...]}."""
        return None if declaration is None else declaration.to_scan_dict()

    @staticmethod
    def __crime_result_layout(crime_result: dict | None) -> dict | None:
        """The crime scan's result as it is saved: each MatchResult in its to_dict() layout."""
        if crime_result is None:
            return None
        return {**crime_result, "match_results": [match.to_dict() for match in crime_result["match_results"]]}

    def run_case_file(self, path: str) -> bool:
        """Assess a case file (the same assessment as the menu). False if it could not be assessed."""
        self.__require_settings()
        case = self.__case_files.load(path)
        if case is not None and not self.__case_files.is_forecasting_case(case):
            self.__ui.show(f"\n{os.path.basename(path)}: not in the forecasting format "
                           "(it's a client record), skipped. Use the menu to assess it.")
            return True
        problems = self.__case_builder.validate_case(case)
        if problems:
            self.__case_builder.show_case_problems(path, problems)
            return False
        self.__ui.show_message(f"\nAssessing {case['client_ref']} ({os.path.basename(path)}).")
        result = self.assess(case, on_step=self.__show_step)
        if result is None:
            self.__ui.show_error("The assessment was stopped. Nothing was saved.")
            return False
        if not self.save_assessment(result, on_step=self.__show_step):
            self.__ui.show_error("Could not save the assessment.")
        self.__report_view.show_verdict_report(result["verdict"], ask_for_evidence=False,
                                               crime_result=result.get("crime_result"),
                                               typologies=result.get("typologies"))
        return result["forecast"] is not None

    # ----- clients and records ---------------------------------------------------------------

    def find_client(self, client_ref: str) -> ClientRecord | None:
        """The saved client with this reference, or None if no client has it.
        Raises ValueError, with a message that is safe to show, if the client database cannot
        be read or the saved record is not valid."""
        try:
            saved = self.__clients.find(client_ref)
        except (OSError, ValueError) as error:
            logger.error("App.find_client: the client records cannot be read: %r", error)
            self.__read_failed("client records")
            raise ValueError(App.CLIENTS_UNAVAILABLE) from error
        if saved is None:
            return None
        try:
            return ClientRecord.from_dict(saved)
        except (ValueError, TypeError, AttributeError) as error:
            logger.error("App.find_client: the saved record %s cannot be read: %r", client_ref, error)
            raise ValueError(f"Client {client_ref} could not be loaded because the saved record is "
                             f"not valid: {ClientRecord.why_unreadable(error)}.") from error

    def save_client(self, record: ClientRecord, actor: str = TERMINAL, new_client: bool = False) -> bool:
        """Save the client (replacing the saved record with the same reference). False if not saved.
        The saved record is read first, so the audit log can say "created" or "edited" and which fields
        changed; if it cannot be read nothing is saved. Saving a record that changed nothing writes
        no audit line. new_client says this is a new client: it is only used when the saved records cannot be
        read, to record a failed creation as "created" and not "edited" (otherwise the saved record tells)."""
        self.__start(actor)
        client_ref = record.client_ref
        try:
            old = self.__clients.find(client_ref)
        except (OSError, ValueError) as error:
            logger.error("App.save_client: not saved, the saved client records cannot be read: %r", error)
            if new_client:
                self.__record("client_created", actor, client_ref, "failed")
            else:
                self.__record("client_edited", actor, client_ref, "failed", {"changes": []})
            return False
        new = record.to_dict()
        changes = RecordDiff(old, new).changes()
        saved = self.__clients.save(new)
        if not saved:
            logger.error("App.save_client: could not save the client record %s", client_ref)
        if old is None:
            self.__record("client_created", actor, client_ref, "ok" if saved else "failed", kept=saved)
        elif changes or not saved:
            self.__record("client_edited", actor, client_ref, "ok" if saved else "failed", {"changes": changes},
                          kept=saved)
        return saved

    def __save_record(self, record: ClientRecord) -> bool:
        """Save the client record with no audit line: used when an assessment writes its outcome
        onto the record, which is not an edit by the officer."""
        saved = self.__clients.save(record.to_dict())
        if not saved:
            logger.error("App.__save_record: could not save the client record %s", record.client_ref)
        return saved

    def __new_client_from_documents(self) -> ClientRecord | None:
        """Read a folder of documents, pre-fill the client, ask for what is missing, show a
        summary to check, then save. Returns the saved record (to assess) or None."""
        # 1. Which folder
        while True:
            folder = self.__client_form.ask_document_folder()
            if folder is None:
                return None
            paths = self.__documents.list_folder(folder)
            if paths is None:
                self.__ui.show_error(f"Folder not found: {folder}")
            elif not paths:
                self.__ui.show_error("No PDF, Word, Excel, text or image files in that folder.")
            else:
                break
        self.__ui.show_documents_found(paths)

        # 2. Read the documents and let the AI pull out the details
        self.__ui.show_message(f"\nReading {len(paths)} document(s) with AI... this can take up to a minute.")
        extracted, warnings = self.read_documents([self.__documents.read_for_extraction(path) for path in paths])
        if extracted is None:
            self.__ui.show_ai_unavailable("Document reading")
            if not self.__ui.ask_yes_no("Type the details in yourself?"):
                return None
            extracted = {}

        # 3. Build the record and ask for anything missing
        builder = self.record_builder()
        try:
            client_ref = self.new_client_ref()
        except ValueError as error:
            self.__ui.show_error(str(error))
            return None
        try:
            document_record, _, dropped = builder.build(extracted, client_ref)
        except ValueError as error:
            logger.error("App.__new_client_from_documents: the AI's reading is not a possible record: %r", error)
            self.__ui.show_error(f"The details read from the documents cannot be used because {error}.")
            if not self.__ui.ask_yes_no("Type the details in yourself?"):
                return None
            extracted = {}
            document_record, _, dropped = builder.build(extracted, client_ref)
        if dropped:
            messages = [entry["message"] for entry in dropped]
            logger.warning("App.__new_client_from_documents: left out of the AI's reading: %s", " | ".join(messages))
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
                record = builder.finish(self.__client_form.edit_existing_client(record, self.upload_document))
                for field in builder.missing_fields(record):
                    record = self.__fill_field(builder, record, field)
                continue
            break

        # 5. Keep the documents with the client, then save
        for path in paths:
            stored = self.upload_document(path)
            if stored is None:
                self.__ui.show_error(f"Could not keep a copy of {os.path.basename(path)}.")
            else:
                record.add_document({"file_name": os.path.basename(path), "file_path": stored})
        if not self.save_client(record, new_client=True):
            self.__ui.show_error("The client could not be saved.")
            return None
        self.__ui.show_message(f"\nClient saved. Reference: {record.client_ref} "
                               f"({len(record.documents())} document(s) attached).")
        return record if self.__client_form.ask_after_save(record) else None

    def read_documents(self, documents: list[dict], actor: str = TERMINAL,
                       client_ref: str = "") -> tuple[dict | None, list[str]]:
        """Ask the AI to read documents the DocumentStore has opened. Returns (details, warnings).
        Reading at least one document is written to the audit log (how many, and how many details were found);
        client_ref, when the documents are for a saved client, ties that line to the client's History."""
        self.__start(actor)
        service = self.__document_ai
        extracted = service.run({"documents": documents})
        warnings = service.warnings()
        for warning in warnings:
            logger.info(warning)
        if documents:
            self.__record("autofill_used", actor, client_ref, "ok" if extracted is not None else "failed",
                          {"documents": len(documents), "fields": App.__count_fields(extracted)})
        return extracted, warnings

    @staticmethod
    def __count_fields(value: object, key: str = "") -> int:
        """How many details the AI found in a reading: every value that is not empty (notes do not count)."""
        if key == "notes" or value is None or value == "" or value == [] or value == {}:
            return 0
        if isinstance(value, dict):
            return sum(App.__count_fields(item, name) for name, item in value.items())
        if isinstance(value, list):
            return sum(App.__count_fields(item) for item in value)
        return 1

    def record_builder(self, date: str = "") -> DocumentRecordBuilder:
        """A DocumentRecordBuilder for one record, dated today unless another date is given."""
        return DocumentRecordBuilder(self.__config, date or self.today())

    def new_client_ref(self) -> str:
        """A new client reference that no saved client has. Raises ValueError, with a message that
        is safe to show, if the saved clients cannot be read or no free reference was found."""
        return self.__client_form.generate_client_id(self.client_ref_taken)

    def client_ref_taken(self, client_ref: str) -> bool:
        """True if a saved client has this reference. Raises ValueError, with a message that is
        safe to show, if the client database cannot be read (that is never "not taken")."""
        try:
            return self.__clients.find(client_ref) is not None
        except (OSError, ValueError) as error:
            logger.error("App.client_ref_taken: the client records cannot be read: %r", error)
            self.__read_failed("client records")
            raise ValueError(App.CLIENTS_UNAVAILABLE) from error

    def validate_case(self, case: object) -> list[str]:
        """Everything wrong with a case. [] means it can be assessed."""
        return self.__case_builder.validate_case(case)

    def read_amount(self, text: object) -> float | None:
        """'1,650,000', 'S$1.65m', '410k' -> a number; None if it cannot be read."""
        return CaseReader.read_amount(text)

    def list_assessments(self) -> None:
        """List saved assessments (filtered by outcome) and optionally open one."""
        outcomes = ["(all)", *Verdict.OUTCOMES, "(include archived)"]
        choice = self.__ui.ask_choice("Show which outcome?", outcomes, allow_back=True)
        if choice is None:
            return          # 0 = back to the main menu
        picked = outcomes[choice]
        with_archived = picked == "(include archived)"      # every outcome, archived ones too
        try:
            matches = self.__assessments.query("" if picked == "(all)" or with_archived else picked,
                                               include_archived=with_archived)
        except (OSError, ValueError) as error:
            logger.error("App.list_assessments: the saved assessments cannot be read: %r", error)
            self.__read_failed("assessments", App.TERMINAL)
            self.__ui.show_error(App.ASSESSMENTS_UNAVAILABLE)
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
        labels = [ReportView.format_assessment_row(record, state).rstrip() for record, state in zip(records, states)]
        return self.__ui.ask_choice(question, labels, allow_back=True, back_label=back_label)

    def __open_assessment(self, chosen: dict) -> None:
        """Show one saved assessment in full: the combined report, or a forecast-only one saved before it."""
        if chosen.get("report"):                                         # the combined assessment
            verdict = self.__saved_verdict(chosen)
            if verdict is None:
                self.__ui.show_error("This saved assessment could not be read, so its report cannot be "
                                     "shown. The other saved assessments are not affected.")
            else:
                self.__report_view.show_verdict_report(verdict)
        else:
            self.__report_view.show_onboarding(chosen["assessment"])     # saved before the combined verdict

    def __change_archive(self, records: list[dict]) -> None:
        """Ask which of these assessments to archive or restore, ask for the reason (archive only) and do it.
        Every result is told to the officer in the words the web app uses; a result that did nothing is never
        shown as done."""
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
            self.__ui.show_error("This assessment's archive record is damaged, so it cannot be changed.")
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
            result = (self.archive_assessment(assessment_id, reason, App.TERMINAL) if archive
                      else self.restore_assessment(assessment_id, App.TERMINAL))
        except ValueError as error:
            logger.error("App.__change_archive: the saved assessments cannot be read: %r", error)
            self.__ui.show_error(App.ASSESSMENTS_UNAVAILABLE)
            return
        word = "archived" if archive else "restored"
        done, nothing_to_do = (("Assessment archived. It is hidden from the lists, not deleted.",
                                "This assessment is already archived.") if archive else
                               ("Assessment restored.", "This assessment is not archived."))
        if result == App.ARCHIVE_CHANGED:
            self.__ui.show_message(done)
        elif result == App.ARCHIVE_NO_CHANGE:
            self.__ui.show_message(nothing_to_do)
        elif result == App.ARCHIVE_UNREADABLE:
            self.__ui.show_error("This assessment's archive record is damaged, so it cannot be changed.")
        elif result == App.ARCHIVE_NOT_SAVED:
            self.__ui.show_error(f"The assessment was not {word} because saving failed. Please try again later.")
        elif result == App.ARCHIVE_BAD_REASON:
            self.__ui.show_error(f"Nothing was archived. {App.archive_reason_problem(reason)}")
        elif result == App.ARCHIVE_NOT_FOUND:
            self.__ui.show_error("That assessment could not be found, so nothing was changed.")
        else:
            self.__ui.show_error(App.ASSESSMENTS_UNAVAILABLE)

    def __client_history(self) -> None:
        """Menu 8: one client's assessments (archive marks), archive/restore, open one in full and the audit
        trail with its Show / When filter."""
        ref = self.__ui.ask_client_ref()
        if ref is None:
            return
        try:
            record = self.find_client(ref)
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
            assessments = self.client_assessments(client_ref, include_archived=True)
        except (OSError, ValueError) as error:
            logger.error("App.__show_client_assessments: the saved assessments cannot be read: %r", error)
            self.__read_failed("assessments", App.TERMINAL)
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
        when = whens[self.__ui.ask_choice("Which period?", [TrailFilter.WHEN_LABELS[w] for w in whens])]
        while True:
            first = last = ""
            if when == "custom":
                first = self.__ui.ask_optional_text("From date (YYYY-MM-DD, Enter for no start)")
                last = self.__ui.ask_optional_text("To date (YYYY-MM-DD, Enter for no end)")
            try:
                trail_filter = TrailFilter(show, when, first, last)
            except ValueError as error:
                self.__ui.show_error(str(error))
                continue
            if when != "custom":
                return trail_filter
            if not first or not last:
                self.__ui.show_error("Pick both a start and an end date.")
            elif AuditFilter.parse_day(last) > AuditFilter.singapore_day(datetime.now(timezone.utc)):
                self.__ui.show_error("The dates cannot be in the future.")
            else:
                return trail_filter

    def __show_trail(self, client_ref: str, trail_filter: TrailFilter) -> None:
        """Show the client's audit trail, newest first, through the filter. An audit log that cannot be read
        is said so; it is never shown as "no history"."""
        try:
            events, unreadable = self.audit_trail(client_ref)
        except ValueError as error:
            logger.error("App.__show_trail: the audit log cannot be read: %r", error)
            self.__ui.show_error(App.AUDIT_UNAVAILABLE)
            return
        now = datetime.now(timezone.utc)
        shown = [event for event in events if trail_filter.matches(event, now)]
        dates = f" ({trail_filter.date_from or '...'} to {trail_filter.date_to or '...'})" \
            if trail_filter.when == "custom" else ""
        self.__ui.show_message(f"\nShowing: {TrailFilter.SHOW_LABELS[trail_filter.show]}, "
                               f"{TrailFilter.WHEN_LABELS[trail_filter.when]}{dates}")
        self.__report_view.show_client_history(shown, len(events), unreadable)

    def client_assessments(self, client_ref: str, include_archived: bool = False) -> list[dict]:
        """Every saved assessment of one client, newest first; archived ones only if include_archived.
        Nothing is hidden or caught here:
        whatever the AssessmentRepository reports (a list, or an OSError or ValueError it raises when
        the saved assessments cannot be read) comes straight back. The caller shows ASSESSMENTS_UNAVAILABLE."""
        return self.__assessments.for_client(client_ref, include_archived)

    def find_assessment(self, assessment_id: str) -> dict | None:
        """The saved assessment with this id, or None if there is none. Raises OSError or ValueError
        when the saved assessments cannot be read; the caller shows ASSESSMENTS_UNAVAILABLE."""
        return self.__assessments.find(assessment_id)

    def upload_document(self, file_path: str, actor: str = TERMINAL, client_ref: str = "") -> str | None:
        """Keep a copy of a supporting document. Returns its id (to save in the client's
        document list), or None if it could not be copied. client_ref, when known, ties the audit line to the client."""
        self.__start(actor)
        file_id = self.__documents.upload(file_path)
        self.__record("document_uploaded", actor, client_ref, "ok" if file_id else "failed",
                      {"file_id": file_id or ""}, kept=bool(file_id))
        return file_id

    def download_document(self, file_id: str, output_path: str, actor: str = TERMINAL,
                          client_ref: str = "") -> bool:
        """Copy a kept document out to output_path. False if it could not be copied."""
        self.__start(actor)
        copied = self.__documents.download(file_id, output_path)
        self.__record("document_downloaded", actor, client_ref, "ok" if copied else "failed",
                      {"file_id": file_id if isinstance(file_id, str) else ""})
        return copied

    def sync_to_cloud(self, actor: str = TERMINAL) -> dict:
        """Back up clients and assessments to the cloud database.
        Returns {"cases_synced", "assessments_synced", "skipped", "errors"}. The audit log gets the counts
        (never the error text)."""
        self.__start(actor)
        stats = self.__sync_all()
        self.__record("cloud_sync", actor, "", "failed" if stats["errors"] else "ok",
                      {"synced": stats["cases_synced"] + stats["assessments_synced"],
                       "skipped": stats["skipped"], "errors": len(stats["errors"])})
        return stats

    def __sync_all(self) -> dict:
        """Run every CloudSync and add up what they report."""
        stats = {"cases_synced": 0, "assessments_synced": 0, "skipped": 0, "errors": []}
        for name, sync in zip(("cases_synced", "assessments_synced"), self.__syncs):
            result = sync.sync()
            stats[name] = result["synced"]
            stats["skipped"] += result["skipped"]
            stats["errors"] += [error for error in result["errors"] if error not in stats["errors"]]
        return stats

    # ----- what the web app asks for, so it never works a manager's object itself --------------

    def owns_document(self, file_id: str) -> bool:
        """True only for a document reference this app made (the DocumentStore decides)."""
        return self.__documents.owns(file_id)

    def read_document_for_extraction(self, path: str, name: str) -> dict:
        """One file read so the AI can pull client details out of it: {"file_name", "kind", ...}.
        A file that cannot be read comes back with kind "error" and a message that is safe to show."""
        return self.__documents.read_for_extraction(path, name)

    def all_clients(self) -> list[dict]:
        """Every saved client; [] only when there are none yet. Raises ValueError(CLIENTS_UNAVAILABLE)
        if the client database cannot be read (that is never "no clients")."""
        try:
            return self.__clients.load()
        except (OSError, ValueError) as error:
            logger.error("App.all_clients: the client records cannot be read: %r", error)
            self.__read_failed("client records")
            raise ValueError(App.CLIENTS_UNAVAILABLE) from error

    def all_assessments(self, include_archived: bool = False) -> list[dict]:
        """Every saved assessment (archived ones only if include_archived); [] only when there are
        none yet. Raises ValueError(ASSESSMENTS_UNAVAILABLE) if the saved assessments cannot be read."""
        try:
            return self.__assessments.query("", include_archived)
        except (OSError, ValueError) as error:
            logger.error("App.all_assessments: the saved assessments cannot be read: %r", error)
            self.__read_failed("assessments")
            raise ValueError(App.ASSESSMENTS_UNAVAILABLE) from error

    def archive_assessment(self, assessment_id: str, reason: str = "", actor: str = TERMINAL) -> str:
        """Hide one assessment from the lists (nothing is deleted), with an optional reason. Returns
        ARCHIVE_CHANGED, ARCHIVE_NOT_FOUND, ARCHIVE_NO_CHANGE (already archived), ARCHIVE_UNREADABLE (its
        archive log is damaged), ARCHIVE_NOT_SAVED, or ARCHIVE_BAD_REASON (nothing archived; reason_problem
        says why). actor is who did it; it is written on the archive line. Raises ValueError(ASSESSMENTS_UNAVAILABLE)
        if the saved assessments cannot be read. The client record is not touched. A change (or a failed
        save) is written to the audit log."""
        self.__start(actor)
        if AssessmentRepository.reason_problem(reason):
            return App.ARCHIVE_BAD_REASON          # checked first, so it is never taken for a read error
        try:
            result = self.__assessments.archive(assessment_id, reason, actor)
        except (OSError, ValueError) as error:
            logger.error("App.archive_assessment: the saved assessments cannot be read: %r", error)
            self.__read_failed("assessments", actor)
            raise ValueError(App.ASSESSMENTS_UNAVAILABLE) from error
        self.__record_archive("assessment_archived", actor, assessment_id, result, reason.strip())
        return result

    def restore_assessment(self, assessment_id: str, actor: str = TERMINAL) -> str:
        """Bring an archived assessment back into the lists. Same results and error as archive_assessment
        (ARCHIVE_NO_CHANGE means it was not archived)."""
        self.__start(actor)
        try:
            result = self.__assessments.restore(assessment_id, actor)
        except (OSError, ValueError) as error:
            logger.error("App.restore_assessment: the saved assessments cannot be read: %r", error)
            self.__read_failed("assessments", actor)
            raise ValueError(App.ASSESSMENTS_UNAVAILABLE) from error
        self.__record_archive("assessment_restored", actor, assessment_id, result, "")
        return result

    def __record_archive(self, action: str, actor: str, assessment_id: str, result: str, reason: str) -> None:
        """Write the audit line for an archive or restore: only when it changed the assessment
        (CHANGED) or the save failed (NOT_SAVED). Nothing was done in any other case."""
        if result not in (AssessmentRepository.CHANGED, AssessmentRepository.NOT_SAVED):
            return
        try:
            saved = self.__assessments.find(assessment_id) or {}
        except (OSError, ValueError) as error:
            logger.error("App.__record_archive: the saved assessment cannot be read for the audit line: %r", error)
            self.__read_failed("assessments", actor)
            saved = {}
        details = {"assessment_id": str(saved.get("assessment_id") or assessment_id).strip()}
        outcome = saved.get("outcome")
        if isinstance(outcome, str) and outcome:
            details["outcome"] = outcome
        if reason:
            details["reason"] = reason
        self.__record(action, actor, str(saved.get("client_ref") or ""),
                      "ok" if result == AssessmentRepository.CHANGED else "failed", details,
                      kept=result == AssessmentRepository.CHANGED)

    @staticmethod
    def archive_reason_problem(reason: object) -> str:
        """What is wrong with an archive reason, in plain words; "" if it is fine."""
        return AssessmentRepository.reason_problem(reason)

    @staticmethod
    def archive_state(saved: dict) -> str:
        """ARCHIVE_ACTIVE, ARCHIVE_ARCHIVED or ARCHIVE_UNREADABLE for one saved assessment."""
        return AssessmentRepository.archive_state(saved)

    def record_from_reading(self, extracted: dict, today: str = "") -> tuple[ClientRecord, list[dict]]:
        """The client record made from the AI's reading of documents, and one entry for each field
        left out because no client record can have that value: {"path", "message", "optional_field"}.
        Raises ValueError, saying what is wrong, if today is not a YYYY-MM-DD date or if the
        reading as a whole cannot be a record."""
        record, _, dropped = self.record_builder(today).build(extracted, "")
        return record, dropped

    def reading_problems(self, record: ClientRecord, today: str = "") -> list[str]:
        """Things worth a second look in a record filled from documents. [] = nothing spotted."""
        return self.record_builder(today).check(record)

    # ----- who is using the app, and the audit log ----------------------------------------------

    def accounts(self) -> list[Account]:
        """Every account that can sign in."""
        return list(self.__config.accounts)

    def account(self, email: str) -> Account | None:
        """The account with this email (upper and lower case are the same), or None."""
        return self.__config.account(email)

    def sign_in(self, name: str, password: str, portal: str) -> tuple[Account | None, str]:
        """Sign in by name and password at a portal (OFFICER_PORTAL or ADMIN_PORTAL). Returns (the account, "")
        and writes a "signed in" line, or (None, the plain message to show) and, if something was typed,
        a "failed sign-in" line (details: the portal only, never the password; the actor is the account
        name if the name matched an account, else UNKNOWN). The name is matched ignoring case and extra
        spaces. An admin account at the officer portal, or an officer at the admin one, is refused with a message
        that says where to sign in, but only after the password was right. Raises ValueError for an unknown portal."""
        if portal not in (App.OFFICER_PORTAL, App.ADMIN_PORTAL):
            raise ValueError(f"The portal must be {App.OFFICER_PORTAL} or {App.ADMIN_PORTAL}.")
        name = " ".join(name.split()) if isinstance(name, str) else ""
        password = password if isinstance(password, str) else ""
        if not name or not password:
            return None, App.SIGN_IN_EMPTY
        match = None
        if len(name) <= App.MAX_SIGN_IN_TEXT and len(password) <= App.MAX_SIGN_IN_TEXT:
            match = next((a for a in self.__config.accounts
                          if " ".join(a.name.split()).casefold() == name.casefold()), None)
        actor = match.name if match is not None else App.UNKNOWN
        if match is None and self.__config.accounts:
            # check a password anyway, so a wrong name takes as long as a wrong password and the reply
            # time does not show which names have accounts (the result is not used)
            self.__config.accounts[0].check_password(password)
        self.__start(actor)
        if match is None or not match.check_password(password):
            self.__record("sign_in_failed", actor, "", "failed", {"portal": portal})
            return None, App.SIGN_IN_WRONG
        if portal == App.ADMIN_PORTAL and not match.is_admin():
            self.__record("sign_in_failed", actor, "", "failed", {"portal": portal})
            return None, App.SIGN_IN_OFFICER_AT_ADMIN
        if portal == App.OFFICER_PORTAL and match.is_admin():
            self.__record("sign_in_failed", actor, "", "failed", {"portal": portal})
            return None, App.SIGN_IN_ADMIN_AT_OFFICER
        self.__record("signed_in", match.name)
        return match, ""

    def sign_out(self, account: Account) -> None:
        """Sign out: the audit log gets a "signed out" line. Raises ValueError if this is not a configured account."""
        if not isinstance(account, Account):
            raise ValueError("Only an account can sign out.")
        self.__start(account.name)
        self.__record("signed_out", account.name)

    def refused(self, actor: str, what: str, now: float | None = None) -> None:
        """Write that actor was refused: what says what they tried ("opening the audit log"). If the same
        actor was refused the same thing less than REFUSAL_REPEAT_SECONDS ago, nothing more is written
        (a reloaded page would otherwise fill the log). now is a clock reading in seconds (time.monotonic()
        if not given). Raises ValueError if actor is not a known actor or what is not printable text of
        1 to MAX_REFUSED_TEXT characters."""
        self.__start(actor)
        text = what.strip() if isinstance(what, str) else ""
        if not text or not text.isprintable() or len(text) > App.MAX_REFUSED_TEXT:
            raise ValueError(f"What was refused must be printable text of 1 to {App.MAX_REFUSED_TEXT} characters.")
        now = time.monotonic() if now is None else now
        key = (actor, text)
        with self.__refusal_lock:
            last = self.__recent_refusals.get(key)
            if last is not None and 0 <= now - last < App.REFUSAL_REPEAT_SECONDS:
                return
        if self.__record("access_refused", actor, "", "ok", {"what": text}):    # a line that failed is tried again
            with self.__refusal_lock:
                self.__recent_refusals = {k: t for k, t in self.__recent_refusals.items()
                                          if 0 <= now - t < App.REFUSAL_REPEAT_SECONDS}
                self.__recent_refusals[key] = now

    def audit_log(self, audit_filter: AuditFilter, now: datetime | None = None) -> AuditPage:
        """One page of the log in the filter's order, with the counts the page needs, all from one read:
        how many events match, how many rows cannot be read, how many readable events the whole log holds
        (so a page can tell an empty log from a filter that matches nothing), how many different people and
        failures there are among the matches, and how many flags are still to handle (open_flags, whatever
        the filter; flagged says which events on the page are behind one). "Flagged only" keeps the events behind a flag that is not resolved. An empty log gives
        an empty page. If the flag rules fail the events are still returned, with open_flags None, nothing
        flagged and flags_ok False (the log does not depend on the rules); only "flagged only" cannot be
        answered then. flags_skipped counts flags that could not be built. Raises ValueError(AUDIT_UNAVAILABLE)
        if the log cannot be read, ValueError(FLAGS_UNAVAILABLE) if "flagged only" is asked and the flags cannot
        be worked out, and ValueError if audit_filter is not an AuditFilter or now has no timezone."""
        if not isinstance(audit_filter, AuditFilter):
            raise ValueError("The audit log needs an AuditFilter.")
        now = App.__checked_now(now)
        readable, unreadable, broken_at = self.__read_log("audit_log", False)
        flags_ok, skipped = True, 0
        try:
            flags, tickets, skipped = self.__work_out_flags("audit_log", readable, broken_at, now)
        except ValueError:                          # already logged; the events do not depend on the rules
            if audit_filter.flagged_only:
                raise
            flags, tickets, flags_ok = [], {}, False
        unresolved = [flag for flag in flags if tickets[flag.flag_id].status != "resolved"]
        flagged = {sequence for flag in unresolved for sequence in flag.sequences}
        events = [event for event in readable if audit_filter.matches(event, now, flagged)]
        if audit_filter.sort == "desc":
            events.reverse()                       # the file is oldest first
        shown = audit_filter.page_of(events)
        return AuditPage(shown, len(events), unreadable, len(readable),
                         len({event.actor.casefold() for event in events
                              if event.actor not in (AuditEvent.TERMINAL, AuditEvent.UNKNOWN)}),
                         sum(1 for event in events if event.result == "failed"),
                         len(unresolved) if flags_ok else None,
                         {event.sequence for event in shown if event.sequence in flagged}, flags_ok, skipped)

    def audit_overview(self, preset: str = OverviewPage.DEFAULT_PRESET, tab: str = OverviewPage.DEFAULT_TAB,
                       page: int = 1, now: datetime | None = None) -> OverviewPage:
        """Everything the admin Overview shows, from one read of the log: the numbers for the range (preset is
        "today", "7", "30" or "90" days back from today, Singapore days), the chain check, the failures per day,
        the flags by type and one page (6) of the flags table for the tab ("handle", "open", "review",
        "followup", "resolved" or "all"). In the table the flags that are not resolved come first, by priority
        then newest; the resolved ones follow, newest first. A page past the end gives the last page.
        Raises ValueError for a preset, tab or page that is not allowed, ValueError(AUDIT_UNAVAILABLE) if the
        log cannot be read (never an empty page), ValueError(AUDIT_KEY_MISSING) if the log has entries and no
        audit key is set (the chain cannot be checked), and ValueError(FLAGS_UNAVAILABLE) if the flags cannot
        be worked out."""
        if preset not in OverviewPage.PRESETS:
            raise ValueError(f"The range must be one of {', '.join(OverviewPage.PRESETS)} (got {preset!r}).")
        if tab not in OverviewPage.TABS:
            raise ValueError(f"The tab must be one of {', '.join(OverviewPage.TABS)} (got {tab!r}).")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError(f"The page must be a whole number, 1 or more (got {page!r}).")
        now = App.__checked_now(now)
        readable, unreadable, broken_at = self.__read_log("audit_overview", True)
        flags, tickets, skipped = self.__work_out_flags("audit_overview", readable, broken_at, now)
        today = AuditFilter.singapore_day(now)
        day_to = today
        day_from = today - timedelta(days=1 if preset == "today" else int(preset)) + timedelta(days=1)
        stats = AuditStats(readable, flags, tickets, day_from, day_to, now)
        ordered = App.__table_order([tickets[flag.flag_id] for flag in flags])
        counts = {"handle": stats.to_handle, "open": 0, "review": 0, "followup": 0, "resolved": 0,
                  "all": len(ordered)}
        for ticket in ordered:
            counts[ticket.status] += 1
        shown = ordered if tab == "all" else [t for t in ordered if (t.status != "resolved" if tab == "handle"
                                                                      else t.status == tab)]
        page_count = max(1, -(-len(shown) // OverviewPage.PAGE_SIZE))
        page = min(page, page_count)
        start = (page - 1) * OverviewPage.PAGE_SIZE
        on_page = shown[start:start + OverviewPage.PAGE_SIZE]
        evidence = {ticket.flag.flag_id: [event for event in readable if event.sequence in ticket.flag.sequences]
                    for ticket in on_page}
        return OverviewPage(
            preset, day_from, day_to, stats.to_handle, stats.not_started, stats.in_progress, stats.actions,
            stats.change_percent(stats.actions, stats.actions_before), stats.failures,
            stats.change_percent(stats.failures, stats.failures_before), broken_at,
            [(day.isoformat(), kinds) for day, kinds in stats.failures_by_day()], stats.flags_by_type(),
            stats.severity_counts(), tab, counts, on_page, page, page_count, unreadable, stats.type_severity(),
            len(readable) + unreadable, evidence, skipped, stats.has_previous,
            stats.actions - stats.actions_before, stats.failures - stats.failures_before)

    def flag(self, flag_id: str, now: datetime | None = None) -> FlagTicket | None:
        """The ticket (the flag, its status and its history) for a flag id, or None if the rules find no
        flag with that id now. Raises ValueError(AUDIT_UNAVAILABLE) if the log cannot be read (never None),
        ValueError(FLAGS_UNAVAILABLE) if the flags cannot be worked out, and ValueError if flag_id is not text."""
        if not isinstance(flag_id, str):
            raise ValueError("The flag id must be text.")
        _, _, _, _, tickets = self.__flag_view("flag", App.__checked_now(now), False)
        return tickets.get(flag_id.strip())

    def flag_evidence(self, flag_id: str, now: datetime | None = None
                      ) -> tuple[FlagTicket | None, list[AuditEvent], int]:
        """What the flag page needs, from one read of the log: (the ticket, the log entries behind the flag in
        entry order, how many entries the whole log holds). Entries that cannot be read are left out of the
        second part but counted in the third. (None, [], 0) when the rules find no flag with that id now.
        Raises ValueError(AUDIT_UNAVAILABLE) if the log cannot be read (never an empty answer),
        ValueError(FLAGS_UNAVAILABLE) if the flags cannot be worked out, and ValueError if flag_id is not text."""
        if not isinstance(flag_id, str):
            raise ValueError("The flag id must be text.")
        events, unreadable, _, _, tickets = self.__flag_view("flag_evidence", App.__checked_now(now), False)
        ticket = tickets.get(flag_id.strip())
        if ticket is None:
            return None, [], 0
        behind = set(ticket.flag.sequences)
        return ticket, [event for event in events if event.sequence in behind], len(events) + unreadable

    def update_flag(self, flag_id: str, actor: str, status: str, note: str, waiting_on: str = "",
                    outcome: str = "", now: datetime | None = None) -> tuple[FlagTicket | None, list[str], int]:
        """An admin moves a flag to a status (or adds a note: the same status) and writes one "flag_updated"
        line in the audit log. Returns (the ticket as it is now, the problems, the new entry's number):
          saved           (ticket, [], N)  N is the entry's number, for "Saved in the audit log as entry #N"
                          (0 only if the line was written but could not be found again to read its number)
          not valid       (ticket, [what is wrong], 0)  nothing is written; the messages are FlagTicket's
          flag is gone    (None, [FLAG_GONE], 0)
          not written     (ticket, [FLAG_NOT_SAVED], 0)  the update was NOT saved; audit_write_failed() is True
        Raises ValueError if actor is not an admin account, if status, note, waiting_on, outcome or flag_id is
        not text, ValueError(AUDIT_KEY_MISSING) if no audit key is set, ValueError(AUDIT_UNAVAILABLE) if the
        log cannot be read (the update is then not saved either), and ValueError(FLAGS_UNAVAILABLE)."""
        self.__start(actor)
        if not any(account.name == actor and account.is_admin() for account in self.__config.accounts):
            raise ValueError(App.FLAG_ADMIN_ONLY)
        for name, value in (("flag id", flag_id), ("status", status), ("note", note), ("waiting on", waiting_on),
                            ("outcome", outcome)):
            if not isinstance(value, str):
                raise ValueError(f"The {name} must be text.")
        if not self.__audit_key:
            raise ValueError(App.AUDIT_KEY_MISSING)
        now = App.__checked_now(now)
        ticket = self.__flag_view("update_flag", now, False)[4].get(flag_id.strip())
        if ticket is None:
            return None, [App.FLAG_GONE], 0
        problems = ticket.check_update(status, note, waiting_on, outcome)
        if problems:
            return ticket, problems, 0
        details = ticket.update_details(actor, status, note, waiting_on, outcome)
        if not self.__record("flag_updated", actor, ticket.flag.client_ref, "ok", details):
            return ticket, [App.FLAG_NOT_SAVED], 0
        event_id = getattr(self.__audit_note, "event_id", "")
        try:
            events, _, _, _, tickets = self.__flag_view("update_flag", now, False)
        except ValueError:
            return ticket, [], 0                     # saved, but it cannot be read back; already logged
        sequence = next((event.sequence for event in events if event.event_id == event_id), 0)
        return tickets.get(ticket.flag.flag_id, ticket), [], sequence

    def client_flags(self, client_ref: str, now: datetime | None = None) -> list[FlagTicket]:
        """The tickets of the flags that are not resolved for one client (matched ignoring case; an empty
        reference matches nothing), in the order of the Overview table. [] only when there are none. Raises
        ValueError(AUDIT_UNAVAILABLE) if the log cannot be read, and ValueError(FLAGS_UNAVAILABLE)."""
        wanted = str(client_ref or "").strip().casefold()
        _, _, _, flags, tickets = self.__flag_view("client_flags", App.__checked_now(now), False)
        return App.__table_order([tickets[flag.flag_id] for flag in flags
                                  if wanted and flag.client_ref.casefold() == wanted
                                  and tickets[flag.flag_id].status != "resolved"])

    def audit_trail(self, client_ref: str) -> tuple[list[AuditEvent], int]:
        """(every audit event about one client, newest first; how many rows of the whole log cannot be read
        and so may be missing from it). The reference is matched ignoring case; an empty one matches nothing.
        Raises ValueError(AUDIT_UNAVAILABLE) if the log cannot be read."""
        rows = self.__audit_rows("audit_trail")
        readable, unreadable = App.__audit_events(rows, "audit_trail")
        wanted = str(client_ref or "").strip().casefold()
        events = [event for event in readable if wanted and event.client_ref.casefold() == wanted]
        events.reverse()
        return events, unreadable

    def last_activity(self) -> dict[str, AuditEvent]:
        """The newest audit event about each client, by client reference in lower case (one read of the
        log). Events with no client are not counted. {} if no client has any. Raises ValueError(AUDIT_UNAVAILABLE)
        if the log cannot be read."""
        readable, _ = App.__audit_events(self.__audit_rows("last_activity"), "last_activity")
        latest: dict[str, AuditEvent] = {}
        for event in readable:                      # file order is oldest first, so a later one replaces an earlier one
            if event.client_ref:
                latest[event.client_ref.casefold()] = event
        return latest

    def verify_audit_log(self, actor: str) -> AuditChain:
        """Check the hash chain of the whole log and write an "audit verified" line. The line's result is
        "failed" only when the chain is broken (the check itself ran; if it could not run, nothing is written
        and ValueError is raised). Raises ValueError(AUDIT_UNAVAILABLE) if the log cannot be read, and
        ValueError(AUDIT_KEY_MISSING) if no audit key is set."""
        self.__start(actor)
        if not self.__audit_key:
            raise ValueError(App.AUDIT_KEY_MISSING)
        rows = self.__audit_rows("verify_audit_log")
        chain = AuditChain(rows, self.__audit_key)
        self.__record("audit_verified", actor, "", "ok" if chain.intact() else "failed",
                      {"entries": len(rows), "intact": chain.intact(), "breaks": len(chain.breaks())})
        return chain

    def __audit_rows(self, caller: str) -> list[dict]:
        """Every row of the audit log, file order. Raises ValueError(AUDIT_UNAVAILABLE) if it cannot be read."""
        try:
            return self.__audit.load()
        except (OSError, ValueError) as error:
            logger.error("App.%s: the audit log cannot be read: %r", caller, error)
            raise ValueError(App.AUDIT_UNAVAILABLE) from error

    @staticmethod
    def __checked_now(now: datetime | None) -> datetime:
        """now, or the current time; ValueError if it carries no timezone."""
        now = now or datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("The time must carry a timezone.")
        return now

    @staticmethod
    def __table_order(tickets: list[FlagTicket]) -> list[FlagTicket]:
        """Flags that are not resolved first, by priority (the order given, newest first, is kept inside a
        priority), then the resolved ones in the order given."""
        rank = {severity: number for number, severity in enumerate(OverviewPage.SEVERITIES)}
        open_ones = sorted((t for t in tickets if t.status != "resolved"), key=lambda t: rank[t.flag.severity])
        return open_ones + [t for t in tickets if t.status == "resolved"]

    def __flag_view(self, caller: str, now: datetime, strict: bool
                    ) -> tuple[list[AuditEvent], int, int, list[Flag], dict[str, FlagTicket]]:
        """One read of the log, worked into (the readable events, how many rows cannot be read, the first
        broken entry or 0, the flags newest first, a ticket per flag id). strict says the chain must be
        checked: with no audit key that is an error (ValueError(AUDIT_KEY_MISSING)); when not strict the
        entry is taken as 0 and the missing key is logged (start() already refuses to run without a key).
        Raises ValueError(AUDIT_UNAVAILABLE) if the log cannot be read, ValueError(FLAGS_UNAVAILABLE) if the
        rules fail."""
        events, unreadable, broken_at = self.__read_log(caller, strict)
        flags, tickets, _ = self.__work_out_flags(caller, events, broken_at, now)
        return events, unreadable, broken_at, flags, tickets

    def __read_log(self, caller: str, strict: bool) -> tuple[list[AuditEvent], int, int]:
        """(the readable events, how many rows cannot be read, the first broken entry or 0). See __flag_view
        for strict. Raises ValueError(AUDIT_UNAVAILABLE) if the log cannot be read."""
        return self.__events_of(self.__audit_rows(caller), caller, strict)

    def __events_of(self, rows: list[dict], caller: str, strict: bool) -> tuple[list[AuditEvent], int, int]:
        """__read_log for rows that have been read already. Raises ValueError(AUDIT_KEY_MISSING) as it does."""
        events, unreadable = App.__audit_events(rows, caller)
        broken_at = 0
        if rows and not self.__audit_key:
            if strict:
                raise ValueError(App.AUDIT_KEY_MISSING)
            logger.error("App.%s: the audit log was not checked for changes, no audit key is set", caller)
        elif rows:
            breaks = AuditChain(rows, self.__audit_key).breaks()
            broken_at = breaks[0] if breaks else 0
        return events, unreadable, broken_at

    def __work_out_flags(self, caller: str, events: list[AuditEvent], broken_at: int, now: datetime
                         ) -> tuple[list[Flag], dict[str, FlagTicket], int]:
        """(the flags newest first, a ticket per flag id, how many flags the rules found but could not build).
        The ones that could not be built are logged here. Raises ValueError(FLAGS_UNAVAILABLE) if the rules fail."""
        try:
            insights = self.__rules(events, self.__audit_policy, broken_at, now)
            flags = insights.flags()
            # Only updates the app itself signed count: a line added or changed in the file by hand has no
            # valid hash, so it can never move a flag (not even close the "log changed outside the app" one).
            updates = [event for event in events if event.action == "flag_updated"
                       and (not self.__audit_key or event.hash_matches(self.__audit_key))]
            tickets = {flag.flag_id: FlagTicket(flag, updates) for flag in flags}
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            logger.error("App.%s: the flags could not be worked out from the audit log: %r", caller, error)
            self.__audit_note.to_handle = None
            raise ValueError(App.FLAGS_UNAVAILABLE) from error
        self.__audit_note.to_handle = sum(1 for ticket in tickets.values() if ticket.status != "resolved")
        if insights.skipped:
            logger.error("App.%s: %d flag(s) found by the rules could not be built and are left out",
                         caller, insights.skipped)
        return flags, tickets, insights.skipped

    def begin_request(self, actor: str) -> None:
        """A new request starts on this thread (one web request, or one pass of the terminal menu): the
        "database unreadable" line may be written once again, and a read that fails during the request is
        recorded as done by actor (the signed-in name, or TERMINAL, or UNKNOWN when nobody is signed in).
        Raises ValueError if actor is neither TERMINAL, UNKNOWN nor a configured account name."""
        self.__check_actor(actor)
        self.__audit_note.read_failed = False
        self.__audit_note.actor = actor
        self.__audit_note.to_handle = None

    def open_flag_count(self, now: datetime | None = None) -> int | None:
        """How many flags are still to handle, for the admin header badge. The log is read once; if it has the
        same number of rows and the same last row as when the count was last worked out, that count is returned
        without checking the chain or running the rules again (any new line, such as a flag update, changes the
        fingerprint). None when it cannot be worked out (never a made-up 0); the reason is logged. Raises
        ValueError if now has no timezone."""
        now = App.__checked_now(now)
        try:
            rows = self.__audit_rows("open_flag_count")
            fingerprint = (len(rows), str(rows[-1].get("hash", "")) if rows and isinstance(rows[-1], dict) else "")
            with self.__flag_count_lock:
                if self.__flag_count is not None and self.__flag_count[0] == fingerprint:
                    return self.__flag_count[1]
            events, _, broken_at = self.__events_of(rows, "open_flag_count", False)
            _, tickets, _ = self.__work_out_flags("open_flag_count", events, broken_at, now)
        except ValueError as error:                 # already logged where it happened
            logger.error("App.open_flag_count: the open flags cannot be counted: %s", error)
            return None
        count = sum(1 for ticket in tickets.values() if ticket.status != "resolved")
        with self.__flag_count_lock:
            self.__flag_count = (fingerprint, count)
        return count

    def flags_to_handle(self) -> int | None:
        """How many flags were still to handle the last time this request (thread) worked the flags out, so a
        page that has just done so can show the header badge without reading the log again. None if no flags
        were worked out since begin_request(), or they could not be (never a made-up 0)."""
        return getattr(self.__audit_note, "to_handle", None)

    def __read_failed(self, what: str, actor: str = "") -> None:
        """Write one "database unreadable" line (it feeds the "Read failed" bar of the Overview), at most
        once for each request (thread). The actor is the one given, else the one begin_request() remembered,
        else UNKNOWN. Never raises, and leaves audit_write_failed() as it was: the line is about a read that
        failed, not about an action that was kept."""
        if getattr(self.__audit_note, "read_failed", False):
            return
        actor = actor or getattr(self.__audit_note, "actor", "") or App.UNKNOWN
        self.__audit_note.read_failed = True
        failed_before = bool(getattr(self.__audit_note, "failed", False))
        try:
            self.__record("data_unavailable", actor, "", "failed", {"what": what})
        except Exception as error:                    # __record never raises; this is for certainty
            logger.error("App.__read_failed: the audit line could not be written: %r", error)
        self.__audit_note.failed = failed_before

    @staticmethod
    def __audit_events(rows: list[dict], caller: str) -> tuple[list[AuditEvent], int]:
        """(the rows that can be shown as events, and how many cannot). A row can be shown if it is sealed
        and has a time and an id of its own written in the row (a hand-added row would otherwise be given a
        made-up time). The others are counted and logged here; the pages say how many there are, and Verify
        log shows which."""
        events: list[AuditEvent] = []
        unreadable = 0
        for row in rows:
            try:
                event = AuditEvent.from_dict(row)
            except ValueError:
                unreadable += 1
                continue
            if event.is_sealed() and row.get("at") and row.get("event_id"):
                events.append(event)
            else:
                unreadable += 1
        if unreadable:
            logger.warning("App.%s: %d audit row(s) cannot be read and are not listed", caller, unreadable)
        return events, unreadable

    def client_outcome_failed(self) -> bool:
        """True if the last save_assessment in this thread saved the assessment but could not write its
        outcome onto the client record (the audit line then says "record_saved": False)."""
        return bool(getattr(self.__audit_note, "outcome_failed", False))

    def audit_write_failed(self) -> bool:
        """True if the last action in this thread was done but its audit line could not be written."""
        return bool(getattr(self.__audit_note, "failed", False))

    def __start(self, actor: str) -> None:
        """Begin an action: forget the last audit failure of this thread and check who is acting.
        Raises ValueError (a programming error) if actor is neither TERMINAL, UNKNOWN nor a configured account name."""
        self.__audit_note.failed = False
        self.__audit_note.outcome_failed = False
        self.__audit_note.read_failed = False
        self.__check_actor(actor)

    def __check_actor(self, actor: str) -> None:
        """Raises ValueError (a programming error) if actor is neither TERMINAL, UNKNOWN nor a configured
        account name."""
        known = isinstance(actor, str) and (actor in (App.TERMINAL, App.UNKNOWN)
                                            or any(account.name == actor for account in self.__config.accounts))
        if not known:
            raise ValueError("The actor must be 'terminal', 'unknown' or the name of a configured account.")

    def __record(self, action: str, actor: str, client_ref: str = "", result: str = "ok",
                 details: dict | None = None, kept: bool = False) -> bool:
        """Add one line to the audit log. Never raises: if it cannot be written the real error is logged,
        audit_write_failed() turns True, and the terminal is told (the web app checks audit_write_failed()).
        kept is True when the action saved something: the message then says "Saved, but ...", otherwise it
        only says the action could not be written."""
        self.__audit_note.failed = False
        try:
            event = AuditEvent(actor=actor, action=action, client_ref=client_ref, result=result, details=details)
            self.__audit_note.event_id = event.event_id
            written = self.__audit.save(event.to_dict())
        except Exception as error:
            logger.error("App.__record: the audit line for %s could not be made or saved: %r", action, error)
            written = False
        if not written:
            logger.error("App.__record: the audit line for %s by %s was not written", action, actor)
            self.__audit_note.failed = True
            if actor == App.TERMINAL:
                self.__ui.show_error(App.AUDIT_NOT_WRITTEN if kept else App.AUDIT_LINE_NOT_WRITTEN)
        return written

    # ----- the objects set-up code and tests reach through App ------------------------------

    def clients(self) -> Repository:
        return self.__clients

    def assessments(self) -> AssessmentRepository:
        return self.__assessments

    def documents(self) -> DocumentStore:
        return self.__documents

    def rate_limiter(self) -> RateLimiter:
        return self.__limiter

    def response_cache(self) -> ResponseCache:
        return self.__response_cache

    def runner(self) -> AssessmentRunner:
        return self.__runner

    # ----- private ---------------------------------------------------------------------------------

    def __ai_model(self) -> str:
        """The model name the AI caller reports, or "" when there is no caller."""
        return getattr(self.__ai_caller, "model_name", lambda: "")() if self.__ai_caller else ""

    def __ai_search_model(self) -> str:
        """The model the AI caller uses for a web search (research), or the normal model's name
        when the caller has no separate one."""
        if not self.__ai_caller:
            return ""
        return getattr(self.__ai_caller, "search_model_name", self.__ai_model)()

    def __create_document_ai(self) -> DocumentAI:
        """The document reader. It gets no caller when the AI is unavailable, so it then
        cannot answer."""
        caller = self.__ai_caller if self.ai_available() else None
        return DocumentAI("ai", caller, self.__ai_model(), 0.0)

    def __create_runner(self, policy: dict) -> AssessmentRunner:
        """The AssessmentRunner and the five AI services it is handed. App creates the services
        but does not keep them, except the document reader (created in __init__), which the
        new-client screen also uses."""
        caller = self.__ai_caller if self.ai_available() else None
        model = self.__ai_model()
        settings = self.forecast_settings()
        return AssessmentRunner(
            self.__config,
            ResearchAI("ai", self.__ai_caller, self.__ai_search_model(), 0.0, policy.get("research_max_reports", 8),
                       policy.get("research_max_excerpts_per_report", 5)),
            TypologyAI("ai", self.__ai_caller, model, 0.0, policy.get("typology_max_patterns", 5)),
            BenchmarkAI("ai", self.__ai_caller, model, 0.0),
            self.__document_ai,
            ForecastAI("ai", caller, model, 0.0, CaseTimeline.FORECAST_YEARS, settings,
                       self.__config.vocabulary),
            self.__documents, self.__response_cache)

    def __handle_failure(self, step: str, error: str) -> bool:
        """Decide what happens when a step of an assessment fails. Returns True to carry on
        without the step, False to stop the assessment."""
        if step in App.CRITICAL_STEPS:
            logger.error("App: critical step failed, stopping the assessment: %s (%s)", step, error)
            self.__ui.show_error(f"{step} failed, so no verdict can be given: {error}")
            return False
        logger.warning("App: step failed, carrying on without it: %s (%s)", step, error)
        self.__ui.show_message(f"   ! {step} could not be completed and is left out: {error}")
        return True

    def __handle_failure_quietly(self, step: str, error: str) -> bool:
        """The same decision as __handle_failure, written to the log only."""
        critical = step in App.CRITICAL_STEPS
        logger.log(logging.ERROR if critical else logging.WARNING,
                   "App: step failed (%s): %s (%s)", "stopping" if critical else "carrying on", step, error)
        return not critical

    def __maybe_assess(self, record: ClientRecord) -> None:
        """Check the rate limit; if clear, run the assessment."""
        allowed, wait = self.__limiter.check("cli")
        if not allowed:
            self.__ui.show_rate_limit_error(wait)
            return
        self.__limiter.record("cli")
        self.assess_client_record(record)

    def __fill_field(self, builder: DocumentRecordBuilder, record: ClientRecord, field: dict,
                     optional: bool = False) -> ClientRecord:
        """Ask the officer for one missing detail until the record accepts it. An optional detail
        may be left empty by pressing Enter (the record is then unchanged)."""
        while True:
            try:
                if optional:
                    answer = self.__client_form.ask_optional_field(field)
                    return record if answer in (None, []) else builder.set_path(record, field["path"], answer)
                return builder.set_path(record, field["path"], self.__client_form.ask_missing_field(field))
            except ValueError as error:
                logger.warning("App: %s was not accepted: %r", field["label"], error)
                self.__ui.show_error(f"That value cannot be used because {error}. Please try again.")

    def __show_step(self, number: int, label: str) -> None:
        self.__ui.show_step(number, len(AssessmentRunner.STEPS), label)

    def __saved_verdict(self, saved: dict) -> Verdict | None:
        """A saved assessment as a Verdict holding its saved report, so it can be shown again.
        None (and logged) if the saved outcome or report is not possible."""
        try:
            verdict = Verdict(str(saved.get("assessment_id") or ""), str(saved.get("client_ref") or ""),
                              str(saved.get("assessed_at") or ""), saved.get("outcome"))
            verdict.report = saved["report"]
        except ValueError as error:
            logger.error("App: the saved assessment %s cannot be read: %r", saved.get("assessment_id"), error)
            return None
        return verdict

    def __configure_logging(self) -> None:
        """Send all logging to logs/app.log. Nothing goes to the console. Done once: a second
        call keeps the handler it made (no duplicate lines). When the file reaches LOG_MAX_BYTES
        it is renamed app.log.1 and a new one is started; only LOG_BACKUPS old files are kept."""
        root_logger = logging.getLogger()
        if any(getattr(handler, "name", None) == App.LOG_HANDLER_NAME for handler in root_logger.handlers):
            return
        log_dir = os.path.join(self.__root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8",
                                                       maxBytes=App.LOG_MAX_BYTES, backupCount=App.LOG_BACKUPS)
        handler.set_name(App.LOG_HANDLER_NAME)
        handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        for name in App.NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
