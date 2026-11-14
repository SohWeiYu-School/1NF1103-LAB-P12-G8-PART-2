"""
io_manager.py - the old function names of the command line interface.

The work now lives in the classes in app/interface (the IO Manager):
    ConsoleUI      every print() and input()
    ReportView     how results and records are laid out
    ClientForm     the questions that create and edit a client
    CaseBuilder    a saved record read into a case, asking for what is missing
    RateLimiter    one assessment per user per cooldown window

The functions below only pass each call on to one object of those classes, so
main.py and the older tests keep working while the rest of the refactor is done.
This file is deleted once App uses the classes directly.
"""

from typing import Callable


from app import utilities
from app.interface.case_builder import CaseBuilder
from app.interface.client_form import ClientForm
from app.interface.console_ui import ConsoleUI
from app.interface.report_view import ReportView

# One of each IO class; the functions below pass each call on to them.
_ui = ConsoleUI()
_report = ReportView(_ui)
_form = ClientForm(_ui, _report)
_cases = CaseBuilder(_ui, utilities.load_schema("case_input.schema.json"))

# The file picker needs tkinter, which isn't installed everywhere (e.g. the Docker image).
# Without it the app still runs; only choosing files to upload or download is unavailable.

Ask = Callable[[str], str]
LINE = ConsoleUI.LINE
PAYMENT_METHODS = ClientForm.PAYMENT_METHODS

def show_app_menu() -> str:
    """Display the unified main menu and return the user's choice (1-8)."""
    return _ui.show_app_menu()

def show_message(text: str) -> None:
    #Print an informational message.
    return _ui.show_message(text)

def show_error(text: str) -> None:
    #Print an error message.
    return _ui.show_error(text)

def show_ai_unavailable(feature: str = "Assessment") -> None:
    return _ui.show_ai_unavailable(feature)

def show_unexpected_error() -> None:
    return _ui.show_unexpected_error()

def show_rate_limit_error(seconds_left: int) -> None:
    return _ui.show_rate_limit_error(seconds_left)

def show_sync_result(stats: dict) -> None:
    return _ui.show_sync_result(stats)

def show_step(number: int, total: int, label: str) -> None:
    """One progress line of the combined assessment (the web app shows the same steps)."""
    return _ui.show_step(number, total, label)


REPORT_WIDTH = ReportView.REPORT_WIDTH


_CRIME_SECTION_TITLE = ReportView._CRIME_SECTION_TITLE
_CRIME_INDICATOR_LABEL = ReportView._CRIME_INDICATOR_LABEL
_CRIME_CATEGORY_LABEL = ReportView._CRIME_CATEGORY_LABEL


def _format_crime_section(crime_result: dict, typologies: list, width: int) -> list[str]:
    """Build lines for the structured crime section inside the verdict report."""
    return _report._format_crime_section(crime_result, typologies, width)


def format_verdict_report(report: dict, crime_result: dict | None = None,
                          typologies: list | None = None) -> str:
    """The combined assessment as text: the same header, sections and evidence the web app shows."""
    return _report.format_verdict_report(report, crime_result, typologies)


def format_evidence(report: dict) -> str:
    """The full evidence behind the verdict (the web app shows the same sections, collapsed)."""
    return _report.format_evidence(report)


def show_verdict_report(report: dict, ask_for_evidence: bool = True,
                        crime_result: dict | None = None, typologies: list | None = None) -> None:
    """The short report, then (if the officer wants it) the full evidence."""
    return _report.show_verdict_report(report, ask_for_evidence, crime_result, typologies)


def generate_client_id() -> str:
    """Generate a unique client reference ID."""

    return _form.generate_client_id()


def get_client_profile() -> dict:
    """Collect name, nationality and current position."""
    return _form.get_client_profile()


def _ask_job() -> dict:
    return _form._ask_job()


def get_career_history() -> list:
    """Collect previous jobs (before the current one)."""
    return _form.get_career_history()


def _ask_asset() -> dict:
    return _form._ask_asset()


def get_investments() -> list:
    return _form.get_investments()


def get_claims() -> dict:
    """Collect financial claims and asset composition."""
    return _form.get_claims()


def get_sow_declaration() -> str:
    return _form.get_sow_declaration()

def get_supporting_documents(upload_fn=None) -> list:
    """
    Ask whether the client has supporting documents.

    If yes, open a Tkinter file picker and upload
    the selected documents.
    """

    return _form.get_supporting_documents(upload_fn)


def display_section(title: str):
    """Print a formatted section heading."""

    return _ui.display_section(title)


def show_client_list(records: list) -> None:
    """Print a compact table of all saved clients."""
    return _ui.show_client_list(records)


FIELD_NAMES = ReportView.FIELD_NAMES


def _field_name(key: str) -> str:
    return _report._field_name(key)


def _field_value(key: str, value) -> str:
    """A saved value as a person would write it: 6,000,000 not 6000000.0, Singapore not ['Singapore']."""
    return _report._field_value(key, value)


def display_client_record(record: dict):
    """Display all information collected for the client."""

    return _report.display_client_record(record)


def create_new_client(save_fn=None, upload_fn=None):
    """Collect, review and optionally save a new client."""

    return _form.create_new_client(save_fn, upload_fn)


# ---------------------------------------------------------------------------
# New client from documents (menu option 2). main.py does the reading, the AI
# call and the saving; these functions only ask and show.
# ---------------------------------------------------------------------------

PEP_OPTIONS = ClientForm.PEP_OPTIONS
SOURCE_TAGS = ReportView.SOURCE_TAGS


def ask_document_folder() -> str | None:
    """Ask which folder holds the client's documents. Returns the folder path, or None to cancel."""
    return _ui.ask_document_folder()


def show_documents_found(paths: list[str]) -> None:
    return _ui.show_documents_found(paths)


def ask_missing_field(field: dict):
    """Ask for one detail the documents didn't give. field comes from logic_manager.missing_client_fields."""
    return _form.ask_missing_field(field)


def show_missing_intro(count: int) -> None:
    return _ui.show_missing_intro(count)


def _summary_value(row: dict) -> str:
    return _report._summary_value(row)


def show_document_summary(rows: list[dict], files: list[str], notes: list[str], checks: list[str]) -> None:
    """The check-before-saving summary: every field, its value, and where it came from."""
    return _report.show_document_summary(rows, files, notes, checks)


def ask_document_record_action() -> str:
    """After the summary: 'save', 'edit' or 'discard'."""
    return _ui.ask_document_record_action()


def ask_after_save(record: dict) -> bool:
    """After a client is saved: view the saved details, run the assessment, or go back.
    Returns True if the assessment should run now."""
    return _form.ask_after_save(record)


def edit_client_profile(record):
    """Edit name, nationality and current career info."""
    return _form.edit_client_profile(record)


def add_career_record(record):
    """Add a job to career_history."""
    return _form.add_career_record(record)


def edit_career_record(record):
    """Edit a job in career_history."""
    return _form.edit_career_record(record)


def add_asset_record(record):
    """Add an entry to investments."""
    return _form.add_asset_record(record)


def edit_asset_record(record):
    """Edit an entry in investments."""
    return _form.edit_asset_record(record)


def edit_asset_composition(record):
    """Edit asset composition inside claims."""
    return _form.edit_asset_composition(record)


def edit_client_declarations(record):
    """Edit claims fields."""
    return _form.edit_client_declarations(record)


def edit_sow_declaration(record):
    """Edit the Source of Wealth declaration string."""
    return _form.edit_sow_declaration(record)


def add_supporting_documents(record, upload_fn=None):
    """Add supporting documents to an existing client."""

    return _form.add_supporting_documents(record, upload_fn)

def edit_existing_client(record, upload_fn=None):
    """Allow the user to edit or add information to an existing client."""

    return _form.edit_existing_client(record, upload_fn)

def find_existing_client(find_fn=None, load_fn=None, save_fn=None, download_fn=None, upload_fn=None):
    """Find, display, edit and manage an existing client from local records."""

    return _form.find_existing_client(find_fn, load_fn, save_fn, download_fn, upload_fn)


# ============================================================================
# Forecasting: shared input helpers (bad answers are rejected and asked again)
# ============================================================================

OUTCOME_LABELS = ReportView.OUTCOME_LABELS


def show(text: str = "") -> None:
    return _ui.show(text)


def money(value: float | None) -> str:
    return _ui.money(value)


def money_range(values: dict) -> str:
    return _ui.money_range(values)


def read_answer(question: str) -> str:
    """The normal way to ask: type into the terminal."""
    return _ui.read_answer(question)


def ask_text(question: str, ask: Ask = read_answer, min_length: int = 1) -> str:
    return _ui.ask_text(question, ask, min_length)


def ask_int(question: str, ask: Ask = read_answer, minimum: int | None = None,
            maximum: int | None = None, allow_blank: bool = False) -> int | None:
    return _ui.ask_int(question, ask, minimum, maximum, allow_blank)


def ask_money(question: str, ask: Ask = read_answer, allow_zero: bool = True) -> float:
    return _ui.ask_money(question, ask, allow_zero)


def ask_choice(question: str, options: list[str], ask: Ask = read_answer, allow_back: bool = False) -> int | None:
    """Show a numbered list and return the index picked. With allow_back, 0 returns None."""
    return _ui.ask_choice(question, options, ask, allow_back)


def ask_yes_no(question: str, ask: Ask = read_answer) -> bool:
    return _ui.ask_yes_no(question, ask)

def ask_year(question: str, minimum: int = 1940, maximum: int | None = None,
             allow_blank: bool = False) -> int | None:
    return _ui.ask_year(question, minimum, maximum, allow_blank)


def ask_currency(ask: Ask = read_answer) -> str:
    return _ui.ask_currency(ask)


def ask_composition(current: dict | None = None) -> dict:
    """Four percentages that must add up to 100. Enter keeps the current value when editing."""
    return _ui.ask_composition(current)


def keep_text(label: str, current, min_length: int = 2) -> str:
    return _ui.keep_text(label, current, min_length)


def keep_int(label: str, current, minimum: int, maximum: int):
    return _ui.keep_int(label, current, minimum, maximum)


def keep_money(label: str, current):
    return _ui.keep_money(label, current)

LETTERS = ConsoleUI.LETTERS
LABEL = ConsoleUI.LABEL


def _only(text: str, allowed: str) -> bool:
    """Must contain at least one letter, and nothing outside letters + the allowed characters."""
    return _ui._only(text, allowed)


def _words_error(allowed: str) -> str:
    return _ui._words_error(allowed)


def ask_words(question: str, allowed: str = LETTERS, min_length: int = 2) -> str:
    return _ui.ask_words(question, allowed, min_length)


def keep_words(label: str, current, allowed: str = LETTERS, min_length: int = 2) -> str:
    return _ui.keep_words(label, current, allowed, min_length)


def ask_countries(question: str) -> list:
    return _ui.ask_countries(question)

MAX_EMPLOYEES = ConsoleUI.MAX_EMPLOYEES


def _parse_count(text: str) -> int | None:
    """'2,500' -> 2500. Returns None for ranges, text, zero or absurdly large numbers."""
    return _ui._parse_count(text)


def ask_count(question: str, ask: Ask = read_answer) -> int:
    return _ui.ask_count(question, ask)


def keep_count(label: str, current):
    return _ui.keep_count(label, current)


def validate_case(case: object) -> list[str]:
    """Everything wrong with a case (from a file or typed in). [] means it's fine."""
    return _cases.validate_case(case)


# ============================================================================
# Forecasting: turning a client record from the form into a forecasting case
# ============================================================================
# The New Client form saves everything as typed text, in its own layout
# (client_profile, career_timeline, asset_timeline, ...). The forecasting needs
# numbers in its own layout (career_history, investments, claims, ...).
# case_from_client_record() converts one into the other and asks the officer
# only for what the form doesn't have or what can't be read.


def _number(text: object) -> float | None:
    """Read an amount typed in the form: '1,650,000', 'S$1.65m', '2.5 million', '410k'. None if unreadable."""
    return _ui.read_number(text)


def _year(text: object) -> int | None:
    return _ui.read_year(text)


def _payment_method(text: object) -> str | None:
    """Map what was typed ('Cash', 'mortgage', 'bank loan', 'sold my flat') to cash / loan / asset_sale."""
    return _cases._payment_method(text)


def _number_or_ask(value: object, question: str, ask: Ask, allow_zero: bool = True) -> float:
    return _cases._number_or_ask(value, question, ask, allow_zero)


def _year_or_ask(value: object, question: str, ask: Ask, minimum: int | None = None,
                 maximum: int | None = None) -> int:
    return _cases._year_or_ask(value, question, ask, minimum, maximum)


def _text_or_ask(value: object, question: str, ask: Ask) -> str:
    return _cases._text_or_ask(value, question, ask)


def _jobs_from_record(record: dict, this_year: int, ask: Ask) -> list[dict]:
    """Career history entries plus the current job from career dict."""
    return _cases._jobs_from_record(record, this_year, ask)


def _first_filled(*values: object) -> object:
    """The first value that isn't None or blank text, else None."""
    return _cases._first_filled()


def _assets_from_record(record: dict, first_year: int, this_year: int, ask: Ask) -> list[dict]:
    """Investments still held, amounts in SGD. Sold assets are excluded."""
    return _cases._assets_from_record(record, first_year, this_year, ask)


def _composition_from_record(record: dict, ask: Ask) -> dict:
    """Asset composition as fractions (0.60 = 60%). Asks if missing or doesn't add up."""
    return _cases._composition_from_record(record, ask)


def case_from_client_record(record: dict, ask: Ask = read_answer) -> dict | None:
    """Build the forecasting case from a saved client record.

    Reads directly from the new flat structure. The officer is asked only for
    what's missing or unreadable.
    Returns None if the case fails validation.
    """
    return _cases.case_from_client_record(record, ask)


def show_case_problems(where: str, problems: list[str]) -> None:
    return _ui.show_case_problems(where, problems)


def ask_client_ref(ask: Ask = read_answer) -> str | None:
    return _ui.ask_client_ref(ask)


# ============================================================================
# Forecasting: progress and reports
# ============================================================================

def show_ai_progress(results: dict) -> None:
    """One line per AI request: where the reply came from and whether it passed the checks."""
    return _ui.show_ai_progress(results)


def format_onboarding(assessment: dict) -> str:
    """A readable onboarding report."""
    return _report.format_onboarding(assessment)


def format_assessment_list(records: list[dict]) -> str:
    return _report.format_assessment_list(records)


def show_onboarding(assessment: dict) -> None:
    """A forecast-only report (assessments saved before the combined verdict)."""
    return _report.show_onboarding(assessment)


def show_assessment_list(records: list[dict]) -> None:
    return _report.show_assessment_list(records)
