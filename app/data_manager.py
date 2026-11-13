"""
data_manager.py - the old function names of the data layer.

The work now lives in the classes in app/data (the Data Manager):
    ClientRepository, AssessmentRepository    local JSON files (data/local database/)
    MongoRepository, CloudSync                the MongoDB Atlas backup ("Manual Sync")
    DocumentStore and the document readers    supporting documents
    ConfigReader                              the settings files

The functions below only pass each call on to those classes, so main.py, the web
app and the older tests keep working while the rest of the refactor is done. This
file is deleted once App calls the classes directly.

Every function returns False / None / [] / {} on error instead of crashing.
"""

import json
import logging
import os
import uuid

from app import utilities
from app.data.assessment_repository import AssessmentRepository
from app.data.client_repository import ClientRepository
from app.data.cloud_sync import CloudSync
from app.data.document_store import DocumentStore
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
# SUPPORTING DOCUMENTS (DocumentStore owns the work; these names stay until App calls it directly)
# ==============================================================================

def _document_store() -> DocumentStore:
    return DocumentStore(DOCUMENTS_DIR, root=utilities.ROOT_DIR)


def read_document_for_extraction(file_path: str, file_name: str | None = None) -> dict:
    """Read one uploaded file so the AI can pull client details out of it."""
    return _document_store().read_for_extraction(file_path, file_name)


def list_documents_in_folder(folder: str) -> list[str] | None:
    """The readable documents directly inside a folder, sorted by name. None if there is no such folder."""
    return _document_store().list_folder(folder)


def upload_supporting_document(file_path: str):
    """Copy the file into data/documents/. Does NOT touch MongoDB (sync does that later)."""
    return _document_store().upload(file_path)


def download_supporting_document(file_id: str, output_path: str) -> bool:
    """Copy a supporting document from its local copy in data/documents/ (never from MongoDB)."""
    return _document_store().download(file_id, output_path)


def read_supporting_documents(entries: list[dict] | None) -> list[dict]:
    """Read every supporting document saved with a client. Reads the local copies only."""
    return _document_store().read_all(entries)


def save_forecast(ref: str, forecast: dict) -> bool:
    return True


def is_forecasting_case(case: dict | None) -> bool:
    """Sample files come in two formats; only the forecasting format can be assessed directly."""
    return isinstance(case, dict) and "career_history" in case and "client_ref" in case


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

