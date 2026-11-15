"""App: creates every object of the system and coordinates them."""

import json
import logging
import os
from datetime import datetime
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
from app.logic.case_timeline import CaseTimeline
from app.logic.document_record_builder import DocumentRecordBuilder
from app.model.client_record import ClientRecord
from app.model.config import Config
from app.model.declaration import Declaration
from app.model.verdict import Verdict

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class App:
    """The Source of Wealth screening system.

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
    CLIENT_COLLECTION: str = "client_cases"
    ASSESSMENT_COLLECTION: str = "ai_assessments"
    # What the user is told when saved records cannot be read (the real error goes to the log).
    CLIENTS_UNAVAILABLE: str = "We can't load the client database right now. Please try again later."
    ASSESSMENTS_UNAVAILABLE: str = "We can't load the saved assessments right now. Please try again later."

    def __init__(self, ai_caller: Callable[[str, dict, dict], str | None] | None = None,
                 root: str = ROOT_DIR, data_folder: str = "data") -> None:
        load_dotenv(os.path.join(root, ".env"))
        self.__root: str = root
        data_dir = data_folder if os.path.isabs(data_folder) else os.path.join(root, data_folder)
        database_dir = os.path.join(data_dir, "local database")

        # Settings (read by the Data Manager, held by a Domain Model object)
        self.__config_reader: ConfigReader = ConfigReader(os.path.join(root, "config"))
        policy_file, vocabulary_file = (self.__config_reader.read(name) for name in ConfigReader.FILE_NAMES)
        self.__config: Config = Config(policy_file, vocabulary_file)
        policy = self.__config.policy

        # Data Manager
        self.__clients: Repository = ClientRepository(os.path.join(database_dir, "sow_cases.json"))
        self.__assessments: AssessmentRepository = AssessmentRepository(
            os.path.join(database_dir, "ai_assessments.json"))
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

        # AI Manager: every service is handed the same caller and the same cache
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
        limits = policy.get("assessment_rate_limit", {}) if isinstance(policy.get("assessment_rate_limit", {}), dict) else {}
        try:
            self.__limiter: RateLimiter = RateLimiter(
                limits.get("cooldown_seconds", RateLimiter.DEFAULT_COOLDOWN_SECONDS), limits.get("enabled", True))
        except ValueError as error:
            # start() reports the setting through ConfigReader.problems() and stops; App itself must not crash.
            logger.error("App: the assessment rate limit setting is not valid, using the default: %s", error)
            self.__limiter = RateLimiter()

    # ----- what the front ends are given ----------------------------------------------

    @property
    def config(self) -> Config:
        return self.__config

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
            --demo                  use the recorded AI replies in tests/golden (no API key needed)
            --web                   start the web app instead of the menu
        """
        self.__configure_logging()
        problems = self.__config_reader.problems()
        if problems:
            for problem in problems:
                self.__ui.show_error(problem)
            return 1
        if "--web" in arguments:
            return self.start_web()
        if not self.ai_available():
            self.__ui.show_error("No OPENAI_API_KEY set: only saved AI replies can be used.")
        if "--demo" in arguments:
            self.__ui.show(f"Demo mode: {self.use_recorded_replies()} recorded AI replies loaded from tests/golden.")
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
        WebApp(self, self.__limiter).start(host or os.getenv("HOST") or "127.0.0.1", port or int(os.getenv("PORT") or 5000))
        return 0

    def run_menu(self) -> None:
        """Show the main menu until the officer chooses to leave."""
        try:
            self.__ui.show_message(f"{len(self.__assessments.load())} saved assessment(s) loaded.")
        except (OSError, ValueError) as error:
            logger.error("App.run_menu: the saved assessments cannot be read: %r", error)
            self.__ui.show_error(App.ASSESSMENTS_UNAVAILABLE)
        while True:
            choice = self.__ui.show_app_menu()
            if choice == "1":
                record = self.__client_form.create_new_client(save_fn=self.save_client,
                                                             upload_fn=self.upload_document)
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
                    self.__ui.show_error(App.CLIENTS_UNAVAILABLE)
                    continue
                self.__report_view.show_client_list(clients)
                self.__ui.read_answer("Press Enter to continue...")
            elif choice == "7":
                self.__ui.show_message("\n--- Synchronizing Local Data to Cloud Database ---")
                self.__ui.show_sync_result(self.sync_to_cloud())
            elif choice == "8":
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
               show_failures: bool = True) -> dict | None:
        """Run one assessment. Returns the result, or None if a critical step failed.
        on_failure defaults to App's own rule (CRITICAL_STEPS). show_failures=False keeps
        failed steps off the terminal (the web app shows them in the report instead)."""
        if on_failure is None:
            on_failure = self.__handle_failure if show_failures else self.__handle_failure_quietly
        return self.__runner.run(case, supporting_documents, on_step, on_failure)

    def assess_client_record(self, record: ClientRecord) -> Verdict | None:
        """The command line's assessment of a saved client: prepare, run, save, show.
        Returns the Verdict, or None if no assessment could be made."""
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
        else:
            self.__ui.show_error("Could not save the assessment.")
        return verdict

    def save_assessment(self, result: dict, record: ClientRecord | None = None,
                        on_step: Callable[[int, str], None] | None = None) -> str | None:
        """Save the assessment as ONE record, and its outcome on the client record when given.
        Returns the assessment id, or None if it could not be saved."""
        if on_step is not None:
            on_step(len(AssessmentRunner.STEPS), AssessmentRunner.STEPS[-1])
        case = result["case"]
        verdict: Verdict = result["verdict"]
        details = verdict.details()             # the layout saved under "verdict"
        if record is not None:
            # The record keeps the case's date (assessed_on), not the time the verdict was made
            # (assessed_at), so ClientRecord.record_assessment is not used here.
            record.review_status.update(verdict.outcome, verdict.next_step, verdict.next_review_date,
                                        details["assessed_on"] or self.today(), case)
            if not self.save_client(record):
                logger.error("App.save_assessment: could not save the client record for %s", verdict.client_ref)
        saved = self.__assessments.save({
            "assessment_id": verdict.assessment_id,
            "client_ref": verdict.client_ref,
            "kind": "onboarding",
            "assessed_at": verdict.assessed_at,
            "outcome": verdict.outcome,
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
        return verdict.assessment_id if saved else None

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

    def use_recorded_replies(self) -> int:
        """Copy the recorded AI replies from tests/golden into the reply cache. Only fills
        gaps, so real replies already saved are never overwritten. Returns how many were copied."""
        golden = os.path.join(self.__root, "tests", "golden")
        copied = 0
        for path in self.__case_files.list_samples():
            name = os.path.splitext(os.path.basename(path))[0]
            recorded = self.__case_files.load(os.path.join(golden, name, "ai_responses.json"), default={})
            case = self.__case_files.load(path)
            if not self.__case_files.is_forecasting_case(case) or not isinstance(recorded, dict):
                continue
            saved = self.__response_cache.load_raw_replies(case["client_ref"])
            missing = {piece: {"ok": True, "from_cache": False, "raw": json.dumps(reply),
                               "prompt_version": "recorded"}
                       for piece, reply in recorded.items() if piece not in saved}
            copied += self.__response_cache.save_raw_replies(case["client_ref"], missing)
        return copied

    # ----- clients and records ---------------------------------------------------------------

    def find_client(self, client_ref: str) -> ClientRecord | None:
        """The saved client with this reference, or None if no client has it.
        Raises ValueError, with a message that is safe to show, if the client database cannot
        be read or the saved record is not valid."""
        try:
            saved = self.__clients.find(client_ref)
        except (OSError, ValueError) as error:
            logger.error("App.find_client: the client records cannot be read: %r", error)
            raise ValueError(App.CLIENTS_UNAVAILABLE) from error
        if saved is None:
            return None
        try:
            return ClientRecord.from_dict(saved)
        except (ValueError, TypeError, AttributeError) as error:
            logger.error("App.find_client: the saved record %s cannot be read: %r", client_ref, error)
            raise ValueError(f"Client {client_ref} could not be loaded because the saved record is "
                             f"not valid: {error}.") from error

    def save_client(self, record: ClientRecord) -> bool:
        """Save the client (replacing the saved record with the same reference). False if not saved."""
        saved = self.__clients.save(record.to_dict())
        if not saved:
            logger.error("App.save_client: could not save the client record %s", record.client_ref)
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
        client_ref = self.__client_form.generate_client_id()
        try:
            document_record, _ = builder.build(extracted, client_ref)
        except ValueError as error:
            logger.error("App.__new_client_from_documents: the AI's reading is not a possible record: %r", error)
            self.__ui.show_error(f"The details read from the documents cannot be used because {error}.")
            if not self.__ui.ask_yes_no("Type the details in yourself?"):
                return None
            extracted = {}
            document_record, _ = builder.build(extracted, client_ref)
        record = document_record
        missing = builder.missing_fields(record)
        self.__ui.show_missing_intro(len(missing))
        for field in missing:
            record = self.__fill_field(builder, record, field)

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
        if not self.save_client(record):
            self.__ui.show_error("The client could not be saved.")
            return None
        self.__ui.show_message(f"\nClient saved. Reference: {record.client_ref} "
                               f"({len(record.documents())} document(s) attached).")
        return record if self.__client_form.ask_after_save(record) else None

    def read_documents(self, documents: list[dict]) -> tuple[dict | None, list[str]]:
        """Ask the AI to read documents the DocumentStore has opened. Returns (details, warnings)."""
        service = self.__document_ai
        extracted = service.run({"documents": documents})
        warnings = service.warnings()
        for warning in warnings:
            logger.info(warning)
        return extracted, warnings

    def record_builder(self, date: str = "") -> DocumentRecordBuilder:
        """A DocumentRecordBuilder for one record, dated today unless another date is given."""
        return DocumentRecordBuilder(self.__config, date or self.today())

    def new_client_ref(self) -> str:
        """A new, unused client reference."""
        return self.__client_form.generate_client_id()

    def validate_case(self, case: object) -> list[str]:
        """Everything wrong with a case. [] means it can be assessed."""
        return self.__case_builder.validate_case(case)

    def read_amount(self, text: object) -> float | None:
        """'1,650,000', 'S$1.65m', '410k' -> a number; None if it cannot be read."""
        return CaseReader.read_amount(text)

    def list_assessments(self) -> None:
        """List saved assessments (filtered by outcome) and optionally open one."""
        outcomes = ["(all)", *Verdict.OUTCOMES]
        choice = self.__ui.ask_choice("Show which outcome?", outcomes, allow_back=True)
        if choice is None:
            return          # 0 = back to the main menu
        picked = outcomes[choice]
        try:
            matches = self.__assessments.query("" if picked == "(all)" else picked)
        except (OSError, ValueError) as error:
            logger.error("App.list_assessments: the saved assessments cannot be read: %r", error)
            self.__ui.show_error(App.ASSESSMENTS_UNAVAILABLE)
            return
        self.__report_view.show_assessment_list(matches)
        if matches and self.__ui.ask_yes_no("Open one in full?"):
            labels = [f"{match['client_ref']}  {match['kind']}" for match in matches]
            chosen = matches[self.__ui.ask_choice("Which one?", labels)]
            if chosen.get("report"):                                         # the combined assessment
                verdict = self.__saved_verdict(chosen)
                if verdict is None:
                    self.__ui.show_error("This saved assessment could not be read, so its report cannot be "
                                         "shown. The other saved assessments are not affected.")
                else:
                    self.__report_view.show_verdict_report(verdict)
            else:
                self.__report_view.show_onboarding(chosen["assessment"])     # saved before the combined verdict

    def client_assessments(self, client_ref: str) -> list[dict]:
        """Every saved assessment of one client, newest first. Nothing is hidden or caught here:
        whatever the AssessmentRepository reports (a list, or an OSError or ValueError it raises when
        the saved assessments cannot be read) comes straight back. The caller shows ASSESSMENTS_UNAVAILABLE."""
        return self.__assessments.for_client(client_ref)

    def find_assessment(self, assessment_id: str) -> dict | None:
        """The saved assessment with this id, or None if there is none. Raises OSError or ValueError
        when the saved assessments cannot be read; the caller shows ASSESSMENTS_UNAVAILABLE."""
        return self.__assessments.find(assessment_id)

    def upload_document(self, file_path: str) -> str | None:
        """Keep a copy of a supporting document. Returns its id (to save in the client's
        document list), or None if it could not be copied."""
        return self.__documents.upload(file_path)

    def download_document(self, file_id: str, output_path: str) -> bool:
        """Copy a kept document out to output_path. False if it could not be copied."""
        return self.__documents.download(file_id, output_path)

    def sync_to_cloud(self) -> dict:
        """Back up clients and assessments to the cloud database.
        Returns {"cases_synced", "assessments_synced", "skipped", "errors"}."""
        stats = {"cases_synced": 0, "assessments_synced": 0, "skipped": 0, "errors": []}
        for name, sync in zip(("cases_synced", "assessments_synced"), self.__syncs):
            result = sync.sync()
            stats[name] = result["synced"]
            stats["skipped"] += result["skipped"]
            stats["errors"] += [error for error in result["errors"] if error not in stats["errors"]]
        return stats

    # ----- the objects the web app reaches through App ---------------------------------------

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

    def __create_document_ai(self) -> DocumentAI:
        """The document reader. It gets no caller when the AI is unavailable, so it then uses
        saved replies only."""
        caller = self.__ai_caller if self.ai_available() else None
        return DocumentAI("ai", caller, self.__ai_model(), 0.0, self.__response_cache)

    def __create_runner(self, policy: dict) -> AssessmentRunner:
        """The AssessmentRunner and the five AI services it is handed. App creates the services
        but does not keep them, except the document reader (created in __init__), which the
        new-client screen also uses."""
        caller = self.__ai_caller if self.ai_available() else None
        model = self.__ai_model()
        cache = self.__response_cache
        settings = self.forecast_settings()
        return AssessmentRunner(
            self.__config,
            ResearchAI("ai", self.__ai_caller, model, 0.0, cache, policy.get("research_max_reports", 8),
                       policy.get("research_max_excerpts_per_report", 5)),
            TypologyAI("ai", self.__ai_caller, model, 0.0, cache, policy.get("typology_max_patterns", 5)),
            BenchmarkAI("ai", self.__ai_caller, model, 0.0, cache),
            self.__document_ai,
            ForecastAI("ai", caller, model, 0.0, cache, CaseTimeline.FORECAST_YEARS, settings,
                       self.__config.vocabulary),
            self.__documents, cache)

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

    def __fill_field(self, builder: DocumentRecordBuilder, record: ClientRecord, field: dict) -> ClientRecord:
        """Ask the officer for one missing detail until the record accepts it."""
        while True:
            try:
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
        """Send all logging to logs/app.log. Nothing goes to the console."""
        log_dir = os.path.join(self.__root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        handler = logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        for name in App.NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
