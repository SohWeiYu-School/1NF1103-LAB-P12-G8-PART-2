"""Every Domain Model class can be created with its default values (the professor's rule:
every attribute has a type and a default)."""

import pytest

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

MODEL_CLASSES = [Account, AuditEvent, AuditFilter, Band, Check, ClaimedSource, Claims, ClientProfile, ClientRecord, Config, Declaration,
                 Investment, Job, MatchResult, ResearchReport, ReviewStatus, Typology, Verdict]


@pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
def test_every_model_class_can_be_made_with_its_defaults(model_class):
    assert isinstance(model_class(), model_class)


def test_the_defaults_are_safe_empty_values():
    assert Verdict().outcome == "MANUAL_REVIEW"          # a verdict nobody filled in is never PASSED
    assert Check().status == "passed" and Check().label == ""
    assert MatchResult().breached is False
    assert Config().policy == {} and Config().vocabulary == {}
    assert Job().is_current() and Job().problems() == []
