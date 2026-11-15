"""App: the whole system put together. The AI is a made-up caller or the recorded replies; no network."""

import json
import os

import pytest

from app.application.app import App
from app.application.assessment_runner import AssessmentRunner
from tests import fake_services
from tests.logic_fixtures import sample_case


@pytest.fixture
def app(tmp_path, monkeypatch):
    """An App that keeps its records, documents and saved replies in a temporary folder and has no AI."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    return App(ai_caller=None, data_folder=str(tmp_path))


def _answers(monkeypatch, *typed):
    waiting = iter(typed)
    monkeypatch.setattr("builtins.input", lambda question="": next(waiting))


def test_app_creates_every_manager_and_shares_one_config(app):
    assert app.config.policy["policy_version"]
    assert app.steps() == list(AssessmentRunner.STEPS)
    assert app.clients().load() == [] and app.assessments().load() == []
    assert isinstance(app.runner(), AssessmentRunner)


def test_with_no_ai_caller_the_app_says_ai_is_not_available(app):
    assert app.ai_available() is False


def test_a_caller_decides_whether_ai_is_available(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))

    def caller(prompt, schema, options):
        return None

    assert App(caller, data_folder=str(tmp_path)).ai_available() is True
    caller.available = lambda: False
    assert App(caller, data_folder=str(tmp_path)).ai_available() is False


def _save_replies_for_the_samples(app):
    """Save made-up forecast replies for every sample case, as if the AI had answered before."""
    folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sample")
    for name in sorted(os.listdir(folder)):
        with open(os.path.join(folder, name), encoding="utf-8") as handle:
            case = json.load(handle)
        if "career_history" in case and "client_ref" in case:
            fake_services.save_forecast_replies(app.response_cache(), case)


def test_every_sample_is_assessed_from_saved_replies_with_no_ai(app, capsys):
    _save_replies_for_the_samples(app)
    assert app.start(["--all-samples"]) == 0
    out = capsys.readouterr().out
    assert "only saved AI replies can be used" in out
    assert "Deciding the verdict" in out
    saved = app.assessments().load()
    assert len(saved) == 2
    assert all(record["outcome"] in ("PASSED", "MANUAL_REVIEW", "RISKY", "SERIOUS_RISK") for record in saved)


def test_with_no_saved_replies_the_samples_still_get_a_verdict_but_the_run_reports_failure(app, capsys):
    assert app.start(["--all-samples", "--demo"]) == 1          # the forecast could not run
    out = capsys.readouterr().out
    assert "The forecast could not be completed and is left out" in out
    assert len(app.assessments().load()) == 2


def test_a_case_file_that_is_missing_is_reported_not_crashed(app, tmp_path, capsys):
    assert app.start(["--case", str(tmp_path / "nowhere.json")]) == 1
    assert "the case must be a JSON object" in capsys.readouterr().out


def test_a_damaged_case_file_is_reported_not_crashed(app, tmp_path, capsys):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert app.start(["--case", str(path)]) == 1


def test_case_needs_a_file_path(app, capsys):
    assert app.start(["--case"]) == 1
    assert "--case needs a file path" in capsys.readouterr().out


def test_a_step_that_fails_is_left_out_and_the_assessment_carries_on(app, capsys):
    case = sample_case()
    fake_services.save_forecast_replies(app.response_cache(), case)
    result = app.assess(case)                        # no AI: research, typologies and benchmark all fail
    assert result is not None
    assert "The peer benchmark" in result["verdict"]["not_run"]
    assert "could not be completed and is left out" in capsys.readouterr().out
    assert result["verdict"]["verdict"] != "PASSED"


def test_a_critical_step_that_fails_stops_the_assessment(app, capsys):
    case = sample_case()
    seen = []

    def on_failure(step: str, reason: str) -> bool:
        seen.append(step)
        return step not in App.CRITICAL_STEPS

    assert App.CRITICAL_STEPS == ("Deciding the verdict",)
    assert app.assess(case, on_failure=on_failure) is not None       # only ordinary steps failed
    assert "Deciding the verdict" not in seen


def test_saving_an_assessment_writes_the_outcome_onto_the_client_record(app):
    record = sample_case()
    app.clients().save(record)
    case, missing = app.read_case(record)
    assert missing == []
    fake_services.save_forecast_replies(app.response_cache(), case)
    result = app.assess(case)
    assessment_id = app.save_assessment(result, record)
    saved_record = app.clients().find(record["client_ref"])
    assert saved_record["outcome"] == result["verdict"]["verdict"]
    assert saved_record["routing"] == result["verdict"]["next_step"]
    assert saved_record["next_review_date"] == result["verdict"]["next_review_date"]
    saved = app.assessments().find(assessment_id)
    assert saved["client_ref"] == record["client_ref"]
    assert saved["report"] == result["report"]

def test_a_saved_assessment_keeps_the_client_info_it_was_based_on(app):
    record = sample_case()
    app.clients().save(record)
    case, _ = app.read_case(record)
    fake_services.save_forecast_replies(app.response_cache(), case)
    result = app.assess(case)
    assessment_id = app.save_assessment(result, record)
    assert app.assessments().find(assessment_id)["case"] == json.loads(json.dumps(case))
    app.clients().save({**record, "name": "Renamed Client"})
    assert app.assessments().find(assessment_id)["case"]["name"] == record["name"]

def test_the_menu_can_list_clients_and_leave(app, monkeypatch, capsys):
    app.clients().save(sample_case())
    _answers(monkeypatch, "6", "", "8")
    app.run_menu()
    out = capsys.readouterr().out
    assert sample_case()["client_ref"] in out
    assert "Goodbye." in out


def test_an_invalid_menu_choice_is_asked_again(app, monkeypatch, capsys):
    _answers(monkeypatch, "99", "abc", "8")
    app.run_menu()
    assert "Goodbye." in capsys.readouterr().out


def test_syncing_with_no_database_reports_it_and_keeps_the_local_data(app):
    app.clients().save(sample_case())
    stats = app.sync_to_cloud()
    assert stats["cases_synced"] == 0
    assert "Cannot reach the cloud database" in stats["errors"][0]
    assert len(app.clients().load()) == 1


def test_recorded_replies_never_overwrite_replies_already_saved(app):
    case = sample_case()
    fake_services.save_forecast_replies(app.response_cache(), case)
    before = app.response_cache().load_raw_replies(case["client_ref"])
    app.use_recorded_replies()
    assert app.response_cache().load_raw_replies(case["client_ref"]) == before
