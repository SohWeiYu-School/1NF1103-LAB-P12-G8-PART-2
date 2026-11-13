"""
data_manager.py - the data layer.

Primary storage — local JSON files (data/local database/):
    sow_cases.json        one entry per client, written on every save
    ai_assessments.json   one entry per assessment, appended on every run

Backup — MongoDB Atlas, pushed only when the officer chooses
"Manual Sync to Cloud Database" (sync_json_to_mongodb):
    sow_risk_db.client_cases      mirrors sow_cases.json
    sow_risk_db.ai_assessments    mirrors ai_assessments.json
    GridFS                        uploaded supporting documents

Forecasting reply cache — local files (data/cache/forecasting/<client_ref>.json):
    raw AI replies reused on re-runs so they are free and give identical answers.

Every function returns False / None / [] / {} on error instead of crashing.
"""

import json
import logging
import os
import uuid
import shutil
import tempfile

from app import utilities
from app.data.assessment_repository import AssessmentRepository
from app.data.client_repository import ClientRepository
from app.data.cloud_sync import CloudSync
from app.data.json_repository import JsonRepository
from app.data.mongo_repository import MongoRepository

logger = logging.getLogger(__name__)

# ==============================================================================
# PATHS & DATABASE SETTINGS
# ==============================================================================

# Define the local data directory folder (e.g., .../data)
DATA_DIR = os.path.join(utilities.ROOT_DIR, "data")

# Subfolder for local JSON database files
LOCAL_DB_DIR = os.path.join(DATA_DIR, "local database")

# Set the path for saving client profiles locally
LOCAL_CASES_JSON = os.path.join(LOCAL_DB_DIR, "sow_cases.json")

# Set the path for saving AI assessment results locally
LOCAL_ASSESSMENTS_JSON = os.path.join(LOCAL_DB_DIR, "ai_assessments.json")

# Define MongoDB database and collection names
DB_NAME = MongoRepository.DB_NAME
COLLECTION_NAME = "client_cases"
ASSESSMENT_COLLECTION_NAME = "ai_assessments"

DOCUMENTS_DIR = os.path.join(DATA_DIR, "documents")


def _ensure_data_dir():
    # Make sure the local database directory exists on disk before reading or writing
    os.makedirs(LOCAL_DB_DIR, exist_ok=True)


# ==============================================================================
# LOCAL JSON FILE HELPERS (Primary Data Source)
# ==============================================================================

class _JsonFile(JsonRepository):
    """Any local JSON list file, for the functions below that still take a file path."""

    def save(self, record: dict) -> bool:
        return self._write_all(self.load() + [record])


def load_from_json(filepath: str) -> list:
    # Every record in a local JSON file; [] if it is missing or unreadable
    return _JsonFile(filepath, "client_ref").load()


def save_to_json(record: dict, filepath: str) -> bool:
    # Add the record, or replace the saved one with the same client_ref
    return ClientRepository(filepath).save(record)


# ==============================================================================
# PRIMARY CRUD OPERATIONS (Reads & Writes Local JSON First)
# ==============================================================================

def save_case_record(record: dict) -> bool:
    # Save or update a client record in local sow_cases.json, always in the current layout
    return ClientRepository(LOCAL_CASES_JSON).save(record)


def load_local_records() -> list:
    # Local sow_cases.json only (this is what Manual Sync uploads), in the current layout
    return ClientRepository(LOCAL_CASES_JSON).load()


def load_all_records() -> list:
    # Every client, from the local sow_cases.json only. MongoDB is a backup that Manual Sync
    # writes to; the app never reads clients back from it.
    return load_local_records()


def find_client_record(client_ref: str) -> dict | None:
    # One client from the local sow_cases.json (case-insensitive), or None
    return ClientRepository(LOCAL_CASES_JSON).find(client_ref)


def append_to_json(record: dict, filepath: str) -> bool:
    # Append a record to a JSON file without overwriting existing entries
    return _JsonFile(filepath, "client_ref").save(record)


def save_assessment(record: dict) -> bool:
    # Append an AI assessment record to local ai_assessments.json (multiple per client allowed)
    return AssessmentRepository(LOCAL_ASSESSMENTS_JSON).save(record)


def load_local_assessments() -> list:
    return AssessmentRepository(LOCAL_ASSESSMENTS_JSON).load()


def load_all_assessments() -> list:
    # Every saved assessment, from the local ai_assessments.json only (never from MongoDB)
    return load_local_assessments()


def query_assessments(assessments: list, outcome: str = None) -> list:
    # Filter a list of assessments by an outcome status string
    if not outcome:
        return assessments
    wanted = AssessmentRepository(LOCAL_ASSESSMENTS_JSON).query(outcome)
    return [a for a in assessments if a in wanted]


def _cloud_syncs() -> list:
    """One CloudSync for the clients and one for the assessments, both to MongoDB."""
    uri = os.getenv("MONGODB_URI")
    return [
        CloudSync(ClientRepository(LOCAL_CASES_JSON),
                  MongoRepository(COLLECTION_NAME, "client_ref", uri), SYNC_STATE_JSON),
        CloudSync(AssessmentRepository(LOCAL_ASSESSMENTS_JSON),
                  MongoRepository(ASSESSMENT_COLLECTION_NAME, "assessment_id", uri), SYNC_STATE_JSON),
    ]


def mongo_is_online() -> bool:
    return _cloud_syncs()[0].is_online()


# ==============================================================================
# SYNC FUNCTIONALITY (JSON -> MongoDB Backup)
# ==============================================================================
SYNC_STATE_JSON = os.path.join(LOCAL_DB_DIR, "sync_state.json")


def sync_json_to_mongodb() -> dict:
    # Sends only what is new or changed since the last sync
    stats = {"cases_synced": 0, "assessments_synced": 0, "skipped": 0, "errors": []}
    for name, sync in zip(("cases_synced", "assessments_synced"), _cloud_syncs()):
        result = sync.sync()
        stats[name] = result["synced"]
        stats["skipped"] += result["skipped"]
        stats["errors"] += [error for error in result["errors"] if error not in stats["errors"]]
    return stats


# ==============================================================================
# READING UPLOADED DOCUMENTS (for auto-filling the client form)
# ==============================================================================

# Longest text kept from one document, so one huge file can't crowd out the others
MAX_DOCUMENT_CHARS = 40_000

# Below this many characters a PDF is treated as scanned and sent to the AI as a file
MIN_PDF_TEXT_CHARS = 80

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif"}
TEXT_TYPES = {".txt", ".csv", ".md", ".json"}


def _pdf_text(file_path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    pages = [f"[Page {number}]\n{page.extract_text() or ''}"
             for number, page in enumerate(reader.pages, start=1)]
    return "\n\n".join(pages)


def _docx_text(file_path: str) -> str:
    from docx import Document
    document = Document(file_path)
    parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:                  # tables often hold the figures
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _xlsx_text(file_path: str) -> str:
    from openpyxl import load_workbook
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    parts = []
    for sheet in workbook.worksheets:
        parts.append(f"[Sheet {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if cell is None else str(cell) for cell in row]
            if any(cells):
                parts.append(" | ".join(cells))
    workbook.close()
    return "\n".join(parts)


def _base64_file(file_path: str) -> str:
    import base64
    with open(file_path, "rb") as handle:
        return base64.b64encode(handle.read()).decode("ascii")


def read_document_for_extraction(file_path: str, file_name: str | None = None) -> dict:
    """Read one uploaded file so the AI can pull client details out of it.

    Returns {"file_name", "kind", ...}:
        kind "text"   -> "text": the document's text (PDF, Word, Excel, plain text)
        kind "image"  -> "mime", "data_b64": a photo or scan
        kind "pdf"    -> "data_b64": a scanned PDF with no readable text
        kind "error"  -> "error": why it couldn't be read
    """
    name = file_name or os.path.basename(file_path)
    extension = os.path.splitext(name)[1].lower()
    try:
        if extension in IMAGE_TYPES:
            return {"file_name": name, "kind": "image", "mime": IMAGE_TYPES[extension],
                    "data_b64": _base64_file(file_path)}
        if extension == ".pdf":
            text = _pdf_text(file_path)
            readable = "".join(line for line in text.splitlines() if not line.startswith("[Page "))
            if len(readable.strip()) < MIN_PDF_TEXT_CHARS:
                return {"file_name": name, "kind": "pdf", "data_b64": _base64_file(file_path)}
        elif extension == ".docx":
            text = _docx_text(file_path)
        elif extension in (".xlsx", ".xlsm"):
            text = _xlsx_text(file_path)
        elif extension in TEXT_TYPES:
            with open(file_path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        else:
            return {"file_name": name, "kind": "error",
                    "error": f"{name}: this file type can't be read (use PDF, Word, Excel, text or an image)."}
    except Exception as exc:   # a damaged or password-protected file
        logger.warning("read_document_for_extraction: %s: %s", name, repr(exc))
        return {"file_name": name, "kind": "error", "error": f"{name}: could not be read ({exc.__class__.__name__})."}

    if not text.strip():
        return {"file_name": name, "kind": "error", "error": f"{name}: no text was found in it."}
    return {"file_name": name, "kind": "text", "text": text[:MAX_DOCUMENT_CHARS]}


DOCUMENT_TYPES = {".pdf", ".docx", ".xlsx", ".xlsm"} | TEXT_TYPES | set(IMAGE_TYPES)


def list_documents_in_folder(folder: str) -> list[str] | None:
    """The readable documents directly inside a folder (not sub-folders), sorted by name.
    Returns None if the folder doesn't exist. Hidden and Office temp files (~$...) are skipped."""
    folder = os.path.expanduser(folder or "")
    if not os.path.isdir(folder):
        return None
    files = []
    for name in sorted(os.listdir(folder), key=str.lower):
        path = os.path.join(folder, name)
        if (os.path.isfile(path) and not name.startswith((".", "~$"))
                and os.path.splitext(name)[1].lower() in DOCUMENT_TYPES):
            files.append(path)
    return files


# ==============================================================================
# SUPPORTING DOCUMENTS & MAIN.PY HELPERS
# ==============================================================================

def upload_supporting_document(file_path: str):
    """Copy the file into data/documents/. Does NOT touch MongoDB (sync does that later)."""
    if not os.path.exists(file_path):
        return None
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    dest = os.path.join(DOCUMENTS_DIR, f"{uuid.uuid4().hex[:8]}_{os.path.basename(file_path)}")
    try:
        shutil.copy2(file_path, dest)
    except OSError as exc:
        logger.warning("upload_supporting_document: copy failed for %s: %s", file_path, repr(exc))
        return None
    return os.path.relpath(dest, utilities.ROOT_DIR).replace("\\", "/")   # forward slashes so it works on any OS


def download_supporting_document(file_id: str, output_path: str) -> bool:
    """Copy a supporting document from its local copy in data/documents/ (never from MongoDB).
    file_id is the local path saved with the client."""
    if not file_id:
        return False
    local = os.path.join(utilities.ROOT_DIR, file_id)
    if not os.path.isfile(local):
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        shutil.copy2(local, output_path)
        return True
    except OSError as exc:
        logger.warning("download_supporting_document: copy failed for %s: %s", file_id, repr(exc))
        return False


def read_supporting_documents(entries: list[dict] | None) -> list[dict]:
    """Read every supporting document saved with a client, the same way the auto-fill reads
    uploads (read_document_for_extraction), under the file name the officer uploaded it as.
    Reads the local copies only."""
    read = []
    for entry in entries or []:
        file_id = entry.get("file_path") or entry.get("file_id")     # the local copy first
        name = os.path.basename(str(entry.get("file_name") or file_id or "document"))
        folder = tempfile.mkdtemp()
        try:
            path = os.path.join(folder, name)
            if download_supporting_document(str(file_id or ""), path):
                read.append(read_document_for_extraction(path, name))
            else:
                read.append({"file_name": name, "kind": "error", "error": f"{name}: the saved copy couldn't be found."})
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return read


# Compatibility stub functions required by main.py
def load_raw_replies(ref: str) -> dict:
    path = os.path.join(DATA_DIR, "cache", "forecasting", f"{ref}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError) as exc:
        logger.warning("load_raw_replies: could not read cache for %s: %s", ref, repr(exc))
        return {}


def save_raw_replies(ref: str, replies: dict) -> int:
    if not isinstance(replies, dict):
        return 0
    path = os.path.join(DATA_DIR, "cache", "forecasting", f"{ref}.json")
    existing = load_raw_replies(ref)
    count = 0
    for name, result in replies.items():
        if isinstance(result, dict) and result.get("raw"):
            existing[name] = result["raw"]
            count += 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except IOError as exc:
        logger.warning("save_raw_replies: could not write cache for %s: %s", ref, repr(exc))
        return 0
    return count


def save_forecast(ref: str, forecast: dict) -> bool:
    return True


def is_forecasting_case(case: dict | None) -> bool:
    """Sample files come in two formats; only the forecasting format can be assessed directly."""
    return isinstance(case, dict) and "career_history" in case and "client_ref" in case


def copy_recorded_replies(golden_dir: str) -> int:
    """Copy AI replies from tests/golden into the reply cache. Only fills gaps — existing replies
    are never overwritten. Returns the number of pieces copied."""
    copied = 0
    for path in list_sample_cases():
        name = os.path.splitext(os.path.basename(path))[0]
        recorded = load_json(os.path.join(golden_dir, name, "ai_responses.json"), default={})
        case = load_case(path)
        if not is_forecasting_case(case) or not isinstance(recorded, dict):
            continue
        saved = load_raw_replies(case["client_ref"])
        missing = {piece: {"ok": True, "from_cache": False, "raw": json.dumps(reply), "prompt_version": "recorded"}
                   for piece, reply in recorded.items() if piece not in saved}
        copied += save_raw_replies(case["client_ref"], missing)
    return copied


def load_case(path: str) -> dict | None:
    # Read a sample case file from a given file path
    return load_json(path)

def load_json(path: str, default=None):
    # Read any JSON file from disk; return default if missing or unreadable
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError) as exc:
        logger.warning("load_json: could not read %s: %s", path, repr(exc))
        return default


def sample_dir() -> str:
    # Return the absolute path to the data/sample directory
    return os.path.join(DATA_DIR, "sample")


def list_sample_cases() -> list:
    # List all sample json files inside data/sample/
    sdir = sample_dir()
    if not os.path.exists(sdir):
        return []
    return [os.path.join(sdir, f) for f in os.listdir(sdir) if f.endswith(".json")]

def load_client_assessments(ref: str) -> list:
    # Return all assessments for a client, newest first
    return AssessmentRepository(LOCAL_ASSESSMENTS_JSON).for_client(ref)


def load_assessment_by_id(assessment_id: str) -> dict | None:
    # Return a single assessment by its unique assessment_id
    return AssessmentRepository(LOCAL_ASSESSMENTS_JSON).find(assessment_id)


# ==============================================================================
# LOCAL TEST HARNESS (Only runs when data_manager.py is executed directly)
# ==============================================================================

