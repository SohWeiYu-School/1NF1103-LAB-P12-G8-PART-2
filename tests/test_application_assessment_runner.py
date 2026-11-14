"""AssessmentRunner: one assessment from made-up AI services, including the ways a step can fail."""

from app.application.assessment_runner import AssessmentRunner
from tests import fake_services
from tests.logic_fixtures import sample_case


def _run(tmp_path, save_forecast=True, on_failure=None, on_step=None, **services):
    runner, cache, fakes = fake_services.runner(tmp_path, **services)
    case = sample_case()
    if save_forecast:
        fake_services.save_forecast_replies(cache, case)
    return runner.run(case, on_step=on_step, on_failure=on_failure), fakes


def test_a_full_run_gives_one_verdict_and_one_report(tmp_path):
    result, _ = _run(tmp_path)
    assert result["verdict"]["verdict"] in ("PASSED", "MANUAL_REVIEW", "RISKY", "SERIOUS_RISK")
    assert result["verdict"]["not_run"] == []
    assert set(result["report"]) == {"header", "sections", "evidence", "evidence_titles", "legend"}
    assert result["forecast_assessment"] is not None and result["crime_result"] is not None


def test_every_step_before_saving_is_announced_in_order(tmp_path):
    seen = []
    _run(tmp_path, on_step=lambda number, label: seen.append((number, label)))
    assert [number for number, _ in seen] == list(range(1, 14))
    assert all(label == AssessmentRunner.STEPS[number - 1] for number, label in seen)


def test_the_benchmark_ai_is_never_given_the_declared_figures(tmp_path):
    _, fakes = _run(tmp_path)
    sent = fakes["benchmark"].sources[0]
    assert "Container shipping" in str(sent["economy"])
    assert "16500000" not in str(sent["economy"])


def test_the_research_ai_is_given_the_trusted_sites(tmp_path):
    _, fakes = _run(tmp_path)
    assert "fatf-gafi.org" in " ".join(fakes["research"].sources[0]["domains"])


def test_a_failed_ai_step_is_reported_and_the_run_carries_on_when_told_to(tmp_path):
    failures = []
    result, _ = _run(tmp_path, benchmark=None, on_failure=lambda step, reason: failures.append(step) or True)
    assert failures == ["The peer benchmark"]
    assert result["verdict"]["not_run"] == ["The peer benchmark"]
    assert result["benchmark"]["findings"] is None


def test_with_no_on_failure_a_failed_step_is_noted_and_the_run_carries_on(tmp_path):
    result, _ = _run(tmp_path, typologies=None)
    assert "The crime scan (sector typologies)" in result["verdict"]["not_run"]


def test_the_run_stops_when_on_failure_says_stop(tmp_path):
    failures = []

    def stop(step: str, reason: str) -> bool:
        failures.append((step, reason))
        return False

    result, fakes = _run(tmp_path, typologies=None, on_failure=stop)
    assert result is None
    assert failures[0][0] == "The crime scan (sector typologies)"
    assert fakes["benchmark"].sources == []          # nothing after the failed step ran


def test_a_forecast_that_cannot_run_is_reported_with_where_it_stopped(tmp_path):
    failures = []
    result, _ = _run(tmp_path, save_forecast=False,
                     on_failure=lambda step, reason: failures.append((step, reason)) or True)
    assert failures[0][0] == "The forecast"
    assert "API key" in failures[0][1]
    assert result["forecast"] is None
    assert result["verdict"]["verdict"] != "PASSED"       # an assessment with no forecast never passes


def test_the_same_inputs_give_the_same_verdict(tmp_path):
    first, _ = _run(tmp_path)
    second, _ = _run(tmp_path)
    assert first["verdict"] == second["verdict"]
