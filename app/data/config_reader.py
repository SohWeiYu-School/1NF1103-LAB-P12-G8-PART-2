"""ConfigReader: reads the settings files in the config folder."""

import json
import logging
import os

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ConfigReader:
    """Reads config/<name>.json. Each file is read once and kept."""

    FILE_NAMES: tuple[str, ...] = ("policy", "vocabulary")     # the files App needs, in this order
    REQUIRED: dict[str, tuple[str, ...]] = {
        "vocabulary": ("signal_codes", "document_codes", "source_types", "crime_categories"),
        "policy": ("policy_version", "tolerance", "fit", "review_interval_months", "routing", "forecasting"),
    }

    def __init__(self, folder: str = os.path.join(ROOT_DIR, "config")) -> None:
        self.__folder: str = folder
        self.__files: dict[str, dict] = {}

    def read(self, name: str) -> dict:
        """The contents of config/<name>.json. Logs the real details and raises OSError if the file is
        missing or cannot be read, ValueError if it is damaged JSON or not a JSON object. An empty
        result is never an error fallback: {} only comes back for a file that really holds {}."""
        if name in self.__files:
            return self.__files[name]
        path = os.path.join(self.__folder, f"{name}.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as error:
            logger.error("Could not read config file %s: %r", path, error)
            raise
        except ValueError as error:                  # json.JSONDecodeError, and bad UTF-8
            logger.error("Config file %s is damaged: %r", path, error)
            raise ValueError(f"config/{name}.json is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            logger.error("Config file %s does not hold a JSON object", path)
            raise ValueError(f"config/{name}.json does not hold a JSON object")
        self.__files[name] = data
        return data

    def problems(self) -> list[str]:
        """Anything missing from the config folder that would stop the app working. A file that
        cannot be read is itself a problem (named here, details in the log)."""
        problems = []
        try:
            vocabulary = self.read("vocabulary")
        except (OSError, ValueError):
            return ["config/vocabulary.json could not be read (see the log)."]
        try:
            policy = self.read("policy")
        except (OSError, ValueError):
            return ["config/policy.json could not be read (see the log)."]
        for key in ConfigReader.REQUIRED["vocabulary"]:
            if not vocabulary.get(key):
                problems.append(f"config/vocabulary.json is missing '{key}'")
        for key in ConfigReader.REQUIRED["policy"]:
            if key not in policy:
                problems.append(f"config/policy.json is missing '{key}'")
        limits = policy.get("assessment_rate_limit", {})
        if not isinstance(limits, dict):
            problems.append("config/policy.json 'assessment_rate_limit' must be an object")
        else:
            cooldown = limits.get("cooldown_seconds", 60)
            if isinstance(cooldown, bool) or not isinstance(cooldown, int) or cooldown < 0:
                problems.append("config/policy.json 'assessment_rate_limit.cooldown_seconds' must be a whole "
                                f"number of seconds, 0 or more (got {cooldown!r})")
            if not isinstance(limits.get("enabled", True), bool):
                problems.append("config/policy.json 'assessment_rate_limit.enabled' must be true or false "
                                f"(got {limits.get('enabled')!r})")
        return problems
