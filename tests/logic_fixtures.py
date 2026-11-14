"""A finished forecast for the sample client, built from the made-up AI replies in fake_ai. No network."""

import json
import os

from app.ai.forecast_ai import ForecastAI
from app.data.config_reader import ConfigReader
from app.model.config import Config
from tests import fake_ai

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sample", "case_001.json")
READER = ConfigReader()
POLICY = READER.read("policy")
VOCABULARY = READER.read("vocabulary")
CONFIG = Config(POLICY, VOCABULARY)


def sample_case() -> dict:
    with open(SAMPLE, encoding="utf-8") as handle:
        return json.load(handle)


def sample_forecast(case: dict, **options) -> dict:
    """The forecast the made-up replies give for this case (see fake_ai.forecast_replies)."""
    service = ForecastAI("fake", None, "fake", 0.0, None, 4, POLICY["forecasting"], VOCABULARY)
    run = service.run({"record": case, "cache": fake_ai.forecast_replies(case, **options)})
    assert run["ok"], run["failed_error"]
    return run["forecast"]
