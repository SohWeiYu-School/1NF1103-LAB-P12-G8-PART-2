"""Every Logic Manager class with injected inputs can be made with its defaults."""

import pytest

from app.logic.asset_path import AssetPath
from app.logic.audit_chain import AuditChain
from app.logic.case_timeline import CaseTimeline
from app.logic.future_paths import FuturePaths
from app.logic.onboarding_assessor import OnboardingAssessor
from app.logic.pay_calibrator import PayCalibrator
from app.logic.record_diff import RecordDiff
from app.logic.verdict_engine import VerdictEngine


@pytest.mark.parametrize("logic_class", [AssetPath, AuditChain, CaseTimeline, FuturePaths, OnboardingAssessor,
                                         PayCalibrator, RecordDiff, VerdictEngine], ids=lambda cls: cls.__name__)
def test_every_logic_class_can_be_made_with_its_defaults(logic_class):
    assert isinstance(logic_class(), logic_class)
