"""
main.py - runs the Source of Wealth screening system. It only coordinates: the four
managers never import each other's work, everything is passed through here.

    python main.py                          interactive menu
    python main.py --case data/sample/case_001.json
                                            assess one sample case
    python main.py --all-samples            assess every sample case in the forecasting format
    python main.py --all-samples --demo     the same, using the recorded AI replies in tests/golden
                                            (for machines with no API key, e.g. CI)
    python main.py --web                    the web app (http://127.0.0.1:5000)

ONE assessment, shared with the web app (both run App.assess, so the command line and the
web app give the same verdict and the same report):

    The client record -> the case (logic_manager.forecasting_case; the CLI asks for anything missing)
     1    Documents           every supporting document is read: what they SHOW (the documents layer),
                              compared later with what the client DECLARED
     2-5  Crime scan context  research reports -> verified -> sector typologies -> verified quotes
     6-10 Forecast            declaration (read ONCE, shared with the crime scan) -> economy ->
                              pay + assets -> person types BUILT FROM the typologies -> behaviour + events
                              (pay is then set to what his tax notices / employment letter show)
     11   Benchmark           peers in the same economy (the forecast's markets go to the benchmark AI)
     12   Test every story    crime warning signs per person type, benchmark checks cross-checked
                              against the forecast, forecast checks, documents vs declaration
     13   ONE verdict         logic_manager.combined_verdict -> logic_manager.verdict_report
     14   Save                one assessment record (verdict, report and the evidence behind them)
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

_BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE, ".env"))  # read .env before ai_manager reads its settings

from app import ai_manager, data_manager, io_manager, logic_manager, utilities  # noqa: E402
from app.ai.ai_caller import gemini_caller, openai_caller, with_fallback  # noqa: E402
from app.application.app import App  # noqa: E402
from app.application.assessment_runner import AssessmentRunner  # noqa: E402
from app.model.config import Config  # noqa: E402


def _configure_logging() -> None:
    utilities.configure_logging(logging.DEBUG)


# ---------------------------------------------------------------------------
# The combined assessment (used by the command line AND the web app)
# ---------------------------------------------------------------------------

# The steps both the command line and the web app's loading page show, in order
ASSESSMENT_STEPS = list(AssessmentRunner.STEPS)


def today() -> str:
    """Every assessment is dated today (the command line and the web app both use this)."""
    return datetime.now().date().isoformat()


def prepare_case(client_record: dict) -> dict | None:
    """The case to assess, built exactly as the web app builds it. The command line only asks
    the officer for what can't be read from the record."""
    case, missing = logic_manager.forecasting_case(client_record, today())
    if case is None:
        io_manager.show_error("Needed before the assessment can run: " + ", ".join(missing))
        case = io_manager.case_from_client_record(client_record)
        if case is None:
            return None
    problems = io_manager.validate_case(case)
    if problems:
        io_manager.show_case_problems(case["client_ref"], problems)
        return None
    return case


class _OldFunction:
    """Stands in for an AI service while the older tests still replace the ai_manager functions:
    run() calls the old function, so a test that replaces it is still obeyed. Removed with them."""

    def __init__(self, call) -> None:
        self.__call = call
        self.__warnings: list[str] = []

    def run(self, source: dict):
        answer = self.__call(source)
        if isinstance(answer, tuple):
            answer, self.__warnings = answer[0], list(answer[1])
        return answer

    def warnings(self) -> list[str]:
        return list(self.__warnings)


def _runner() -> AssessmentRunner:
    """The AssessmentRunner, with its AI services reached through the old ai_manager function names."""
    config = Config(utilities.policy(), utilities.vocabulary())
    return AssessmentRunner(
        config,
        _OldFunction(lambda source: ai_manager.get_ai_research(source["case"])),
        _OldFunction(lambda source: ai_manager.get_typologies(source["case"], source["research"])),
        _OldFunction(lambda source: ai_manager.get_ai_benchmark(source["client"], source["economy"])),
        _OldFunction(lambda source: ai_manager.extract_client_details(source["documents"])),
        _OldFunction(lambda source: ai_manager.run_onboarding_forecast(
            source["record"], source["cache"], source["typologies"], source["on_step"])),
        data_manager._document_store(),
        utilities.response_cache())


def run_combined_assessment(case: dict, supporting_documents: list[dict] | None = None, on_step=None) -> dict:
    """Documents, crime scan, forecast and benchmark as ONE assessment, then ONE verdict.
    AssessmentRunner (app/application) does the work; on_step(number, label) is told each step."""
    return _runner().run(case, supporting_documents, on_step)


def save_combined_assessment(result: dict, client_record: dict | None = None,
                             on_step=None) -> str | None:
    """Save the assessment as ONE record (and the case on the client record, when given).
    Returns the assessment id, or None if it couldn't be saved."""
    if on_step is not None:
        on_step(len(ASSESSMENT_STEPS), ASSESSMENT_STEPS[-1])
    case = result["case"]
    verdict = result["verdict"]
    if client_record is not None:
        client_record["forecasting_case"] = case
        client_record.update(outcome=verdict["verdict"], routing=verdict["next_step"],
                             next_review_date=verdict["next_review_date"], last_assessed_on=verdict["assessed_on"])
        if not data_manager.save_case_record(client_record):
            logging.getLogger(__name__).error(
                "save_combined_assessment: could not save client record for %s",
                case.get("client_ref")
            )
    assessment_id = str(uuid.uuid4())
    saved = data_manager.save_assessment({
        "assessment_id": assessment_id,
        "client_ref": case["client_ref"],
        "kind": "onboarding",
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "outcome": result["verdict"]["verdict"],
        "verdict": result["verdict"],
        "report": result["report"],
        "crime_scan": {"research": result["research"], "typologies": result["typology_response"],
                       "declaration": result["crime_declaration"]},
        "crime_result": result["crime_result"],
        "benchmark": result["benchmark"],
        "document_evidence": result["evidence"],
        "forecast": result["forecast_assessment"],
        "assessment": result["forecast_assessment"],
    })
    return assessment_id if saved else None


def _show_step(number: int, label: str) -> None:
    io_manager.show_step(number, len(ASSESSMENT_STEPS), label)


def assess_client_record(client_record: dict) -> dict | None:
    """The command line's assessment of a saved client: the same flow and report as the web app."""
    case = prepare_case(client_record)
    if case is None:
        return None
    io_manager.show_message(f"\nAssessing {case['client_ref']}: documents, crime scan, forecast and benchmark together.")
    result = run_combined_assessment(case, client_record.get("supporting_documents"), on_step=_show_step)
    saved = save_combined_assessment(result, client_record, on_step=_show_step)
    io_manager.show_verdict_report(result["report"],
                                   crime_result=result.get("crime_result"),
                                   typologies=result.get("typologies"))
    if saved:
        io_manager.show_message("Assessment saved.")
    else:
        io_manager.show_error("Could not save the assessment.")
    return result


# ---------------------------------------------------------------------------
# New client from a folder of documents (menu option 2)
# ---------------------------------------------------------------------------

def new_client_from_documents() -> dict | None:
    """Read a folder of documents, auto-fill the client, ask for what's missing, show a summary
    to check, then save. Returns the saved record (to assess) or None."""
    # 1. Which folder
    while True:
        folder = io_manager.ask_document_folder()
        if folder is None:
            return None
        paths = data_manager.list_documents_in_folder(folder)
        if paths is None:
            io_manager.show_error(f"Folder not found: {folder}")
        elif not paths:
            io_manager.show_error("No PDF, Word, Excel, text or image files in that folder.")
        else:
            break
    io_manager.show_documents_found(paths)

    # 2. Read the documents and let the AI pull out the details
    io_manager.show_message(f"\nReading {len(paths)} document(s) with AI... this can take up to a minute.")
    documents = [data_manager.read_document_for_extraction(path) for path in paths]
    extracted, warnings = ai_manager.extract_client_details(documents)
    for warning in warnings:
        logging.getLogger(__name__).info(warning)
    if extracted is None:
        io_manager.show_ai_unavailable("Document reading")
        if not io_manager.ask_yes_no("Type the details in yourself?"):
            return None
        extracted = {}

    # 3. Build the record and ask for anything missing
    date = today()
    doc_record, _ = logic_manager.record_from_documents(extracted, io_manager.generate_client_id(), date)
    record = doc_record
    missing = logic_manager.missing_client_fields(record)
    io_manager.show_missing_intro(len(missing))
    for field in missing:
        record = logic_manager.set_path(record, field["path"], io_manager.ask_missing_field(field))
    record = logic_manager.finish_document_record(record)
    doc_record = logic_manager.finish_document_record(doc_record)

    # 4. Summary to check, edit until right, then save or discard
    notes = list(extracted.get("notes") or []) + list(warnings)
    while True:
        rows = logic_manager.summarise_document_record(record, doc_record)
        checks = logic_manager.check_document_record(record, date, utilities.policy())
        io_manager.show_document_summary(rows, paths, notes, checks)
        action = io_manager.ask_document_record_action()
        if action == "discard":
            io_manager.show_message("\nClient discarded. Nothing was saved.")
            return None
        if action == "edit":
            before = json.loads(json.dumps(record))
            io_manager.edit_existing_client(record, data_manager.upload_supporting_document)
            record = logic_manager.sync_after_edit(before, record)
            still_missing = logic_manager.missing_client_fields(record)
            for field in still_missing:
                record = logic_manager.set_path(record, field["path"], io_manager.ask_missing_field(field))
            continue
        break

    # 5. Keep the documents with the client, then save
    for path in paths:
        stored = data_manager.upload_supporting_document(path)
        if stored is None:
            io_manager.show_error(f"Could not keep a copy of {os.path.basename(path)}.")
        else:
            record.setdefault("supporting_documents", []).append(
                {"file_name": os.path.basename(path), "file_path": stored})
    if not data_manager.save_case_record(record):
        io_manager.show_error("The client could not be saved.")
        return None
    io_manager.show_message(f"\nClient saved. Reference: {record['client_ref']} "
                            f"({len(record['supporting_documents'])} document(s) attached).")
    return record if io_manager.ask_after_save(record) else None


# ---------------------------------------------------------------------------
# Sample case files and saved cases
# ---------------------------------------------------------------------------

def run_case_file(path: str) -> bool:
    """Assess a case file (the same combined assessment as the menu)."""
    case = data_manager.load_case(path)
    if case is not None and not data_manager.is_forecasting_case(case):
        io_manager.show(f"\n{os.path.basename(path)}: not in the forecasting format "
                        "(it's a client record), skipped. Use the menu to assess it.")
        return True
    problems = io_manager.validate_case(case)
    if problems:
        io_manager.show_case_problems(path, problems)
        return False
    io_manager.show_message(f"\nAssessing {case['client_ref']} ({os.path.basename(path)}).")
    result = run_combined_assessment(case, on_step=_show_step)
    if not save_combined_assessment(result, on_step=_show_step):
        io_manager.show_error("Could not save the assessment.")
    io_manager.show_verdict_report(result["report"], ask_for_evidence=False,
                                   crime_result=result.get("crime_result"),
                                   typologies=result.get("typologies"))
    return result["forecast"] is not None


def use_recorded_replies() -> int:
    """Copy the recorded AI replies from tests/golden into the reply cache.
    Only fills gaps, so real replies already saved are never overwritten."""
    golden = os.path.join(utilities.ROOT_DIR, "tests", "golden")
    cache = utilities.response_cache()
    copied = 0
    for path in data_manager.list_sample_cases():
        name = os.path.splitext(os.path.basename(path))[0]
        recorded = data_manager.load_json(os.path.join(golden, name, "ai_responses.json"), default={})
        case = data_manager.load_case(path)
        if not data_manager.is_forecasting_case(case) or not isinstance(recorded, dict):
            continue
        saved = cache.load_raw_replies(case["client_ref"])
        missing = {piece: {"ok": True, "from_cache": False, "raw": json.dumps(reply), "prompt_version": "recorded"}
                   for piece, reply in recorded.items() if piece not in saved}
        copied += cache.save_raw_replies(case["client_ref"], missing)
    return copied


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def list_assessments() -> None:
    """List saved forecasting decisions (filtered by outcome) and optionally open one."""
    outcomes = ["(all)", "PASSED", "MANUAL_REVIEW", "RISKY", "SERIOUS_RISK"]
    choice = io_manager.ask_choice("Show which outcome?", outcomes, allow_back=True)
    if choice is None:
        return          # 0 = back to the main menu
    picked = outcomes[choice]
    matches = data_manager.query_assessments(data_manager.load_all_assessments(),
                                             outcome=None if picked == "(all)" else picked)
    io_manager.show_assessment_list(matches)
    if matches and io_manager.ask_yes_no("Open one in full?"):
        labels = [f"{m['client_ref']}  {m['kind']}" for m in matches]
        chosen = matches[io_manager.ask_choice("Which one?", labels)]
        if chosen.get("report"):
            io_manager.show_verdict_report(chosen["report"])     # the combined assessment
        else:
            io_manager.show_onboarding(chosen["assessment"])     # saved before the combined verdict


def _maybe_assess(client_record: dict) -> None:
    """Check the rate limit; if clear, run the combined assessment."""
    allowed, wait = utilities.check_rate_limit("cli")
    if not allowed:
        io_manager.show_rate_limit_error(wait)
    else:
        utilities.record_assessment("cli")
        assess_client_record(client_record)


def run_menu() -> None:
    records = data_manager.load_all_assessments()   # load everything saved on startup
    io_manager.show_message(f"{len(records)} saved assessment(s) loaded.")
    while True:
        choice = io_manager.show_app_menu()
        if choice == "1":
            client_record = io_manager.create_new_client(
                save_fn=data_manager.save_case_record,
                upload_fn=data_manager.upload_supporting_document,
            )
            if client_record is not None:
                _maybe_assess(client_record)

        elif choice == "2":
            client_record = new_client_from_documents()
            if client_record is not None:
                _maybe_assess(client_record)

        elif choice == "3":
            io_manager.find_existing_client(
                find_fn=data_manager.find_client_record,
                save_fn=data_manager.save_case_record,
                download_fn=data_manager.download_supporting_document,
                upload_fn=data_manager.upload_supporting_document,
            )

        elif choice == "4":
            ref = io_manager.ask_client_ref()
            if ref is None:
                continue
            client_record = data_manager.find_client_record(ref)
            if client_record is None:
                io_manager.show_error(f"No client found with reference {ref} (or the database can't be reached).")
                continue
            _maybe_assess(client_record)

        elif choice == "5":
            list_assessments()

        elif choice == "6":
            io_manager.show_client_list(data_manager.load_all_records())
            io_manager.read_answer("Press Enter to continue...")

        elif choice == "7":
            io_manager.show_message("\n--- Synchronizing Local Data to Cloud Database ---")
            stats = data_manager.sync_json_to_mongodb()
            io_manager.show_sync_result(stats)

        elif choice == "8":
            io_manager.show_message("\nGoodbye.")
            break


def main(arguments: list[str]) -> int:
    if "--web" in arguments:      # the web app is started through App, with the AI brand chosen here
        return App(with_fallback(openai_caller(), gemini_caller())).start(["--web"])
    _configure_logging()
    problems = utilities.config_problems()
    if problems:
        for problem in problems:
            io_manager.show_error(problem)
        return 1
    if not ai_manager.has_api_key():
        io_manager.show_error("No OPENAI_API_KEY set: only saved AI replies can be used.")

    if "--demo" in arguments:
        io_manager.show(f"Demo mode: {use_recorded_replies()} recorded AI replies loaded from tests/golden.")
    try:
        if "--all-samples" in arguments:
            paths = data_manager.list_sample_cases()
            results = [run_case_file(path) for path in paths]
            return 0 if paths and all(results) else 1
        if "--case" in arguments:
            position = arguments.index("--case")
            if position + 1 >= len(arguments):
                io_manager.show_error("--case needs a file path")
                return 1
            return 0 if run_case_file(arguments[position + 1]) else 1
    except Exception:
        logging.getLogger(__name__).exception("Unexpected error in CLI")
        io_manager.show_unexpected_error()
        return 1

    try:
        run_menu()
    except Exception:
        logging.getLogger(__name__).exception("Unexpected error in CLI")
        io_manager.show_unexpected_error()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))