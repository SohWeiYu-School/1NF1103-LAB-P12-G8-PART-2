"""App: the whole system put together. The AI is a made-up caller or the recorded replies; no network."""

import json
import os

import pytest

from app.application.app import App
from app.application.assessment_runner import AssessmentRunner
from app.model.client_record import ClientRecord
from app.model.match_result import MatchResult
from tests import fake_ai, fake_services
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


def test_every_assessment_is_dated_today_without_an_app():
    """today() reads no App state, so it is a static method: the same date for every App."""
    import datetime
    assert App.today() == datetime.date.today().isoformat()


def test_the_document_reader_is_ready_as_soon_as_the_app_is_built(app):
    """App creates its DocumentAI in __init__, so documents can be read before any assessment."""
    assert app.read_documents([]) == (None, [])
    assert app.read_documents([{"kind": "error", "error": "scan.pdf could not be opened."}]) == \
        (None, ["scan.pdf could not be opened."])


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


def test_a_new_client_reference_is_checked_against_the_saved_clients(app, tmp_path):
    saved = {**sample_case(), "client_ref": "CL-TAKEN001"}
    app.clients().save(saved)
    assert app.client_ref_taken("CL-TAKEN001") is True
    assert app.client_ref_taken("cl-taken001") is True          # upper and lower case are the same reference
    assert app.client_ref_taken("CL-FREE0001") is False
    assert app.new_client_ref().startswith("CL-")


def test_a_client_file_that_cannot_be_read_is_an_error_not_a_free_reference(app, tmp_path, caplog):
    _damage(tmp_path, "sow_cases.json")
    with pytest.raises(ValueError) as error:
        app.client_ref_taken("CL-ANYTHING")
    assert str(error.value) == App.CLIENTS_UNAVAILABLE
    with pytest.raises(ValueError):
        app.new_client_ref()
    assert "App.client_ref_taken" in caplog.text


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
    assert "The peer benchmark" in result["verdict"].not_run
    assert "could not be completed and is left out" in capsys.readouterr().out
    assert result["verdict"].outcome != "PASSED"


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
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    case, missing = app.read_case(record)
    assert missing == []
    fake_services.save_forecast_replies(app.response_cache(), case)
    result = app.assess(case)
    verdict = result["verdict"]
    assessment_id = app.save_assessment(result, record)
    assert record.review_status.outcome == verdict.outcome     # the record passed in is updated
    saved_record = app.clients().find(record.client_ref)
    assert saved_record["outcome"] == verdict.outcome
    assert saved_record["routing"] == verdict.next_step
    assert saved_record["next_review_date"] == verdict.next_review_date
    assert saved_record["last_assessed_on"] == case["current_date"]     # the case's date, not a timestamp
    saved = app.assessments().find(assessment_id)
    assert saved["client_ref"] == record.client_ref
    assert saved["report"] == verdict.report


def test_a_failed_assessment_save_leaves_the_client_record_as_it_was(app, tmp_path):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    before = app.clients().find(record.client_ref)
    case, _ = app.read_case(record)
    fake_services.save_forecast_replies(app.response_cache(), case)
    result = app.assess(case)
    path = tmp_path / "local database" / "ai_assessments.json"
    path.write_bytes(b"[{broken")                       # the saved assessments cannot be read
    assert app.save_assessment(result, record) is None
    assert app.clients().find(record.client_ref) == before      # no outcome without a saved assessment
    assert record.review_status.outcome == ClientRecord.from_dict(before).review_status.outcome
    assert path.read_bytes() == b"[{broken"


def test_the_saved_assessment_keeps_its_layout(app):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    case, _ = app.read_case(record)
    fake_services.save_forecast_replies(app.response_cache(), case)
    result = app.assess(case)
    verdict = result["verdict"]
    assessment_id = app.save_assessment(result, record)
    saved = app.assessments().find(assessment_id)
    assert assessment_id == verdict.assessment_id
    assert list(saved) == ["assessment_id", "client_ref", "kind", "assessed_at", "outcome", "verdict", "report",
                           "crime_scan", "crime_result", "benchmark", "document_evidence", "forecast", "assessment"]
    assert (saved["client_ref"], saved["kind"], saved["assessed_at"], saved["outcome"]) == (
        verdict.client_ref, "onboarding", verdict.assessed_at, verdict.outcome)
    assert saved["verdict"] == json.loads(json.dumps(verdict.details()))      # every check, reason and note
    assert list(saved["verdict"]) == list(verdict.details())
    assert saved["verdict"]["benchmark"] and saved["verdict"]["forecast"] and saved["verdict"]["reasons"]
    assert saved["forecast"] == saved["assessment"] == json.loads(json.dumps(result["forecast_assessment"]))
    assert saved["crime_scan"]["typologies"] == result["typology_response"]
    assert saved["document_evidence"] == json.loads(json.dumps(result["evidence"]))
    # the crime scan's reading of the declaration is saved as its rows, in the row layout
    assert saved["crime_scan"]["declaration"] == json.loads(json.dumps(result["crime_declaration"].to_scan_dict()))
    assert list(saved["crime_scan"]["declaration"]["sources"][0]) == [
        "source_id", "source_type", "description", "amount_sgd", "start_year", "end_year", "jurisdiction",
        "counterparty", "evidence_sentence", "occupation_mismatch", "amount_explained_by_forecast"]


def _saved_assessment(app) -> dict:
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    case, _ = app.read_case(record)
    fake_services.save_forecast_replies(app.response_cache(), case)
    result = app.assess(case)
    return app.assessments().find(app.save_assessment(result, record))


def test_a_saved_assessment_can_be_opened_from_the_list(app, monkeypatch, capsys):
    saved = _saved_assessment(app)
    capsys.readouterr()
    _answers(monkeypatch, "1", "y", "1", "y")         # every outcome, open one, the first, the evidence
    app.list_assessments()
    out = capsys.readouterr().out
    assert f"COMBINED ASSESSMENT  {saved['client_ref']}" in out
    assert saved["report"]["header"]["summary"][:40] in " ".join(out.split())
    assert "FULL EVIDENCE  " in out


def test_a_damaged_saved_assessment_is_reported_not_shown_or_crashed(app, tmp_path, monkeypatch, capsys, caplog):
    saved = _saved_assessment(app)
    records = app.assessments().load()
    records[0]["outcome"] = "FINE"                    # not an outcome
    with open(tmp_path / "local database" / "ai_assessments.json", "w", encoding="utf-8") as handle:
        json.dump(records, handle)
    capsys.readouterr()
    _answers(monkeypatch, "1", "y", "1")
    app.list_assessments()
    out = capsys.readouterr().out
    assert "This saved assessment could not be read" in out
    assert "COMBINED ASSESSMENT" not in out
    assert saved["assessment_id"] in caplog.text and "FINE" in caplog.text


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


def _broken_record() -> dict:
    """A saved record with an impossible value: ClientRecord cannot be built from it."""
    record = sample_case()
    record["career"]["age"] = 5
    return record


def test_find_client_gives_the_saved_client_as_a_client_record(app):
    app.clients().save(sample_case())
    record = app.find_client(sample_case()["client_ref"].lower())
    assert isinstance(record, ClientRecord)
    assert record.client_ref == sample_case()["client_ref"]
    assert record.profile.name == sample_case()["name"]


def test_find_client_gives_none_when_no_client_has_the_reference(app):
    assert app.find_client("CL-NOBODY") is None


def test_a_saved_client_that_cannot_be_read_is_reported_not_treated_as_missing(app, caplog):
    app.clients().save(_broken_record())
    with pytest.raises(ValueError) as error:
        app.find_client(sample_case()["client_ref"])
    assert "could not be loaded" in str(error.value) and "age must be between 18 and 120" in str(error.value)
    assert "App.find_client" in caplog.text                     # the real error is logged


def test_save_client_saves_the_record_in_the_saved_layout(app):
    record = ClientRecord.from_dict(sample_case())
    assert app.save_client(record) is True
    saved = app.clients().find(record.client_ref)
    assert saved == record.to_dict()
    assert app.find_client(record.client_ref).to_dict() == saved


def test_save_client_reports_a_record_that_could_not_be_saved(app, monkeypatch):
    monkeypatch.setattr(app.clients(), "save", lambda data: False)
    assert app.save_client(ClientRecord.from_dict(sample_case())) is False


def test_the_menu_reports_a_client_that_cannot_be_read_and_carries_on(app, monkeypatch, capsys):
    app.clients().save(_broken_record())
    _answers(monkeypatch, "4", sample_case()["client_ref"], "8")
    app.run_menu()
    out = capsys.readouterr().out
    assert "could not be loaded" in out
    assert "No client found" not in out                         # broken is not the same as missing
    assert "Goodbye." in out


def test_a_new_client_is_made_from_a_folder_of_documents(tmp_path, monkeypatch, capsys):
    """Menu option 2: the AI reads the folder, the officer fills the one gap and saves."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setattr("app.interface.client_form.tk", None)          # no file explorer window
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "marcus_lim")
    with open(folder + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    app = App(fake_ai.caller(documents_reply=reading), data_folder=str(tmp_path))
    #       menu  folder  income of asset 3  save  back to the menu  leave
    _answers(monkeypatch, "2", folder, "0", "1", "3", "8")
    app.run_menu()
    assert "Client saved. Reference: CL-" in capsys.readouterr().out
    saved = app.clients().load()
    assert len(saved) == 1
    record = app.find_client(saved[0]["client_ref"])
    assert record.profile.name == reading["client"]["name"]
    assert record.investments()[2].income_produced == 0
    assert len(record.documents()) == len(os.listdir(folder))


def test_an_impossible_value_in_the_reading_is_left_empty_named_and_asked_for_while_good_fields_are_kept(
        tmp_path, monkeypatch, capsys, caplog):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setattr("app.interface.client_form.tk", None)
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "marcus_lim")
    with open(folder + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    reading["client"].update(age=200, date_of_birth=None)
    app = App(fake_ai.caller(documents_reply=reading), data_folder=str(tmp_path))
    #       menu  folder  age (asked for)  income of asset 3  save  back to the menu  leave
    _answers(monkeypatch, "2", folder, "45", "0", "1", "3", "8")
    app.run_menu()
    out = capsys.readouterr().out
    assert "Age: the value read from the documents (200) is not possible" in out
    assert "so it was left empty. Please enter it." in out
    assert "cannot be used" not in out                        # the whole reading was not thrown away
    assert "left out of the AI's reading" in caplog.text      # the details are logged
    saved = app.find_client(app.clients().load()[0]["client_ref"])
    assert saved.profile.name == reading["client"]["name"] and saved.profile.age == 45


def _documents_with_a_bad_end_year(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setattr("app.interface.client_form.tk", None)
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "marcus_lim")
    with open(folder + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    reading["jobs"][0]["end_year"] = 2200                      # a past job the AI read as ending in 2200
    return App(fake_ai.caller(documents_reply=reading), data_folder=str(tmp_path)), folder


def test_a_dropped_optional_end_year_is_asked_for_and_the_answer_is_kept(tmp_path, monkeypatch, capsys):
    app, folder = _documents_with_a_bad_end_year(tmp_path, monkeypatch)
    #       menu  folder  income of asset 3  end year of job 1  save  back  leave
    _answers(monkeypatch, "2", folder, "0", "2003", "1", "3", "8")
    app.run_menu()
    out = capsys.readouterr().out
    assert "end year: the value read from the documents (2200) is not possible" in out
    assert "(2001-present)" in out and "blank = current job" in out         # the prompt says what blank means
    # the officer sees the dropped details before being asked for anything
    assert out.index("left empty") < out.index("required detail(s) weren't") < out.index("optional detail(s)")
    saved = app.clients().load()[0]
    assert saved["career_history"][0]["end_year"] == 2003
    assert sum(job["end_year"] is None for job in saved["career_history"]) == 1


def test_enter_on_a_dropped_optional_field_leaves_it_empty_and_does_not_block_saving(tmp_path, monkeypatch, capsys):
    app, folder = _documents_with_a_bad_end_year(tmp_path, monkeypatch)
    _answers(monkeypatch, "2", folder, "0", "", "1", "3", "8")
    app.run_menu()
    assert "Client saved. Reference: CL-" in capsys.readouterr().out
    assert app.clients().load()[0]["career_history"][0]["end_year"] is None


def test_the_crime_result_is_saved_in_the_match_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(fake_ai.caller(), data_folder=str(tmp_path))
    record = ClientRecord.from_dict(sample_case())
    application.save_client(record)
    case, _ = application.read_case(record)
    fake_services.save_forecast_replies(application.response_cache(), case)
    result = application.assess(case)
    matches = result["crime_result"]["match_results"]
    assert matches and all(isinstance(match, MatchResult) for match in matches)       # objects in the middle
    saved = application.assessments().find(application.save_assessment(result, record))
    assert saved["crime_result"] == {**result["crime_result"], "match_results": [m.to_dict() for m in matches]}
    assert list(saved["crime_result"]["match_results"][0]) == [
        "typology_id", "name", "source_ids", "breached", "category", "core_indicators", "core_fired",
        "supporting_indicators", "supporting_fired", "typical_documents"]
    assert saved["crime_scan"]["typologies"] == result["typology_response"]           # the reply, as it came


def test_a_bad_rate_limit_setting_is_reported_at_start_not_crashed(tmp_path, monkeypatch, capsys):
    """App must not crash while it is built; start() reports the setting and stops."""
    import shutil
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    root = tmp_path / "root"
    shutil.copytree("config", root / "config")
    policy = json.loads((root / "config" / "policy.json").read_text())
    policy["assessment_rate_limit"] = {"enabled": True, "cooldown_seconds": 60.5}
    (root / "config" / "policy.json").write_text(json.dumps(policy))
    application = App(ai_caller=None, root=str(root), data_folder=str(tmp_path / "data"))
    assert application.start(["--web"]) == 1                 # the web app is not started either
    assert "cooldown_seconds" in capsys.readouterr().out


@pytest.mark.parametrize("damage", ["missing", "damaged", "not_an_object"])
@pytest.mark.parametrize("start", [["--web"], []])
def test_unreadable_settings_stop_the_app_with_a_message_and_nothing_runs(tmp_path, monkeypatch, capsys,
                                                                          damage, start):
    import shutil
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    root = tmp_path / "root"
    shutil.copytree("config", root / "config")
    policy = root / "config" / "policy.json"
    if damage == "missing":
        policy.unlink()
    else:
        policy.write_text("{broken" if damage == "damaged" else "[1, 2]")
    application = App(ai_caller=None, root=str(root), data_folder=str(tmp_path / "data"))   # no crash
    assert application.start(start) == 1
    out = capsys.readouterr().out
    assert App.SETTINGS_UNAVAILABLE in out
    assert "Traceback" not in out and "policy.json" not in out         # technical details stay in the log


def test_client_assessments_gives_one_clients_assessments_newest_first(app):
    older = {"assessment_id": "A1", "client_ref": "C-1", "assessed_at": "2025-01-01T00:00:00+00:00"}
    newer = {"assessment_id": "A2", "client_ref": "C-1", "assessed_at": "2025-06-01T00:00:00+00:00"}
    other = {"assessment_id": "A3", "client_ref": "C-2", "assessed_at": "2025-03-01T00:00:00+00:00"}
    for saved in (older, newer, other):
        assert app.assessments().save(saved)
    assert app.client_assessments("C-1") == [newer, older]
    assert app.client_assessments("C-9") == []


def test_client_assessments_passes_on_an_error_from_the_repository(app, monkeypatch):
    def broken(client_ref):
        raise OSError("disk problem")
    monkeypatch.setattr(app.assessments(), "for_client", broken)
    with pytest.raises(OSError):
        app.client_assessments("C-1")


def test_find_assessment_gives_the_saved_assessment_or_none(app):
    saved = {"assessment_id": "A1", "client_ref": "C-1", "assessed_at": "2025-01-01T00:00:00+00:00"}
    assert app.assessments().save(saved)
    assert app.find_assessment("A1") == saved
    assert app.find_assessment("missing") is None


def test_upload_and_download_document_round_trip_a_file(app, tmp_path):
    source = tmp_path / "payslip.txt"
    source.write_text("salary 5000", encoding="utf-8")
    file_id = app.upload_document(str(source))
    assert file_id is not None and file_id.endswith("payslip.txt")
    target = tmp_path / "copy" / "payslip.txt"
    assert app.download_document(file_id, str(target)) is True
    assert target.read_text(encoding="utf-8") == "salary 5000"


def test_upload_document_gives_none_for_a_file_that_does_not_exist(app, tmp_path):
    assert app.upload_document(str(tmp_path / "missing.pdf")) is None


def test_download_document_gives_false_for_an_unknown_document(app, tmp_path):
    assert app.download_document("data/documents/nothing.pdf", str(tmp_path / "out.pdf")) is False


# ----- a read failure is reported, never shown as "no records" ------------------------------------

def _damage(tmp_path, name):
    path = tmp_path / "local database" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"[{broken")
    return path


def test_the_menu_tells_the_user_when_the_client_database_cannot_be_read(app, tmp_path, monkeypatch, capsys, caplog):
    path = _damage(tmp_path, "sow_cases.json")
    _answers(monkeypatch, "6", "8")
    app.run_menu()
    out = capsys.readouterr().out
    assert App.CLIENTS_UNAVAILABLE in out
    assert "No clients saved yet" not in out
    assert "damaged" in caplog.text                               # the real details are logged
    assert "damaged" not in out and "JSONDecodeError" not in out  # and not shown
    assert path.read_bytes() == b"[{broken"


def test_the_menu_tells_the_user_when_the_saved_assessments_cannot_be_read(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "ai_assessments.json")
    _answers(monkeypatch, "5", "1", "8")
    app.run_menu()
    out = capsys.readouterr().out
    assert out.count(App.ASSESSMENTS_UNAVAILABLE) == 2           # at start-up, and when listing
    assert "saved assessment(s) loaded" not in out
    assert "No assessments" not in out


def test_find_client_raises_a_safe_message_when_the_database_cannot_be_read(app, tmp_path, caplog):
    _damage(tmp_path, "sow_cases.json")
    with pytest.raises(ValueError) as error:
        app.find_client("CL-1")
    assert str(error.value) == App.CLIENTS_UNAVAILABLE
    assert "App.find_client" in caplog.text


def test_menu_find_client_shows_the_message_not_no_client_found(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "sow_cases.json")
    _answers(monkeypatch, "4", "CL-1", "8")
    app.run_menu()
    out = capsys.readouterr().out
    assert App.CLIENTS_UNAVAILABLE in out and "No client found" not in out


def test_saving_a_client_into_a_damaged_file_fails_and_keeps_the_file(app, tmp_path):
    path = _damage(tmp_path, "sow_cases.json")
    assert app.save_client(ClientRecord.from_dict(sample_case())) is False
    assert path.read_bytes() == b"[{broken"


def test_the_web_facade_methods_raise_when_the_saved_assessments_cannot_be_read(app, tmp_path):
    _damage(tmp_path, "ai_assessments.json")
    with pytest.raises(ValueError):
        app.client_assessments("C-1")
    with pytest.raises(ValueError):
        app.find_assessment("A1")


def test_a_failed_local_read_is_a_failed_sync_through_the_app(app, tmp_path):
    _damage(tmp_path, "sow_cases.json")
    stats = app.sync_to_cloud()
    assert stats["cases_synced"] == 0 and stats["errors"]


def _app_with_damaged_policy(tmp_path, monkeypatch):
    import shutil
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    root = tmp_path / "root"
    shutil.copytree("config", root / "config")
    (root / "config" / "policy.json").write_text("{broken")
    return root


def test_a_damaged_policy_is_logged_to_the_log_file_not_shown_on_the_terminal(tmp_path, monkeypatch, capsys):
    import logging
    root = _app_with_damaged_policy(tmp_path, monkeypatch)
    root_logger = logging.getLogger()
    saved_handlers, saved_level = root_logger.handlers[:], root_logger.level
    root_logger.handlers = []                                  # a fresh process: nothing configured yet
    try:
        application = App(ai_caller=None, root=str(root), data_folder=str(tmp_path / "data"))
        assert application.start([]) == 1
        for handler in root_logger.handlers:
            handler.flush()
        log = (root / "logs" / "app.log").read_text(encoding="utf-8")
        assert len(root_logger.handlers) == 1                  # start() did not add a second handler
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers, root_logger.level = saved_handlers, saved_level
    shown = capsys.readouterr()
    assert App.SETTINGS_UNAVAILABLE in shown.out
    for text in (shown.out, shown.err):
        assert "policy.json" not in text and "JSONDecodeError" not in text and "Errno" not in text
    assert "policy.json" in log and "JSONDecodeError" in log          # the real error is in the log
    assert log.count("Config file") == 1                              # and written once


def test_an_app_with_broken_settings_says_so_and_refuses_to_assess(tmp_path, monkeypatch):
    root = _app_with_damaged_policy(tmp_path, monkeypatch)
    application = App(ai_caller=fake_ai.caller, root=str(root), data_folder=str(tmp_path / "data"))
    assert application.settings_ok() is False
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(sample_case()))
    with pytest.raises(RuntimeError, match="settings could not be loaded"):
        application.assess(sample_case())
    with pytest.raises(RuntimeError, match="settings could not be loaded"):
        application.run_case_file(str(case_path))
    with pytest.raises(RuntimeError, match="settings could not be loaded"):
        application.assess_client_record(ClientRecord.from_dict(sample_case()))


def test_an_app_with_good_settings_reports_settings_ok(app):
    assert app.settings_ok() is True


def test_typologies_checked_reads_the_could_not_run_section():
    research_failed = {"sections": [{"title": "Could not run",
                                     "items": [{"mark": "skip", "text": AssessmentRunner.RESEARCH_STEP, "sub": []}]}]}
    other_failed = {"sections": [{"title": "Could not run",
                                  "items": [{"mark": "skip", "text": "The forecast", "sub": []}]}]}
    assert App.typologies_checked(research_failed) is False
    assert App.typologies_checked(other_failed) is True
    assert App.typologies_checked({"sections": []}) is True and App.typologies_checked(None) is True


# ----- what the web app asks App for ---------------------------------------------------------

_READING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "marcus_lim_expected_extract.json")


def _reading():
    with open(_READING_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def test_the_app_says_which_document_references_it_made(app, tmp_path):
    source = tmp_path / "deed.txt"
    source.write_text("a deed", encoding="utf-8")
    file_id = app.upload_document(str(source))
    assert app.owns_document(file_id) is True
    assert app.owns_document("../../.env") is False
    assert app.owns_document("") is False


def test_a_document_is_read_for_extraction_and_an_unreadable_one_comes_back_as_an_error(app, tmp_path):
    good = tmp_path / "note.txt"
    good.write_text("Salary from DBS", encoding="utf-8")
    read = app.read_document_for_extraction(str(good), "note.txt")
    assert read["file_name"] == "note.txt" and read["kind"] != "error"
    odd = tmp_path / "data.xyz"
    odd.write_text("?", encoding="utf-8")
    bad = app.read_document_for_extraction(str(odd), "data.xyz")
    assert bad["kind"] == "error" and "can't be read" in bad["error"]


def test_all_clients_is_empty_when_there_are_none_and_lists_them_when_saved(app):
    assert app.all_clients() == []
    app.clients().save(sample_case())
    assert [client["client_ref"] for client in app.all_clients()] == [sample_case()["client_ref"]]


def test_all_clients_raises_the_safe_message_when_the_database_cannot_be_read(app, tmp_path, caplog):
    _damage(tmp_path, "sow_cases.json")
    with pytest.raises(ValueError) as error:
        app.all_clients()
    assert str(error.value) == App.CLIENTS_UNAVAILABLE
    assert "App.all_clients" in caplog.text


def test_all_assessments_is_empty_when_there_are_none(app):
    assert app.all_assessments() == []


def test_all_assessments_lists_the_saved_ones(app):
    saved = {"assessment_id": "A1", "client_ref": "C-1", "assessed_at": "2025-01-01T00:00:00+00:00"}
    assert app.assessments().save(saved)
    assert app.all_assessments() == [saved]


def test_all_assessments_raises_the_safe_message_when_they_cannot_be_read(app, tmp_path, caplog):
    _damage(tmp_path, "ai_assessments.json")
    with pytest.raises(ValueError) as error:
        app.all_assessments()
    assert str(error.value) == App.ASSESSMENTS_UNAVAILABLE
    assert "App.all_assessments" in caplog.text


def test_a_reading_becomes_a_record_and_the_fields_left_out_are_named(app):
    record, dropped = app.record_from_reading(_reading(), "2026-10-14")
    assert isinstance(record, ClientRecord)
    assert record.current_date == "2026-10-14" and dropped == []
    bad = {**_reading(), "client": {**_reading()["client"], "age": 12, "date_of_birth": None}}
    _, dropped = app.record_from_reading(bad, "2026-10-14")
    assert [entry["path"] for entry in dropped] == [["career", "age"]]


def test_a_reading_dated_with_a_bad_date_raises_value_error_saying_what_is_wrong(app):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        app.record_from_reading(_reading(), "14/10/2026")


def test_reading_problems_lists_things_worth_a_second_look(app):
    record, _ = app.record_from_reading(_reading(), "2026-10-14")
    problems = app.reading_problems(record, "2026-10-14")
    assert isinstance(problems, list) and all(isinstance(line, str) for line in problems)
    early = record.to_dict()
    early["career"]["career_start_year"] = 1900
    assert any("before age 14" in line for line in app.reading_problems(ClientRecord.from_dict(early), "2026-10-14"))


def test_a_rate_limit_setting_that_is_not_an_object_is_logged_with_its_value(tmp_path, monkeypatch, caplog):
    import shutil
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    root = tmp_path / "root"
    shutil.copytree("config", root / "config")
    policy = json.loads((root / "config" / "policy.json").read_text())
    policy["assessment_rate_limit"] = "30 seconds"
    (root / "config" / "policy.json").write_text(json.dumps(policy))
    application = App(ai_caller=None, root=str(root), data_folder=str(tmp_path / "data"))
    assert "'30 seconds'" in caplog.text and "assessment_rate_limit" in caplog.text
    assert application.rate_limiter() is not None


def test_find_client_hides_the_technical_text_of_a_badly_laid_out_record(app, caplog):
    assert app.clients().save({"client_ref": "CL-1", "claims": 5})
    with pytest.raises(ValueError) as error:
        app.find_client("CL-1")
    assert "not in the expected layout" in str(error.value)
    assert "attribute" not in str(error.value)                  # the technical details stay in the log
    assert "App.find_client" in caplog.text


def test_the_research_asks_with_the_callers_research_model(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    caller = fake_ai.caller()
    caller.search_model_name = lambda: "research-model"
    application = App(caller, data_folder=str(tmp_path))
    case = sample_case()
    fake_services.save_forecast_replies(application.response_cache(), case)
    assert application.assess(case) is not None
    models = {key: options.get("model") for key, options in caller.asked}
    assert models["reports"] == "research-model"                       # the web search
    assert models["sector_typologies"] == "fake-model"                 # everything else
    assert models["expected_wealth"] == "fake-model"
