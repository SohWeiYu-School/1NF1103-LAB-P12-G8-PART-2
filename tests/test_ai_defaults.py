"""Every AI service can be made with its defaults; with no AI caller it simply has no AI."""

import pytest

from app.ai.benchmark_ai import BenchmarkAI
from app.ai.document_ai import DocumentAI
from app.ai.forecast_ai import ForecastAI
from app.ai.research_ai import ResearchAI
from app.ai.typology_ai import TypologyAI


@pytest.mark.parametrize("service", [BenchmarkAI, DocumentAI, ForecastAI, ResearchAI, TypologyAI],
                         ids=lambda cls: cls.__name__)
def test_every_ai_service_can_be_made_with_its_defaults(service):
    assert isinstance(service(), service)


def test_forecast_ai_with_no_caller_reports_no_ai():
    assert ForecastAI()._can_ask() is False
