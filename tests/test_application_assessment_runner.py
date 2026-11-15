"""AssessmentRunner: one assessment from made-up AI services, including the ways a step can fail."""

from app.application.assessment_runner import AssessmentRunner
from app.model.typology import Typology
from app.model.verdict import Verdict
from tests import fake_ai, fake_services
from tests.logic_fixtures import sample_case


def _run(tmp_path, save_forecast=True, on_failure=None, on_step=None, **services):
    runner, cache, fakes = fake_services.runner(tmp_path, **services)
    case = sample_case()
    if save_forecast:
        fake_services.save_forecast_replies(cache, case)
    return runner.run(case, on_step=on_step, on_failure=on_failure), fakes


def test_a_full_run_gives_one_verdict_and_one_report(tmp_path):
    result, _ = _run(tmp_path)
    verdict = result["verdict"]
    assert isinstance(verdict, Verdict)
    assert verdict.outcome in Verdict.OUTCOMES
    assert verdict.not_run == []
    assert set(verdict.report) == {"header", "sections", "evidence", "evidence_titles", "legend"}
    assert "report" not in result                          # the report travels on the Verdict
    assert result["forecast_assessment"] is not None and result["crime_result"] is not None


def test_each_run_gives_its_verdict_a_new_id_and_the_time_it_was_made(tmp_path):
    first, _ = _run(tmp_path)
    second, _ = _run(tmp_path)
    assert first["verdict"].assessment_id and first["verdict"].assessed_at
    assert first["verdict"].assessment_id != second["verdict"].assessment_id
    assert first["verdict"].assessed_at.endswith("+00:00")        # UTC, as saved assessments always had
    assert first["verdict"].client_ref == sample_case()["client_ref"]


def test_the_verdict_keeps_the_notes_of_the_run(tmp_path):
    result, _ = _run(tmp_path, save_forecast=False)
    notes = result["verdict"].notes
    assert any(note.startswith("The forecast stopped at") for note in notes)
    assert result["verdict"].details()["notes"] == notes
    assert "Warnings from the run" in result["verdict"].report["evidence_titles"]


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
    assert result["verdict"].not_run == ["The peer benchmark"]
    assert result["benchmark"]["findings"] is None


def test_with_no_on_failure_a_failed_step_is_noted_and_the_run_carries_on(tmp_path):
    result, _ = _run(tmp_path, typologies=None)
    assert "The crime scan (sector typologies)" in result["verdict"].not_run


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
    assert result["verdict"].outcome != "PASSED"          # an assessment with no forecast never passes


def test_the_same_inputs_give_the_same_verdict(tmp_path):
    first, _ = _run(tmp_path)
    second, _ = _run(tmp_path)
    assert first["verdict"].details() == second["verdict"].details()
    assert first["verdict"].report == second["verdict"].report


def test_the_typologies_are_checked_typology_objects_that_keep_the_reply_layout(tmp_path):
    result, _ = _run(tmp_path)
    typologies = result["typologies"]
    assert all(isinstance(typology, Typology) and typology.verified for typology in typologies)
    reply = fake_ai.typologies()["sector_typologies"][0]
    assert typologies[0].to_dict() == {**reply, "corroborated": False, "outdated_source_ids": []}
    assert result["typology_response"] == {**fake_ai.typologies(), "sector_typologies": [reply]}   # kept as given


def test_without_research_the_typologies_are_taken_unchecked(tmp_path):
    result, _ = _run(tmp_path, research=None)
    typologies = result["typologies"]
    assert all(isinstance(typology, Typology) and not typology.verified for typology in typologies)
    assert [typology.to_dict() for typology in typologies] == fake_ai.typologies()["sector_typologies"]


def test_parallel_runs_never_interleave_a_crime_scan_check_and_its_warnings(tmp_path, monkeypatch):
    """The web app runs assessments in parallel on one runner. CrimeScan keeps the warnings of its
    last check, so one run must not start a check while another is still reading its warnings.
    The check is slowed down here so that, without the runner's lock, the two would overlap."""
    import threading
    import time
    from app.logic.crime_scan import CrimeScan
    runner, cache, _ = fake_services.runner(tmp_path)
    fake_services.save_forecast_replies(cache, sample_case())
    spans, guard = [], threading.Lock()

    def slowed(original):
        def check(self, *args):
            start = time.monotonic()
            found = original(self, *args)
            time.sleep(0.2)
            with guard:
                spans.append((start, time.monotonic()))
            return found
        return check

    for name in ("verify_research", "verify_typology_sources", "read_typologies"):
        monkeypatch.setattr(CrimeScan, name, slowed(getattr(CrimeScan, name)))
    threads = [threading.Thread(target=runner.run, args=(sample_case(),)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(spans) >= 2
    spans.sort()
    for (_, earlier_end), (later_start, _) in zip(spans, spans[1:]):
        assert later_start >= earlier_end       # no check started while another was still running
