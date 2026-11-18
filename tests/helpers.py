"""
helpers.py - shared helpers for the golden and cross-check tests.

The real AI replies are read from the local cache where the system saves them
(data/cache/clients/<client_ref>.json, written when you run the system on a case).

Only sample files in the forecasting format (career_history, investments, claims) are
used. data/sample also holds client records in the New Client form's format
(case_daniel_tan.json, case_benchmark.json); those go through the menu, not these tests.

Tests that need saved replies are skipped, with a message, until the case has been run.
"""

import json
import os

import pytest

from app.ai.forecast_ai import ForecastAI
from app.ai.response_cache import ResponseCache
from app.data.case_files import CaseFiles
from app.logic.forecast import Forecast
from tests.logic_fixtures import CONFIG, POLICY, VOCABULARY

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
GOLDEN_DIR = os.path.join(TESTS_DIR, "golden")
CROSSCHECK_DIR = os.path.join(TESTS_DIR, "crosscheck")
SAMPLE_DIR = os.path.join(ROOT_DIR, "data", "sample")
FILES = CaseFiles(SAMPLE_DIR)

CASE_IDS = sorted(os.path.splitext(os.path.basename(path))[0]
                  for path in FILES.list_samples() if FILES.is_forecasting_case(FILES.load(path)))


def load_case(case_id: str) -> dict:
    case = FILES.load(os.path.join(SAMPLE_DIR, f"{case_id}.json"))
    assert case is not None, f"data/sample/{case_id}.json is missing or not valid JSON"
    return case


def saved_replies(case_id: str) -> dict:
    """The real forecast replies saved for this case, or skip the test if there are none.
    The client's file is read as it is (the fingerprint is not checked): these tests replay
    whatever the last real run saved."""
    client_ref = load_case(case_id)["client_ref"]
    folder = os.getenv("CACHE_DIR") or os.path.join(ROOT_DIR, "data", "cache")
    path = os.path.join(folder, ResponseCache.CLIENT_FOLDER, f"{client_ref}.json")
    try:
        with open(path, encoding="utf-8") as handle:
            replies = json.load(handle)["replies"]["forecast"]
    except (OSError, ValueError, KeyError, TypeError):
        replies = {}
    if not replies:
        pytest.skip(f"no saved AI replies for {client_ref} in the database yet - assess {case_id} "
                    "in the system first, so its AI replies are saved")
    return replies


def run_from_saved(case_id: str) -> dict:
    """Rebuild the forecast from the saved replies. No API calls. Returns {"case", "forecast"}."""
    case = load_case(case_id)
    replies = saved_replies(case_id)
    service = ForecastAI("saved", None, "", 0.0, 4, POLICY["forecasting"], VOCABULARY)
    run = service.run({"record": case, "cache": replies})
    assert run["ok"], (f"the saved replies for {case_id} are incomplete (stopped at {run['failed_step']}) - "
                       f"run the system on {case_id} again so it finishes")
    return {"case": case, "forecast": run["forecast"]}


def decision(case_id: str) -> dict:
    """The onboarding decision from the saved replies, as it would look saved to JSON."""
    run = run_from_saved(case_id)
    return as_saved(Forecast(POLICY, CONFIG).run(run["case"], {"forecast": run["forecast"]}))


def golden_path(case_id: str, name: str) -> str:
    return os.path.join(GOLDEN_DIR, case_id, name)


def read_golden(case_id: str, name: str) -> dict:
    path = golden_path(case_id, name)
    if not os.path.exists(path):
        pytest.skip(f"tests/golden/{case_id}/{name} doesn't exist yet - run `python -m tests.update_golden` "
                    f"and check the result as a team")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def as_saved(value: dict) -> dict:
    """What a result looks like after saving to JSON and reading back (number keys become strings)."""
    return json.loads(json.dumps(value))
