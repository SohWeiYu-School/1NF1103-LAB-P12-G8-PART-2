"""Made-up AI services for tests: each returns one hard-coded answer. No network."""

from app.ai.forecast_ai import ForecastAI
from app.ai.response_cache import ResponseCache
from app.application.assessment_runner import AssessmentRunner
from app.data.document_store import DocumentStore
from tests import fake_ai
from tests.logic_fixtures import CONFIG, POLICY, VOCABULARY


class FixedAI:
    """Stands in for one AI service: run() always gives the same hard-coded answer.
    answer=None means "the AI gave no usable answer" (no connection, or a malformed reply)."""

    def __init__(self, answer: dict | None, warnings: list[str] | None = None) -> None:
        self.answer = answer
        self.sources: list[dict] = []
        self.__warnings = list(warnings or [])

    def run(self, source: dict) -> dict | None:
        self.sources.append(source)
        return self.answer

    def warnings(self) -> list[str]:
        return list(self.__warnings)


def forecast_ai(caller=None) -> ForecastAI:
    """A real ForecastAI with no AI caller: it can only use the replies it is handed."""
    settings = {**POLICY["forecasting"], "retry_wait_seconds": 0,
                "net_worth_documents": POLICY.get("breach_documents", {}).get("NET_WORTH")}
    return ForecastAI("fake", caller, "fake", 0.0, 4, settings, VOCABULARY)


def save_forecast_replies(cache: ResponseCache, case: dict, documents: list[dict] | None = None,
                          overrides: dict | None = None, **options) -> None:
    """Save the made-up forecast replies for this case, as if the AI had answered before for this
    same client. documents is what DocumentStore.read_all gives for its files (none by default);
    overrides is {piece name: raw reply} that replaces the made-up reply of those pieces."""
    replies = {**fake_ai.forecast_replies(case, **options), **(overrides or {})}
    cache.save_client_replies(case["client_ref"], cache.fingerprint(case, documents or []),
                              {"forecast": dict(replies)})


def runner(tmp_path, research="default", typologies="default", benchmark="default", documents=None):
    """An AssessmentRunner whose AI services are made up. Pass None for a service to make it fail.
    Returns (runner, cache, services)."""
    cache = ResponseCache(str(tmp_path / "cache"))
    services = {
        "research": FixedAI(fake_ai.research() if research == "default" else research),
        "typologies": FixedAI(fake_ai.typologies() if typologies == "default" else typologies),
        "benchmark": FixedAI(fake_ai.benchmark() if benchmark == "default" else benchmark),
        "documents": FixedAI(documents),
    }
    built = AssessmentRunner(CONFIG, services["research"], services["typologies"], services["benchmark"],
                             services["documents"], forecast_ai(),
                             DocumentStore("data/documents", root=str(tmp_path)), cache)
    return built, cache, services
