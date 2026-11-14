"""AssessmentRunner can be made with its defaults."""

from app.application.assessment_runner import AssessmentRunner


def test_assessment_runner_can_be_made_with_its_defaults():
    assert isinstance(AssessmentRunner(), AssessmentRunner)
