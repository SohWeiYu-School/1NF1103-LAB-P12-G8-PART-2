"""ConfigReader: reads the settings files in the config folder."""

import json
import logging
import os

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ConfigReader:
    """Reads config/<name>.json. Each file is read once and kept."""

    REQUIRED: dict[str, tuple[str, ...]] = {
        "vocabulary": ("signal_codes", "document_codes", "source_types", "crime_categories"),
        "policy": ("policy_version", "tolerance", "fit", "review_interval_months", "routing", "forecasting"),
    }

    def __init__(self, folder: str = os.path.join(ROOT_DIR, "config")) -> None:
        self.__folder: str = folder
        self.__files: dict[str, dict] = {}

    def read(self, name: str) -> dict:
        """The contents of config/<name>.json. Returns {} if the file is missing or damaged."""
        if name in self.__files:
            return self.__files[name]
        path = os.path.join(self.__folder, f"{name}.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            logger.error("Could not read config file %s: %s", path, error)
            return {}
        if not isinstance(data, dict):
            logger.error("Config file %s does not hold a JSON object", path)
            return {}
        self.__files[name] = data
        return data

    def problems(self) -> list[str]:
        """Anything missing from the config folder that would stop the app working."""
        problems = []
        vocabulary = self.read("vocabulary")
        for key in ConfigReader.REQUIRED["vocabulary"]:
            if not vocabulary.get(key):
                problems.append(f"config/vocabulary.json is missing '{key}'")
        policy = self.read("policy")
        for key in ConfigReader.REQUIRED["policy"]:
            if key not in policy:
                problems.append(f"config/policy.json is missing '{key}'")
        return problems
