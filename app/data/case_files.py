"""CaseFiles: the case files kept on disk (the sample cases and the input schema)."""

import json
import logging
import os

from app.data.json_repository import ROOT_DIR

logger = logging.getLogger(__name__)


class CaseFiles:
    """Reads single JSON files: a sample case or a schema.
    A missing or damaged file gives the default instead of an error.

    folder is where the sample cases are kept.
    """

    def __init__(self, folder: str = os.path.join(ROOT_DIR, "data", "sample")) -> None:
        self.__folder: str = folder

    def list_samples(self) -> list[str]:
        """The path of every sample case file, sorted by name. [] if the folder is missing."""
        if not os.path.isdir(self.__folder):
            return []
        return sorted(os.path.join(self.__folder, name)
                      for name in os.listdir(self.__folder) if name.endswith(".json"))

    def load(self, path: str, default: object = None) -> object:
        """The contents of one JSON file, or default if it is missing or cannot be read."""
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (ValueError, OSError) as error:
            logger.warning("CaseFiles.load: could not read %s: %s", path, repr(error))
            return default

    def is_forecasting_case(self, case: object) -> bool:
        """Sample files come in two layouts; only the forecasting layout can be assessed directly."""
        return isinstance(case, dict) and "career_history" in case and "client_ref" in case
