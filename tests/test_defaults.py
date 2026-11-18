"""Every class can be made with its default values (the professor's rule: every attribute has a type
and a default), and those defaults are safe empty values."""

import pytest

from app.ai.benchmark_ai import BenchmarkAI
from app.ai.document_ai import DocumentAI
from app.ai.forecast_ai import ForecastAI
from app.ai.research_ai import ResearchAI
from app.ai.typology_ai import TypologyAI
from app.application.assessment_runner import AssessmentRunner
from app.data.cloud_sync import CloudSync
from app.data.database_repository import DatabaseRepository
from app.data.json_repository import JsonRepository
from app.data.repository import Repository
from app.interface.case_builder import CaseBuilder
from app.interface.client_form import ClientForm
from app.interface.report_view import ReportView
from app.logic.asset_path import AssetPath
from app.logic.audit_chain import AuditChain
from app.logic.case_timeline import CaseTimeline
from app.logic.future_paths import FuturePaths
from app.logic.onboarding_assessor import OnboardingAssessor
from app.logic.pay_calibrator import PayCalibrator
from app.logic.record_diff import RecordDiff
from app.logic.verdict_engine import VerdictEngine
from app.model.account import Account
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.band import Band
from app.model.check import Check
from app.model.claimed_source import ClaimedSource
from app.model.claims import Claims
from app.model.client_profile import ClientProfile
from app.model.client_record import ClientRecord
from app.model.config import Config
from app.model.declaration import Declaration
from app.model.investment import Investment
from app.model.job import Job
from app.model.match_result import MatchResult
from app.model.research_report import ResearchReport
from app.model.review_status import ReviewStatus
from app.model.typology import Typology
from app.model.verdict import Verdict

CLASSES = [
    # AI Manager
    BenchmarkAI, DocumentAI, ForecastAI, ResearchAI, TypologyAI,
    # Application
    AssessmentRunner,
    # IO Manager
    CaseBuilder, ClientForm, ReportView,
    # Logic Manager (the classes with injected inputs)
    AssetPath, AuditChain, CaseTimeline, FuturePaths, OnboardingAssessor, PayCalibrator, RecordDiff, VerdictEngine,
    # Domain Model
    Account, AuditEvent, AuditFilter, Band, Check, ClaimedSource, Claims, ClientProfile, ClientRecord, Config,
    Declaration, Investment, Job, MatchResult, ResearchReport, ReviewStatus, Typology, Verdict,
]


@pytest.mark.parametrize("cls", CLASSES, ids=lambda cls: cls.__name__)
def test_every_class_can_be_made_with_its_defaults(cls):
    assert isinstance(cls(), cls)


def test_the_model_defaults_are_safe_empty_values():
    assert Verdict().outcome == "MANUAL_REVIEW"          # a verdict nobody filled in is never PASSED
    assert Check().status == "passed" and Check().label == ""
    assert MatchResult().breached is False
    assert Config().policy == {} and Config().vocabulary == {}
    assert Job().is_current() and Job().problems() == []


def test_forecast_ai_with_no_caller_reports_no_ai():
    assert ForecastAI()._can_ask() is False


def test_repository_interface_defines_its_own_init():
    assert "__init__" in Repository.__dict__


def test_both_kinds_of_store_are_repositories():
    assert issubclass(JsonRepository, Repository) and issubclass(DatabaseRepository, Repository)


def test_cloud_sync_with_no_stores_is_offline_and_sync_does_nothing():
    sync = CloudSync()
    assert sync.is_online() is False
    stats = sync.sync()
    assert stats["synced"] == 0 and stats["errors"]
