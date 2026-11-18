"""App: the whole system put together. The AI is a made-up caller or saved sample replies; no network."""

import json
import os

import pytest

from app.application.app import App
from app.application.assessment_runner import AssessmentRunner
from app.logic.audit_insights import AuditInsights
from app.model.account import Account
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.client_record import ClientRecord
from app.model.match_result import MatchResult
from app.model.verdict import Verdict
from tests import fake_ai, fake_services
from tests.audit_files import break_audit, fix_audit
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
    assert app.start(["--all-samples"]) == 1          # the forecast could not run
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


def test_an_unknown_option_is_refused_with_the_allowed_ones(app, capsys):
    assert app.start(["--all-samples", "--demo"]) == 1
    out = capsys.readouterr().out
    assert "Unknown option --demo" in out and "--case FILE" in out
    assert app.assessments().load() == []                   # nothing was run


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
    assert list(saved) == ["assessment_id", "client_ref", "kind", "assessed_at", "outcome", "case", "verdict", "report",
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
    _answers(monkeypatch, "1", "1", "1", "y")         # every outcome, open one, the first, the evidence
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
    _answers(monkeypatch, "1", "1", "1")
    app.list_assessments()
    out = capsys.readouterr().out
    assert "This saved assessment could not be read" in out
    assert "COMBINED ASSESSMENT" not in out
    assert saved["assessment_id"] in caplog.text and "FINE" in caplog.text


def test_the_menu_can_list_clients_and_leave(app, monkeypatch, capsys):
    app.clients().save(sample_case())
    _answers(monkeypatch, "6", "", "0")
    app.run_menu()
    out = capsys.readouterr().out
    assert sample_case()["client_ref"] in out
    assert "Goodbye." in out


def test_the_client_list_in_the_menu_shows_each_clients_last_activity(app, monkeypatch, capsys):
    app.save_client(ClientRecord.from_dict(sample_case()), new_client=True)
    app.clients().save({**sample_case(), "client_ref": "CL-QUIET"})
    capsys.readouterr()
    _answers(monkeypatch, "6", "", "0")
    app.run_menu()
    out = capsys.readouterr().out
    assert "Last activity" in out
    ref = sample_case()["client_ref"]
    assert "Client created" in next(line for line in out.splitlines() if ref in line and "#" not in line)
    assert next(line for line in out.splitlines() if "CL-QUIET" in line).rstrip().endswith("—")


def test_an_unreadable_audit_log_still_shows_the_client_list_without_the_column_and_says_why(
        app, tmp_path, monkeypatch, capsys, caplog):
    app.clients().save(sample_case())
    _damage(tmp_path, "audit_log.json")
    capsys.readouterr()
    _answers(monkeypatch, "6", "", "0")
    app.run_menu()
    out = capsys.readouterr().out
    assert sample_case()["client_ref"] in out
    assert App.AUDIT_UNAVAILABLE in out
    assert "Last activity" not in out and "No activity" not in out
    assert f"{App.AUDIT_UNAVAILABLE} The last activity of each client cannot be shown." in out
    assert "the audit log cannot be read" in caplog.text


def test_an_invalid_menu_choice_is_asked_again(app, monkeypatch, capsys):
    _answers(monkeypatch, "99", "abc", "0")
    app.run_menu()
    assert "Goodbye." in capsys.readouterr().out


def test_syncing_with_no_database_reports_it_and_keeps_the_local_data(app):
    app.clients().save(sample_case())
    stats = app.sync_to_cloud()
    assert stats["cases_synced"] == 0
    assert "Cannot reach the cloud database" in stats["errors"][0]
    assert len(app.clients().load()) == 1


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
    _answers(monkeypatch, "4", sample_case()["client_ref"], "0")
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
    _answers(monkeypatch, "2", folder, "0", "1", "3", "0")
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
    _answers(monkeypatch, "2", folder, "45", "0", "1", "3", "0")
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
    _answers(monkeypatch, "2", folder, "0", "2003", "1", "3", "0")
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
    _answers(monkeypatch, "2", folder, "0", "", "1", "3", "0")
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
    def broken(client_ref, include_archived=False):
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
    _answers(monkeypatch, "6", "0")
    app.run_menu()
    out = capsys.readouterr().out
    assert App.CLIENTS_UNAVAILABLE in out
    assert "No clients saved yet" not in out
    assert "damaged" in caplog.text                               # the real details are logged
    assert "damaged" not in out and "JSONDecodeError" not in out  # and not shown
    assert path.read_bytes() == b"[{broken"


def test_the_menu_tells_the_user_when_the_saved_assessments_cannot_be_read(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "ai_assessments.json")
    _answers(monkeypatch, "5", "1", "0")
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
    _answers(monkeypatch, "4", "CL-1", "0")
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


def test_the_log_file_starts_a_new_file_when_full_and_keeps_three_old_ones(tmp_path, monkeypatch):
    import logging
    root = _app_with_damaged_policy(tmp_path, monkeypatch)
    root_logger = logging.getLogger()
    saved_handlers, saved_level = root_logger.handlers[:], root_logger.level
    root_logger.handlers = []                                  # a fresh process: nothing configured yet
    try:
        App(ai_caller=None, root=str(root), data_folder=str(tmp_path / "data"))
        handler = root_logger.handlers[0]
        assert (handler.maxBytes, handler.backupCount) == (App.LOG_MAX_BYTES, App.LOG_BACKUPS) == (5 * 1024 * 1024, 3)
        for _ in range(App.LOG_BACKUPS + 2):                   # fill it up more often than files are kept
            handler.doRollover()
            logging.getLogger("test").warning("a line after a new file was started")
        handler.flush()
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers, root_logger.level = saved_handlers, saved_level
    files = sorted(path.name for path in (root / "logs").iterdir())
    assert files == ["app.log", "app.log.1", "app.log.2", "app.log.3"]          # the oldest ones were deleted
    assert "a line after a new file" in (root / "logs" / "app.log").read_text(encoding="utf-8")


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


# ----- the client snapshot, archive and restore ---------------------------------------------

def test_the_saved_assessment_keeps_a_copy_of_the_client_as_assessed(app):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    case, _ = app.read_case(record)
    fake_services.save_forecast_replies(app.response_cache(), case)
    result = app.assess(case)
    saved = app.assessments().find(app.save_assessment(result, record))
    assert saved["case"] == json.loads(json.dumps(result["case"]))


def _two_saved(app):
    for number in (1, 2):
        assert app.assessments().save({"assessment_id": f"A{number}", "client_ref": "C-1", "kind": "onboarding",
                                       "assessed_at": f"2025-0{number}-01T00:00:00+00:00", "outcome": "PASSED"})


def test_archive_and_restore_hide_and_show_an_assessment_in_the_lists(app):
    _two_saved(app)
    assert app.archive_assessment("A1") == App.ARCHIVE_CHANGED
    assert [a["assessment_id"] for a in app.client_assessments("C-1")] == ["A2"]
    assert [a["assessment_id"] for a in app.client_assessments("C-1", include_archived=True)] == ["A2", "A1"]
    assert [a["assessment_id"] for a in app.all_assessments()] == ["A2"]
    assert len(app.all_assessments(include_archived=True)) == 2
    assert App.archive_state(app.find_assessment("A1")) == App.ARCHIVE_ARCHIVED
    assert app.restore_assessment("A1") == App.ARCHIVE_CHANGED
    assert App.archive_state(app.find_assessment("A1")) == App.ARCHIVE_ACTIVE
    assert len(app.all_assessments()) == 2


def test_archive_saves_the_reason_and_refuses_a_bad_one_without_archiving(app):
    _two_saved(app)
    assert app.archive_assessment("A1", "x" * (App.MAX_ARCHIVE_REASON + 1)) == App.ARCHIVE_BAD_REASON
    assert app.archive_assessment("A1", "two\nlines") == App.ARCHIVE_BAD_REASON
    assert "archive_log" not in app.find_assessment("A1")
    assert "at most 200 characters" in App.archive_reason_problem("x" * 201)
    assert App.archive_reason_problem("typed the wrong net worth") == ""
    assert app.archive_assessment("A1", "  typed the wrong net worth  ") == App.ARCHIVE_CHANGED
    assert app.find_assessment("A1")["archive_log"][-1]["reason"] == "typed the wrong net worth"


def test_archive_and_restore_report_every_other_result(app):
    _two_saved(app)
    assert app.restore_assessment("A1") == App.ARCHIVE_NO_CHANGE
    assert app.archive_assessment("nope") == App.ARCHIVE_NOT_FOUND
    app.archive_assessment("A1")
    assert app.archive_assessment("A1") == App.ARCHIVE_NO_CHANGE


def test_archive_state_tells_a_damaged_log_apart():
    assert App.archive_state({"archive_log": "text"}) == App.ARCHIVE_UNREADABLE
    assert App.archive_state({}) == App.ARCHIVE_ACTIVE


def test_archiving_does_not_touch_the_client_record(app):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    before = app.clients().find(record.client_ref)
    assert app.assessments().save({"assessment_id": "A1", "client_ref": record.client_ref})
    app.archive_assessment("A1")
    assert app.clients().find(record.client_ref) == before


def test_archive_and_restore_raise_the_safe_message_when_they_cannot_read(app, tmp_path, caplog):
    _damage(tmp_path, "ai_assessments.json")
    for action in (app.archive_assessment, app.restore_assessment):
        with pytest.raises(ValueError) as error:
            action("A1")
        assert str(error.value) == App.ASSESSMENTS_UNAVAILABLE
    assert "App.archive_assessment" in caplog.text and "App.restore_assessment" in caplog.text


def test_the_menu_can_list_archived_assessments_too_and_marks_them(app, monkeypatch, capsys):
    _two_saved(app)
    app.archive_assessment("A1")
    app.assessments().save({"assessment_id": "A3", "client_ref": "C-3", "kind": "onboarding",
                            "archive_log": "broken", "outcome": "PASSED"})
    capsys.readouterr()
    _answers(monkeypatch, "1", "0")                   # every outcome: archived and damaged ones are hidden
    app.list_assessments()
    out = capsys.readouterr().out
    assert "(archived)" not in out and "unreadable" not in out and "C-3" not in out
    _answers(monkeypatch, str(len(Verdict.OUTCOMES) + 2), "0")     # the last option
    app.list_assessments()
    out = capsys.readouterr().out
    assert out.count("(archived)") == 1 and out.count("(archive state unreadable)") == 1 and "C-3" in out


@pytest.mark.parametrize("damage", ["missing", "damaged", "bad_entry", "not_a_list"])
def test_a_bad_accounts_file_stops_the_app_like_a_bad_policy_file(tmp_path, monkeypatch, capsys, damage):
    import shutil
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    root = tmp_path / "root"
    shutil.copytree("config", root / "config")
    accounts = root / "config" / "accounts.json"
    if damage == "missing":
        accounts.unlink()
    else:
        accounts.write_text({"damaged": "{broken", "bad_entry": '{"accounts": [{"email": "x"}]}',
                             "not_a_list": '{"accounts": 5}'}[damage])
    application = App(ai_caller=None, root=str(root), data_folder=str(tmp_path / "data"))   # no crash
    assert application.start([]) == 1
    out = capsys.readouterr().out
    assert App.SETTINGS_UNAVAILABLE in out and "Traceback" not in out and "accounts.json" not in out


# ----- the audit log ------------------------------------------------------------------------

def _events(app, **filters) -> list[AuditEvent]:
    """Every audit event that matches, oldest first (the whole log unless filters narrow it)."""
    first = app.audit_log(AuditFilter("custom", sort="asc", **filters))      # a custom range with no dates is all dates
    events, page = first.events, 1
    while len(events) < first.total:
        page += 1
        events += app.audit_log(AuditFilter("custom", sort="asc", page=page, **filters)).events
    return events


def _actions(app) -> list[str]:
    return [event.action for event in _events(app)]


def _assessed(app, actor=App.TERMINAL):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record, actor)
    case, _ = app.read_case(record)
    fake_services.save_forecast_replies(app.response_cache(), case)
    return record, app.assess(case, actor=actor)


def test_a_new_client_is_recorded_as_created_by_the_actor(app):
    record = ClientRecord.from_dict(sample_case())
    assert app.save_client(record, "Shareen") is True
    [event] = _events(app)
    assert (event.action, event.actor, event.client_ref, event.result) == (
        "client_created", "Shareen", record.client_ref, "ok")
    assert event.is_sealed()


def test_the_terminal_is_the_default_actor(app):
    app.save_client(ClientRecord.from_dict(sample_case()))
    assert _events(app)[0].actor == App.TERMINAL == AuditEvent.TERMINAL


def test_an_edit_is_recorded_with_what_changed(app):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record, "Shareen")
    edited = ClientRecord.from_dict({**record.to_dict(), "name": "Someone Else"})
    assert app.save_client(edited, "Adrian") is True
    created, event = _events(app)
    assert event.action == "client_edited" and event.actor == "Adrian"
    assert event.details["changes"] == [{"field": "name", "before": sample_case()["name"], "after": "Someone Else"}]
    assert created.action == "client_created"


def test_saving_a_client_that_did_not_change_writes_nothing(app):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    assert app.save_client(ClientRecord.from_dict(record.to_dict())) is True
    assert _actions(app) == ["client_created"]


def test_a_client_that_could_not_be_saved_is_recorded_as_failed(app, monkeypatch):
    monkeypatch.setattr(app.clients(), "save", lambda data: False)
    assert app.save_client(ClientRecord.from_dict(sample_case()), "Shareen") is False
    [event] = _events(app)
    assert (event.action, event.result) == ("client_created", "failed")


def test_a_client_file_that_cannot_be_read_is_not_overwritten_and_is_recorded_as_failed(app, tmp_path):
    path = _damage(tmp_path, "sow_cases.json")
    assert app.save_client(ClientRecord.from_dict(sample_case()), "Shareen") is False
    assert path.read_bytes() == b"[{broken"
    [event] = _events(app)
    assert (event.action, event.result, event.details) == ("client_edited", "failed", {"changes": []})


def test_an_assessment_is_recorded_with_its_outcome_and_the_review_save_is_not_an_edit(app):
    record, result = _assessed(app, "Shareen")
    assessment_id = app.save_assessment(result, record, actor="Shareen")
    assert _actions(app) == ["client_created", "assessment_run"]       # no client_edited for the outcome
    event = _events(app)[1]
    verdict = result["verdict"]
    assert (event.actor, event.client_ref, event.result) == ("Shareen", record.client_ref, "ok")
    assert event.details["assessment_id"] == assessment_id == verdict.assessment_id
    assert event.details["outcome"] == verdict.outcome
    assert event.details["previous_outcome"] == ""
    assert event.details["not_run"] and set(event.details["not_run"]) == set(verdict.not_run)
    assert "Assessment saved for" in event.summary()


def test_a_second_assessment_records_the_previous_outcome(app):
    record, result = _assessed(app)
    app.save_assessment(result, record)
    first_outcome = record.review_status.outcome
    case, _ = app.read_case(record)
    app.save_assessment(app.assess(case), record)
    assert _events(app)[-1].details["previous_outcome"] == first_outcome != ""


def test_the_steps_that_did_not_run_are_listed_by_name_only(app):
    record, result = _assessed(app)          # no AI: research, typologies and benchmark did not run
    app.save_assessment(result, record)
    not_run = _events(app)[-1].details["not_run"]
    assert "The peer benchmark" in not_run and all(isinstance(name, str) for name in not_run)


def test_an_assessment_that_could_not_be_saved_is_recorded_as_failed(app, tmp_path):
    record, result = _assessed(app, "Shareen")
    _damage(tmp_path, "ai_assessments.json")
    assert app.save_assessment(result, record, actor="Shareen") is None
    event = _events(app)[-1]
    assert (event.action, event.result, event.actor) == ("assessment_failed", "failed", "Shareen")
    assert event.details["step"] == "Saving the assessment"
    assert "assessment_run" not in _actions(app)


def test_an_assessment_stopped_on_a_critical_step_is_recorded_as_failed_with_the_step_name(app):
    case = sample_case()
    assert app.assess(case, on_failure=lambda step, reason: False, show_failures=False, actor="Adrian") is None
    [event] = _events(app)
    assert (event.action, event.result, event.actor, event.client_ref) == (
        "assessment_failed", "failed", "Adrian", case["client_ref"])
    assert event.details["step"] == AssessmentRunner.RESEARCH_STEP       # the first step that failed (no AI)
    assert "could not be completed" in event.summary()


def test_an_assessment_that_carries_on_without_a_step_writes_no_failure_line(app):
    case = sample_case()
    fake_services.save_forecast_replies(app.response_cache(), case)
    assert app.assess(case) is not None
    assert _actions(app) == []


def test_archive_and_restore_are_recorded_with_who_why_and_which_assessment(app):
    _two_saved(app)
    assert app.archive_assessment("A1", "  duplicate ", "Shareen") == App.ARCHIVE_CHANGED
    assert app.restore_assessment("A1", "Adrian") == App.ARCHIVE_CHANGED
    archived, restored = _events(app)
    assert (archived.action, archived.actor, archived.client_ref) == ("assessment_archived", "Shareen", "C-1")
    assert archived.details == {"assessment_id": "A1", "outcome": "PASSED", "reason": "duplicate"}
    assert (restored.action, restored.actor) == ("assessment_restored", "Adrian")
    assert restored.details == {"assessment_id": "A1", "outcome": "PASSED"}
    log = app.find_assessment("A1")["archive_log"]
    assert [entry["by"] for entry in log] == ["Shareen", "Adrian"]


def test_archive_and_restore_that_change_nothing_write_no_line(app):
    _two_saved(app)
    app.restore_assessment("A1")                           # not archived
    app.archive_assessment("nope")                         # not found
    app.archive_assessment("A1", "two\nlines")             # bad reason
    app.archive_assessment("A1")
    app.archive_assessment("A1")                           # already archived
    assert _actions(app) == ["assessment_archived"]


def test_an_archive_that_could_not_be_saved_is_recorded_as_failed(app, monkeypatch):
    _two_saved(app)
    monkeypatch.setattr(app.assessments(), "_write_all", lambda records: False)
    assert app.archive_assessment("A1", "", "Shareen") == App.ARCHIVE_NOT_SAVED
    [event] = _events(app)
    assert (event.action, event.result) == ("assessment_archived", "failed")


def test_reading_documents_is_recorded_with_counts_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setattr("app.interface.client_form.tk", None)
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "marcus_lim")
    with open(folder + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    app = App(fake_ai.caller(documents_reply=reading), data_folder=str(tmp_path))
    names = sorted(os.listdir(folder))
    documents = [app.read_document_for_extraction(os.path.join(folder, name), name) for name in names]
    extracted, _ = app.read_documents(documents, "Shareen")
    assert extracted is not None
    [event] = _events(app)
    assert (event.action, event.actor, event.result) == ("autofill_used", "Shareen", "ok")
    assert event.details["documents"] == len(names) and event.details["fields"] > 5
    assert set(event.details) == {"documents", "fields"}


def test_reading_documents_for_auto_fill_always_asks_the_ai(tmp_path, monkeypatch):
    """Auto-fill gets no saved replies: the same documents are read by the AI every time, and nothing is
    saved for any client."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents",
                           "marcus_lim_expected_extract.json"), encoding="utf-8") as handle:
        reading = json.load(handle)
    caller = fake_ai.caller(documents_reply=reading)
    app = App(caller, data_folder=str(tmp_path))
    documents = [{"file_name": "cv.txt", "kind": "text", "text": "A CV"}]
    assert app.read_documents(documents)[0] is not None
    assert app.read_documents(documents)[0] is not None
    assert [key for key, _ in caller.asked] == ["jobs", "jobs"]
    assert not (tmp_path / "cache").exists()


def test_reading_documents_that_gave_nothing_is_recorded_as_failed_and_reading_none_writes_nothing(app):
    assert app.read_documents([]) == (None, [])
    assert _actions(app) == []
    app.read_documents([{"kind": "error", "error": "scan.pdf could not be opened."}], "Shareen")
    [event] = _events(app)
    assert (event.action, event.result, event.details) == ("autofill_used", "failed", {"documents": 1, "fields": 0})


def test_upload_and_download_are_recorded_with_the_file_id_only(app, tmp_path):
    source = tmp_path / "payslip.txt"
    source.write_text("salary 5000", encoding="utf-8")
    file_id = app.upload_document(str(source), "Shareen", "C-9")
    assert app.download_document(file_id, str(tmp_path / "out" / "payslip.txt"), "Adrian", "C-9") is True
    uploaded, downloaded = _events(app)
    assert (uploaded.action, uploaded.actor, uploaded.client_ref, uploaded.details) == (
        "document_uploaded", "Shareen", "C-9", {"file_id": file_id})
    assert (downloaded.action, downloaded.actor, downloaded.details) == (
        "document_downloaded", "Adrian", {"file_id": file_id})
    assert [event.action for event in app.audit_trail("c-9")[0]] == ["document_downloaded", "document_uploaded"]


def test_a_document_that_could_not_be_kept_or_copied_is_recorded_as_failed(app, tmp_path):
    assert app.upload_document(str(tmp_path / "missing.pdf")) is None
    assert app.download_document("data/documents/nothing.pdf", str(tmp_path / "out.pdf")) is False
    assert [(event.action, event.result) for event in _events(app)] == [
        ("document_uploaded", "failed"), ("document_downloaded", "failed")]


def test_a_cloud_sync_is_recorded_with_counts_and_never_the_error_text(app):
    app.clients().save(sample_case())
    stats = app.sync_to_cloud("Shareen")
    assert stats["errors"]
    [event] = _events(app)
    assert (event.action, event.actor, event.result) == ("cloud_sync", "Shareen", "failed")
    assert event.details == {"synced": 0, "skipped": stats["skipped"], "errors": len(stats["errors"])}
    assert stats["errors"][0] not in json.dumps(event.to_dict())


def test_signing_in_and_out_are_recorded_under_the_account_name(app):
    account, problem = app.sign_in("  shareen ", "officer123", App.OFFICER_PORTAL)
    assert account is not None and account.name == "Shareen" and problem == ""
    app.sign_out(account)
    assert [(event.action, event.actor) for event in _events(app)] == [
        ("signed_in", "Shareen"), ("signed_out", "Shareen")]


def test_the_name_is_matched_ignoring_case_and_extra_spaces(app):
    assert app.sign_in("WEI   yu", "officer123", App.OFFICER_PORTAL)[0].name == "Wei Yu"
    assert app.sign_in(" orbit  admin", "admin123", App.ADMIN_PORTAL)[0].name == "Orbit Admin"


def test_nothing_typed_is_refused_and_writes_nothing(app):
    for name, password in (("", "officer123"), ("Shareen", ""), ("  ", " "), (None, None)):
        assert app.sign_in(name, password, App.OFFICER_PORTAL) == (None, App.SIGN_IN_EMPTY)
    assert _actions(app) == []


def test_a_wrong_password_is_recorded_under_the_account_without_the_password(app):
    assert app.sign_in("Shareen", "wrong-password-XYZ", App.OFFICER_PORTAL) == (None, App.SIGN_IN_WRONG)
    [event] = _events(app)
    assert (event.action, event.actor, event.result, event.details) == (
        "sign_in_failed", "Shareen", "failed", {"portal": "officer"})
    assert "wrong-password-XYZ" not in json.dumps(event.to_dict())


def test_an_unknown_name_is_recorded_as_the_unknown_actor_and_gets_the_same_message(app):
    assert app.sign_in("Nobody Here", "officer123", App.ADMIN_PORTAL) == (None, App.SIGN_IN_WRONG)
    [event] = _events(app)
    assert (event.actor, event.result, event.details) == ("unknown", "failed", {"portal": "admin"})
    assert app.sign_in("x" * 500, "y" * 500, App.OFFICER_PORTAL) == (None, App.SIGN_IN_WRONG)


def test_an_unknown_name_still_checks_a_password_so_the_reply_time_gives_nothing_away(app, monkeypatch):
    checked = []
    real = Account.check_password
    monkeypatch.setattr(Account, "check_password", lambda self, password: checked.append(password) or real(self, password))
    assert app.sign_in("Nobody Here", "officer123", App.OFFICER_PORTAL) == (None, App.SIGN_IN_WRONG)
    assert checked == ["officer123"]


def test_the_right_password_at_the_wrong_portal_says_where_to_sign_in_and_is_recorded(app):
    assert app.sign_in("Shareen", "officer123", App.ADMIN_PORTAL) == (None, App.SIGN_IN_OFFICER_AT_ADMIN)
    assert app.sign_in("Orbit Admin", "admin123", App.OFFICER_PORTAL) == (None, App.SIGN_IN_ADMIN_AT_OFFICER)
    assert [(event.actor, event.result, event.details["portal"]) for event in _events(app)] == [
        ("Shareen", "failed", "admin"), ("Orbit Admin", "failed", "officer")]
    # a wrong password never reveals which portal the account belongs to
    assert app.sign_in("Shareen", "nope", App.ADMIN_PORTAL)[1] == App.SIGN_IN_WRONG


def test_the_last_activity_of_each_client_comes_from_one_read_of_the_log(app):
    assert app.last_activity() == {}
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record, "Shareen")
    app.sign_in("Adrian", "officer123", App.OFFICER_PORTAL)         # no client: not counted
    changed = ClientRecord.from_dict({**sample_case(), "name": "Somebody Else"})
    app.save_client(changed, "Adrian")
    latest = app.last_activity()
    assert list(latest) == [record.client_ref.casefold()]
    assert (latest[record.client_ref.casefold()].actor, latest[record.client_ref.casefold()].action) == ("Adrian", "client_edited")


def test_the_last_activity_says_when_the_log_cannot_be_read(app, tmp_path):
    break_audit(tmp_path)
    with pytest.raises(ValueError, match="audit log"):
        app.last_activity()


def test_a_refusal_is_recorded_and_its_text_is_checked(app):
    app.refused("Shareen", "  opening the audit log ")
    [event] = _events(app)
    assert (event.action, event.actor, event.details) == ("access_refused", "Shareen", {"what": "opening the audit log"})
    for bad in ("", "  ", "two\nlines", "x" * (App.MAX_REFUSED_TEXT + 1), None):
        with pytest.raises(ValueError):
            app.refused("Shareen", bad)
    assert len(_events(app)) == 1


def test_an_unknown_actor_is_a_programming_error_and_nothing_happens(app, tmp_path):
    record = ClientRecord.from_dict(sample_case())
    source = tmp_path / "a.txt"
    source.write_text("x", encoding="utf-8")
    calls = [lambda actor: app.save_client(record, actor),
             lambda actor: app.assess(sample_case(), actor=actor),
             lambda actor: app.save_assessment({}, record, actor=actor),
             lambda actor: app.archive_assessment("A1", "", actor),
             lambda actor: app.restore_assessment("A1", actor),
             lambda actor: app.read_documents([], actor),
             lambda actor: app.upload_document(str(source), actor),
             lambda actor: app.download_document("x", str(tmp_path / "o"), actor),
             lambda actor: app.sync_to_cloud(actor),
             lambda actor: app.refused(actor, "x"),
             lambda actor: app.verify_audit_log(actor)]
    for call in calls:
        for bad in ("", "Mallory", "shareen", None, 5):
            with pytest.raises(ValueError):
                call(bad)
    assert app.clients().load() == [] and _events(app) == []


def test_an_audit_line_that_cannot_be_written_leaves_the_action_standing_and_is_flagged(app, tmp_path, caplog):
    break_audit(tmp_path)
    assert app.audit_write_failed() is False
    assert app.save_client(ClientRecord.from_dict(sample_case()), "Shareen") is True
    assert app.audit_write_failed() is True
    assert len(app.clients().load()) == 1
    assert "was not written" in caplog.text


def test_the_terminal_is_told_when_the_audit_line_was_not_written_but_the_web_is_not_printed_to(
        app, tmp_path, capsys):
    break_audit(tmp_path)
    app.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    assert capsys.readouterr().out == ""
    app.sync_to_cloud()                                  # the terminal: nothing was saved
    assert App.AUDIT_LINE_NOT_WRITTEN in capsys.readouterr().out


def test_the_audit_failure_flag_is_reset_by_the_next_action(app, tmp_path):
    break_audit(tmp_path)
    app.sync_to_cloud("Shareen")
    assert app.audit_write_failed() is True
    fix_audit(tmp_path)
    app.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    assert app.audit_write_failed() is False
    app.archive_assessment("nope", "", "Shareen")        # writes no line, so nothing can have failed
    assert app.audit_write_failed() is False


def test_an_audit_file_that_is_a_folder_does_not_stop_the_action(app, tmp_path, caplog):
    (tmp_path / "local database").mkdir(parents=True, exist_ok=True)
    (tmp_path / "local database" / "audit_log.json").mkdir()
    assert app.save_client(ClientRecord.from_dict(sample_case()), "Shareen") is True
    assert app.audit_write_failed() is True
    assert "audit" in caplog.text.lower()


def test_the_audit_flag_belongs_to_one_thread(app, tmp_path):
    import threading
    break_audit(tmp_path)
    app.sync_to_cloud("Shareen")
    seen = []
    thread = threading.Thread(target=lambda: seen.append(app.audit_write_failed()))
    thread.start()
    thread.join()
    assert seen == [False] and app.audit_write_failed() is True


def test_the_log_is_written_to_audit_log_json_next_to_the_other_stores(app, tmp_path):
    app.sync_to_cloud()
    assert (tmp_path / "local database" / "audit_log.json").exists()


def test_accounts_come_from_the_config(app):
    assert [account.name for account in app.accounts()][:2] == ["Orbit Admin", "Shareen"]
    assert app.account("Adrian@Orbit.local").name == "Adrian"
    assert app.account("nobody@example.com") is None
    app.accounts().clear()
    assert len(app.accounts()) == 6                      # a copy: the config is not changed


def test_the_log_gives_newest_first_with_the_total_and_applies_the_filter(app):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record, "Shareen")
    app.sign_in("Adrian", "officer123", App.OFFICER_PORTAL)
    app.sync_to_cloud("Shareen")
    log = app.audit_log(AuditFilter())
    assert log.total == 3 and [event.action for event in log.events] == ["cloud_sync", "signed_in", "client_created"]
    assert (log.officers, log.failed, log.everything) == (2, 1, 3)           # the sync failed: there is no cloud here
    log = app.audit_log(AuditFilter(actor="shareen"))
    assert log.total == 2 and {event.actor for event in log.events} == {"Shareen"} and log.officers == 1
    log = app.audit_log(AuditFilter(groups=["Sign-in"]))
    assert [event.action for event in log.events] == ["signed_in"] and log.total == 1
    assert app.audit_log(AuditFilter(client_ref=record.client_ref.lower())).total == 1
    assert app.audit_log(AuditFilter(result="failed")).total == 1 and app.audit_log(AuditFilter(query="nothing like this")).total == 0
    assert app.audit_log(AuditFilter(query="cloud")).total == 1


def test_a_filter_that_matches_nothing_still_says_how_much_the_whole_log_holds_from_the_same_read(app):
    app.sync_to_cloud("Shareen")
    app.sync_to_cloud("Shareen")
    log = app.audit_log(AuditFilter(client_ref="nobody"))
    assert (log.events, log.total, log.everything) == ([], 0, 2)


def test_the_log_uses_the_time_it_is_given_for_the_period(app):
    from datetime import datetime, timedelta, timezone
    app.sync_to_cloud()
    now = datetime.now(timezone.utc)
    assert app.audit_log(AuditFilter("1"), now).total == 1
    assert app.audit_log(AuditFilter("1"), now + timedelta(days=3)).total == 0
    assert app.audit_log(AuditFilter("custom"), now + timedelta(days=3)).total == 1


def test_an_empty_log_is_an_empty_page_not_an_error(app):
    log = app.audit_log(AuditFilter())
    assert (log.events, log.total, log.unreadable, log.everything) == ([], 0, 0, 0)
    assert app.audit_trail("C-1") == ([], 0)


def test_an_unreadable_audit_log_gives_the_safe_message_and_is_logged(app, tmp_path, caplog):
    _damage(tmp_path, "audit_log.json")
    for action in (lambda: app.audit_log(AuditFilter()), lambda: app.audit_trail("C-1"),
                   lambda: app.verify_audit_log("Orbit Admin")):
        with pytest.raises(ValueError) as error:
            action()
        assert str(error.value) == App.AUDIT_UNAVAILABLE
    assert "the audit log cannot be read" in caplog.text


def test_a_row_that_cannot_be_read_is_not_listed_but_is_logged(app, tmp_path, caplog):
    app.sync_to_cloud()
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(rows + [{"action": "bogus"}]), encoding="utf-8")
    assert app.audit_log(AuditFilter()).total == 1
    assert "cannot be read and are not listed" in caplog.text


def test_the_trail_of_one_client_is_newest_first(app):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record, "Shareen")
    app.save_client(ClientRecord.from_dict({**record.to_dict(), "name": "Someone Else"}), "Adrian")
    app.sync_to_cloud()
    assert [event.action for event in app.audit_trail(record.client_ref)[0]] == ["client_edited", "client_created"]


def test_verifying_an_untouched_log_passes_and_is_recorded(app):
    app.sync_to_cloud()
    app.sync_to_cloud()
    chain = app.verify_audit_log("Orbit Admin")
    assert chain.intact() and chain.summary() == "No changes found in the 2 entries."
    event = _events(app)[-1]
    assert (event.action, event.actor, event.result) == ("audit_verified", "Orbit Admin", "ok")
    assert event.details == {"entries": 2, "intact": True, "breaks": 0}


def test_verifying_a_changed_log_reports_the_break_and_records_it_as_failed(app, tmp_path):
    app.sync_to_cloud()
    app.sync_to_cloud()
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[0]["actor"] = "Someone Else"
    path.write_text(json.dumps(rows), encoding="utf-8")
    chain = app.verify_audit_log("Orbit Admin")
    assert not chain.intact() and "entry 1 does not match" in chain.summary()
    event = _events(app)[-1]
    assert (event.action, event.result, event.details["intact"]) == ("audit_verified", "failed", False)


def test_the_menu_flow_that_reads_documents_records_every_step(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setattr("app.interface.client_form.tk", None)
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "marcus_lim")
    with open(folder + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    app = App(fake_ai.caller(documents_reply=reading), data_folder=str(tmp_path))
    _answers(monkeypatch, "2", folder, "0", "1", "3", "0")
    app.run_menu()
    actions = _actions(app)
    assert actions[0] == "autofill_used" and actions[-1] == "client_created"
    assert actions.count("document_uploaded") == len(os.listdir(folder))
    assert {event.actor for event in _events(app)} == {App.TERMINAL}
    assert App.AUDIT_NOT_WRITTEN not in capsys.readouterr().out


def test_a_hand_added_row_without_a_time_or_id_is_not_listed_but_verify_reports_it(app, tmp_path, caplog):
    app.sync_to_cloud("Shareen")
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows.append({"action": "cloud_sync", "actor": "Shareen"})                       # unsealed: no at, no id
    rows.append({"action": "cloud_sync", "actor": "Shareen", "sequence": 3, "hash": "a" * 64,
                 "previous_hash": rows[0]["hash"]})                                  # sealed-looking, no at or id
    path.write_text(json.dumps(rows), encoding="utf-8")
    log = app.audit_log(AuditFilter())
    events, total = log.events, log.total
    assert total == 1 and [event.actor for event in events] == ["Shareen"]
    assert app.audit_trail("") == ([], 2)        # no client matches, but two rows are unreadable
    assert "2 audit row(s) cannot be read and are not listed" in caplog.text
    chain = app.verify_audit_log("Orbit Admin")
    assert not chain.intact() and len(chain.breaks()) >= 2


def test_a_run_that_raises_writes_a_failure_line_without_the_error_text_and_raises_again(app):
    with pytest.raises(Exception):
        app.assess({"client_ref": "C-1"}, show_failures=False, actor="Shareen")     # not a case the runner can read
    [event] = _events(app)
    assert (event.action, event.result, event.actor, event.client_ref) == (
        "assessment_failed", "failed", "Shareen", "C-1")
    assert event.details == {"step": App.UNEXPECTED_ERROR_STEP}


def test_a_save_that_raises_writes_a_failure_line_and_raises_again(app):
    record, result = _assessed(app, "Shareen")
    del result["research"]                                  # the saved layout needs it: the save raises KeyError
    with pytest.raises(KeyError):
        app.save_assessment(result, record, actor="Shareen")
    event = _events(app)[-1]
    assert (event.action, event.result, event.client_ref) == ("assessment_failed", "failed", record.client_ref)
    assert event.details == {"step": App.UNEXPECTED_ERROR_STEP}
    assert app.assessments().load() == []


def test_a_save_of_something_that_is_not_a_result_raises_and_is_recorded_without_a_client(app):
    with pytest.raises(KeyError):
        app.save_assessment({}, None, actor="Adrian")
    [event] = _events(app)
    assert (event.action, event.client_ref, event.actor) == ("assessment_failed", "", "Adrian")


def test_reading_documents_for_a_client_ties_the_line_to_that_client(app):
    app.read_documents([{"kind": "error", "error": "scan.pdf could not be opened."}], "Shareen", "C-7")
    [event] = _events(app)
    assert event.client_ref == "C-7"
    assert [e.action for e in app.audit_trail("C-7")[0]] == ["autofill_used"]


def test_a_new_client_that_could_not_be_saved_because_the_file_is_unreadable_is_recorded_as_created(app, tmp_path):
    _damage(tmp_path, "sow_cases.json")
    record = ClientRecord.from_dict(sample_case())
    assert app.save_client(record, "Shareen", new_client=True) is False
    assert app.save_client(record, "Shareen") is False
    first, second = _events(app)
    assert (first.action, first.result) == ("client_created", "failed")
    assert (second.action, second.result) == ("client_edited", "failed")


def test_an_assessment_saved_but_not_its_outcome_is_recorded_ok_with_record_saved_false(app, tmp_path, caplog):
    record, result = _assessed(app, "Shareen")
    _damage(tmp_path, "sow_cases.json")                     # the client record can no longer be written
    assessment_id = app.save_assessment(result, record, actor="Shareen")
    assert assessment_id is not None and app.client_outcome_failed() is True
    event = _events(app)[-1]
    assert (event.action, event.result) == ("assessment_run", "ok")
    assert event.details["record_saved"] is False and event.details["assessment_id"] == assessment_id
    assert "could not save the client record" in caplog.text
    app.save_client(ClientRecord.from_dict(sample_case()), "Shareen")       # the next action forgets it
    assert app.client_outcome_failed() is False


def test_an_assessment_with_its_outcome_saved_says_record_saved_true_and_one_with_no_record_says_nothing(app):
    record, result = _assessed(app)
    app.save_assessment(result, record)
    assert _events(app)[-1].details["record_saved"] is True and app.client_outcome_failed() is False
    case, _ = app.read_case(record)
    app.save_assessment(app.assess(case), None)
    assert "record_saved" not in _events(app)[-1].details


def test_the_terminal_is_told_when_the_outcome_could_not_be_written(app, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda question="": "n")        # the report asks about evidence
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    case, _ = app.read_case(record)
    fake_services.save_forecast_replies(app.response_cache(), case)
    _damage(tmp_path, "sow_cases.json")
    assert app.assess_client_record(record) is not None
    out = capsys.readouterr().out
    assert "Assessment saved." in out and App.OUTCOME_NOT_UPDATED in out


def test_the_terminal_message_says_saved_only_when_something_was_saved(app, tmp_path, capsys):
    break_audit(tmp_path)
    app.save_client(ClientRecord.from_dict(sample_case()))                    # saved: "Saved, but ..."
    out = capsys.readouterr().out
    assert App.AUDIT_NOT_WRITTEN in out
    app.refused("Shareen", "opening the audit log")                           # nothing saved
    app.sync_to_cloud()
    app.upload_document(str(tmp_path / "missing.pdf"))                         # not kept
    out = capsys.readouterr().out
    assert App.AUDIT_NOT_WRITTEN not in out and out.count(App.AUDIT_LINE_NOT_WRITTEN) == 2
    source = tmp_path / "a.txt"
    source.write_text("x", encoding="utf-8")
    assert app.upload_document(str(source)) is not None                       # kept
    assert App.AUDIT_NOT_WRITTEN in capsys.readouterr().out


def test_an_archive_that_changed_something_says_saved_and_one_that_changed_nothing_writes_no_line(app, tmp_path, capsys):
    _two_saved(app)
    break_audit(tmp_path)
    app.archive_assessment("A1")
    assert app.audit_write_failed() is True and App.AUDIT_NOT_WRITTEN in capsys.readouterr().out
    app.archive_assessment("A1")                                               # already archived: no line, no message
    assert app.audit_write_failed() is False and capsys.readouterr().out == ""


def test_without_an_audit_key_app_is_built_but_start_and_start_web_stop_with_a_message(tmp_path, monkeypatch, capsys,
                                                                                       caplog):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.delenv("AUDIT_KEY", raising=False)
    import shutil
    shutil.copytree("config", tmp_path / "root" / "config")      # a root with no .env, so no key is read from it
    application = App(ai_caller=None, root=str(tmp_path / "root"), data_folder=str(tmp_path / "data"))
    assert not application.audit_key_ok()
    for run in (lambda: application.start([]), lambda: application.start(["--web"]), application.start_web):
        assert run() == 1
        out = capsys.readouterr().out
        assert App.AUDIT_KEY_MISSING in out and "AUDIT_KEY" not in out
    assert "AUDIT_KEY" in caplog.text                         # the real reason is logged
    with pytest.raises(ValueError, match="key is missing"):
        application.verify_audit_log("Orbit Admin")


def test_an_audit_key_shorter_than_32_characters_counts_as_not_set(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setenv("AUDIT_KEY", "short-secret")
    application = App(ai_caller=None, data_folder=str(tmp_path / "data"))
    assert not application.audit_key_ok() and application.start_web() == 1
    assert App.AUDIT_KEY_MISSING in capsys.readouterr().out


def test_verify_with_a_different_key_than_the_log_was_written_with_reports_changes(app, tmp_path, monkeypatch):
    app.sync_to_cloud()
    app.sync_to_cloud()
    monkeypatch.setenv("AUDIT_KEY", "f" * 64)
    other = App(ai_caller=None, data_folder=str(tmp_path))
    chain = other.verify_audit_log("Orbit Admin")
    assert not chain.intact() and "entries 1, 2 do not match" in chain.summary()


def _add_unreadable_rows(tmp_path, count):
    """Append rows the app cannot show (unsealed, no time, no id) to the audit file."""
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    rows += [{"action": "cloud_sync", "actor": "Shareen"} for _ in range(count)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_the_log_and_the_trail_count_the_unreadable_rows_of_the_whole_log(app, tmp_path):
    ref = _assessed(app)[0].client_ref
    assert app.audit_log(AuditFilter("custom")).unreadable == 0 and app.audit_trail(ref)[1] == 0
    _add_unreadable_rows(tmp_path, 3)
    log = app.audit_log(AuditFilter("custom"))
    assert log.total == len(log.events) and log.unreadable == 3
    trail, trail_unreadable = app.audit_trail(ref)
    assert trail and trail_unreadable == 3                    # counted for the whole log, not just this client
    nobody = app.audit_log(AuditFilter("custom", client_ref="nobody"))
    assert (nobody.total, nobody.unreadable) == (0, 3)        # a filter never hides them


def test_a_log_where_every_row_is_unreadable_gives_no_events_and_the_count(app, tmp_path):
    _add_unreadable_rows(tmp_path, 2)
    log = app.audit_log(AuditFilter("custom"))
    assert (log.events, log.total, log.unreadable, log.everything) == ([], 0, 2, 0)
    assert app.audit_trail("C-1") == ([], 2)


# ----- the audit Overview, flags and "database unreadable" lines ----------------------------------------

import stat
from datetime import date, datetime, timezone

from app.model.overview_page import OverviewPage
from tests.audit_files import audit_path, seed_audit

FLAG_NOW = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)          # 16:00 on Monday 16 Nov in Singapore
ADMIN = "Orbit Admin"
NIGHT_OWNER = [("client_created", "2026-11-10T02:00:00Z", "Shareen", "SOW-1", "ok", {}),
               # Adrian did not create SOW-1 and changed a watched field: "Edited by non-owner", high (entry 2)
               ("client_edited", "2026-11-10T03:00:00Z", "Adrian", "SOW-1", "ok",
                {"changes": [{"field": "claims.expected_aum", "before": 1, "after": 2}]}),
               # 00:00 in Singapore: "After-hours activity", low (entry 3)
               ("assessment_run", "2026-11-11T16:00:00Z", "Shareen", "SOW-1", "ok",
                {"outcome": "PASSED", "assessment_id": "A-1"})]


@pytest.fixture
def flagged(app, tmp_path):
    """An App whose audit log holds one high flag (F-OTH-SOW-1-2) and one low flag (F-HOU-SOW-1-3)."""
    seed_audit(tmp_path, NIGHT_OWNER)
    return app


def _log_text(tmp_path):
    return (tmp_path / "local database" / "audit_log.json").read_text(encoding="utf-8")


def test_the_audit_settings_come_from_the_policy(app):
    assert app.audit_policy.window_days == 30 and app.audit_policy.jump_levels == 2


@pytest.mark.parametrize("value, text", [("often", "'often'"), ({"window_days": 0}, "window_days")])
def test_a_bad_audit_setting_is_logged_and_the_defaults_are_used(tmp_path, monkeypatch, caplog, value, text):
    import shutil
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    root = tmp_path / "root"
    shutil.copytree("config", root / "config")
    policy = json.loads((root / "config" / "policy.json").read_text())
    policy["audit"] = value
    (root / "config" / "policy.json").write_text(json.dumps(policy))
    application = App(ai_caller=None, root=str(root), data_folder=str(tmp_path / "data"))
    assert text in caplog.text and "audit" in caplog.text
    assert application.audit_policy.window_days == 30                      # the defaults


def test_the_overview_counts_the_range_and_the_flags(flagged):
    page = flagged.audit_overview("7", now=FLAG_NOW)
    assert (page.preset, page.day_from, page.day_to) == ("7", date(2026, 11, 10), date(2026, 11, 16))
    assert (page.to_handle, page.not_started, page.in_progress, page.open_flags) == (2, 2, 0, 2)
    assert (page.actions, page.failures, page.broken_at, page.unreadable) == (3, 0, 0, 0)
    assert page.intact and page.actions_change is None and page.failures_change is None   # no earlier data
    assert page.severity_counts == {"high": 1, "medium": 0, "low": 1}
    assert [kind for kind, _, _, _ in page.flags_by_type] == ["other", "hours"]
    assert page.type_severity == {"other": "high", "hours": "low"}
    assert page.entries == 3 and [e.sequence for e in page.evidence("F-OTH-SOW-1-2")] == [2]
    assert page.evidence("F-HOU-SOW-1-3")[0].action == "assessment_run" and page.evidence("F-X") == []
    assert [ticket.flag.flag_id for ticket in page.rows] == ["F-OTH-SOW-1-2", "F-HOU-SOW-1-3"]    # high before low
    assert (page.tab, page.page, page.page_count) == ("handle", 1, 1)
    assert page.tab_counts == {"handle": 2, "open": 2, "review": 0, "followup": 0, "resolved": 0, "all": 2}
    assert [day for day, _ in page.failures_by_day] == [f"2026-11-{n}" for n in range(10, 17)]


def test_the_ranges_are_singapore_days_back_from_today(flagged):
    spans = {preset: flagged.audit_overview(preset, now=FLAG_NOW) for preset in OverviewPage.PRESETS}
    assert (spans["today"].day_from, spans["today"].day_to) == (date(2026, 11, 16),) * 2
    assert spans["7"].day_from == date(2026, 11, 10)
    assert spans["30"].day_from == date(2026, 10, 18) and spans["90"].day_from == date(2026, 8, 19)
    assert spans["today"].actions == 0 and spans["today"].flags_by_type == []      # nothing raised today ...
    assert spans["today"].to_handle == 2 and spans["today"].rows                   # ... but flags stay until resolved


def test_the_change_against_the_range_before_is_given_when_the_log_reaches_back(app, tmp_path):
    seed_audit(tmp_path, [("cloud_sync", "2026-11-03T04:00:00Z", "terminal", "", "ok", {"synced": 1})] +
               [("cloud_sync", f"2026-11-1{n}T04:00:00Z", "terminal", "", "failed", {"synced": 0}) for n in range(0, 3)])
    page = app.audit_overview("7", now=FLAG_NOW)                  # 10 to 16 Nov; before: 3 to 9 Nov
    assert (page.actions, page.failures) == (3, 3)
    assert page.actions_change == 200 and page.failures_change is None      # 1 action before, no failures before


@pytest.mark.parametrize("kwargs", [{"preset": "1"}, {"preset": "custom"}, {"preset": 7}, {"tab": "done"},
                                    {"page": 0}, {"page": "1"}, {"page": True}, {"now": datetime(2026, 11, 16)}])
def test_the_overview_refuses_a_range_tab_page_or_time_that_is_not_allowed(flagged, kwargs):
    with pytest.raises(ValueError):
        flagged.audit_overview(**kwargs)


def test_an_empty_log_gives_an_overview_with_no_flags_not_an_error(app):
    page = app.audit_overview(now=FLAG_NOW)
    assert (page.to_handle, page.actions, page.rows, page.broken_at) == (0, 0, [], 0)


def test_the_flags_table_has_six_to_a_page_and_a_page_past_the_end_is_the_last(app, tmp_path):
    lines = []
    for number in range(8):             # eight clients, each edited by its owner at 00:00 in Singapore
        client = f"C-{number}"
        lines += [("client_created", "2026-11-10T02:00:00Z", "Shareen", client, "ok", {}),
                  ("client_edited", "2026-11-11T16:00:00Z", "Shareen", client, "ok",
                   {"changes": [{"field": "career.employer", "before": "A", "after": "B"}]})]
    seed_audit(tmp_path, lines)
    first = app.audit_overview(now=FLAG_NOW)
    assert (first.page, first.page_count, len(first.rows), first.tab_counts["all"]) == (1, 2, 6, 8)
    assert len(app.audit_overview(page=2, now=FLAG_NOW).rows) == 2
    assert app.audit_overview(page=9, now=FLAG_NOW).page == 2
    assert len({t.flag.flag_id for t in first.rows} | {t.flag.flag_id for t in app.audit_overview(
        page=2, now=FLAG_NOW).rows}) == 8


def test_the_tabs_follow_each_flags_status_and_resolved_flags_go_last(flagged):
    ticket, problems, _ = flagged.update_flag("F-OTH-SOW-1-2", ADMIN, "review", "Asked Adrian why.", now=FLAG_NOW)
    assert problems == [] and ticket.status == "review"
    flagged.update_flag("F-HOU-SOW-1-3", ADMIN, "resolved", "Planned night work.", outcome="legit", now=FLAG_NOW)
    page = flagged.audit_overview(tab="all", now=FLAG_NOW)
    assert [t.flag.flag_id for t in page.rows] == ["F-OTH-SOW-1-2", "F-HOU-SOW-1-3"]
    assert page.tab_counts == {"handle": 1, "open": 0, "review": 1, "followup": 0, "resolved": 1, "all": 2}
    assert (page.to_handle, page.not_started, page.in_progress) == (1, 0, 1)
    assert [t.flag.flag_id for t in flagged.audit_overview(tab="handle", now=FLAG_NOW).rows] == ["F-OTH-SOW-1-2"]
    assert [t.flag.flag_id for t in flagged.audit_overview(tab="resolved", now=FLAG_NOW).rows] == ["F-HOU-SOW-1-3"]
    assert flagged.audit_overview(tab="open", now=FLAG_NOW).rows == []
    assert page.flags_by_type[0][:3] == ("other", "Edited by non-owner", 1) and page.severity_counts["low"] == 0


def test_a_resolved_flag_that_is_older_than_a_new_open_one_still_sorts_after_it(app, tmp_path):
    """Unresolved first by priority then newest, then resolved newest first, whatever their priority."""
    seed_audit(tmp_path, NIGHT_OWNER)
    app.update_flag("F-OTH-SOW-1-2", ADMIN, "resolved", "Checked with Adrian.", outcome="fixed", now=FLAG_NOW)
    assert [t.flag.flag_id for t in app.audit_overview(tab="all", now=FLAG_NOW).rows] == \
        ["F-HOU-SOW-1-3", "F-OTH-SOW-1-2"]


def test_a_changed_log_shows_in_the_overview_with_its_flag_and_unreadable_rows_are_counted(flagged, tmp_path):
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[1]["actor"] = "Someone Else"
    path.write_text(json.dumps(rows + [{"junk": 1}]), encoding="utf-8")
    page = flagged.audit_overview(now=FLAG_NOW)
    assert (page.broken_at, page.intact, page.unreadable) == (2, False, 1)
    assert "F-INT-2" in [t.flag.flag_id for t in page.rows]
    assert page.rows[0].flag.severity == "high"


def test_a_flag_update_added_to_the_file_by_hand_cannot_close_a_flag(flagged, tmp_path):
    """Only lines the app signed with its key move a flag: a forged "resolved" line (any hash) is ignored,
    even for the "log changed outside the app" flag it would hide, while a real update after it still counts."""
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    forged = dict(rows[-1], action="flag_updated", actor=ADMIN, result="ok", sequence=len(rows) + 1,
                  details={"flag_id": "F-INT-4", "from": "open", "to": "resolved", "waiting_on": "",
                           "outcome": "legit", "note": "Nothing to see here."}, hash="ab" * 32)
    path.write_text(json.dumps(rows + [forged]), encoding="utf-8")
    page = flagged.audit_overview(tab="all", now=FLAG_NOW)
    integrity = [t for t in page.rows if t.flag.kind == "integrity"]
    assert page.unreadable == 0 and page.broken_at == 4                 # the forged line is read, but ...
    assert len(integrity) == 1 and integrity[0].status == "open"        # ... it does not close the flag
    ticket, problems, _ = flagged.update_flag(integrity[0].flag.flag_id, ADMIN, "review", "Reported it to IT.",
                                              now=FLAG_NOW)
    assert problems == [] and ticket.status == "review"            # a real update made by the app still counts


def test_a_log_without_a_key_cannot_be_checked_so_the_overview_says_so(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    import shutil
    shutil.copytree("config", tmp_path / "root" / "config")      # a root with no .env, so no key is read from it
    seed_audit(tmp_path / "data", NIGHT_OWNER)
    monkeypatch.delenv("AUDIT_KEY")
    keyless = App(ai_caller=None, root=str(tmp_path / "root"), data_folder=str(tmp_path / "data"))
    with pytest.raises(ValueError, match="key is missing"):
        keyless.audit_overview(now=FLAG_NOW)
    with pytest.raises(ValueError, match="key is missing"):
        keyless.update_flag("F-OTH-SOW-1-2", ADMIN, "review", "Asked Adrian why.", now=FLAG_NOW)
    assert keyless.audit_log(AuditFilter(), FLAG_NOW).total == 3          # the log itself can still be shown
    assert "not checked for changes" in caplog.text


def test_when_the_log_cannot_be_read_the_flag_methods_say_so_not_empty(flagged, tmp_path):
    break_audit(tmp_path)
    for call in (lambda: flagged.audit_overview(now=FLAG_NOW), lambda: flagged.flag("F-OTH-SOW-1-2"), lambda: flagged.flag_evidence("F-OTH-SOW-1-2"),
                 lambda: flagged.client_flags("SOW-1"),
                 lambda: flagged.update_flag("F-OTH-SOW-1-2", ADMIN, "review", "Asked Adrian why."),
                 lambda: flagged.audit_log(AuditFilter())):
        with pytest.raises(ValueError, match="audit log"):
            call()


def test_a_flag_is_found_by_its_id_or_is_none(flagged):
    ticket = flagged.flag(" F-OTH-SOW-1-2 ", FLAG_NOW)
    assert (ticket.flag.kind, ticket.status, ticket.flag.client_ref) == ("other", "open", "SOW-1")
    assert flagged.flag("F-OTH-SOW-1-99", FLAG_NOW) is None and flagged.flag("", FLAG_NOW) is None
    with pytest.raises(ValueError):
        flagged.flag(None)


def test_the_flag_evidence_is_the_ticket_the_entries_behind_it_and_the_size_of_the_log(flagged, tmp_path):
    ticket, entries, size = flagged.flag_evidence(" F-OTH-SOW-1-2 ", FLAG_NOW)
    assert ticket.flag.flag_id == "F-OTH-SOW-1-2" and [e.sequence for e in entries] == [2] and size == 3
    assert flagged.flag_evidence("F-OTH-SOW-1-99", FLAG_NOW) == (None, [], 0)
    with pytest.raises(ValueError, match="must be text"):
        flagged.flag_evidence(None)
    _add_unreadable_rows(tmp_path, 2)
    assert flagged.flag_evidence("F-HOU-SOW-1-3", FLAG_NOW)[2] == 5      # the unreadable rows still count


def test_an_update_writes_one_line_in_the_log_and_gives_back_its_number(flagged, tmp_path):
    ticket, problems, entry = flagged.update_flag("F-OTH-SOW-1-2", ADMIN, "followup", "  Asked Adrian by email. ",
                                                  "Officer who made the change", now=FLAG_NOW)
    assert problems == [] and entry == 4 and flagged.audit_write_failed() is False
    assert (ticket.status, ticket.waiting_on, ticket.assignee) == ("followup", "Officer who made the change", ADMIN)
    line = _events(flagged)[-1]
    assert (line.action, line.actor, line.client_ref, line.result, line.sequence) == \
        ("flag_updated", ADMIN, "SOW-1", "ok", 4)
    assert line.details == {"flag_id": "F-OTH-SOW-1-2", "from": "open", "to": "followup",
                            "waiting_on": "Officer who made the change", "outcome": "", "note": "Asked Adrian by email."}
    assert flagged.flag("F-OTH-SOW-1-2", FLAG_NOW).status == "followup"          # rebuilt from the log
    assert flagged.verify_audit_log(ADMIN).intact()                              # and the chain still holds
    _, _, again = flagged.update_flag("F-OTH-SOW-1-2", ADMIN, "followup", "Still waiting for a reply.", now=FLAG_NOW)
    assert again == 6                                                            # entry 5 is the "verified" line


@pytest.mark.parametrize("args, text", [
    (("review", "no"), "at least 5 characters"),
    (("review", "x" * 501), "500 characters"),
    (("done", "Asked Adrian why."), "Choose a status"),
    (("followup", "Asked Adrian why."), "who you are waiting on"),
    (("resolved", "Planned night work."), "outcome before resolving")])
def test_an_update_that_is_not_valid_says_why_and_writes_nothing(flagged, args, text):
    before = len(_events(flagged))
    ticket, problems, entry = flagged.update_flag("F-OTH-SOW-1-2", ADMIN, *args, now=FLAG_NOW)
    assert ticket.status == "open" and entry == 0 and any(text in line for line in problems)
    assert len(_events(flagged)) == before


def test_an_update_to_a_flag_that_is_gone_says_so_and_writes_nothing(flagged):
    assert flagged.update_flag("F-OTH-SOW-1-99", ADMIN, "review", "Asked Adrian why.", now=FLAG_NOW) == \
        (None, [App.FLAG_GONE], 0)
    assert len(_events(flagged)) == 3


def test_only_an_admin_can_update_a_flag_and_the_inputs_must_be_text(flagged):
    for actor in ("Shareen", "terminal", "unknown", "Mallory", None):
        with pytest.raises(ValueError):
            flagged.update_flag("F-OTH-SOW-1-2", actor, "review", "Asked Adrian why.", now=FLAG_NOW)
    for kwargs in ({"flag_id": 5}, {"status": ["review"]}, {"note": None}, {"waiting_on": 1}, {"outcome": 1}):
        arguments = {"flag_id": "F-OTH-SOW-1-2", "status": "review", "note": "Asked Adrian why."} | kwargs
        with pytest.raises(ValueError, match="must be text"):
            flagged.update_flag(actor=ADMIN, now=FLAG_NOW, **arguments)
    assert len(_events(flagged)) == 3


def test_an_update_that_cannot_be_written_is_not_saved_and_the_caller_can_tell(flagged, tmp_path, caplog):
    folder = tmp_path / "local database"
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)                  # readable, but no new file can be made in it
    try:
        ticket, problems, entry = flagged.update_flag("F-OTH-SOW-1-2", ADMIN, "review", "Asked Adrian why.",
                                                      now=FLAG_NOW)
    finally:
        folder.chmod(stat.S_IRWXU)
    assert problems == [App.FLAG_NOT_SAVED] and entry == 0 and ticket.status == "open"
    assert flagged.audit_write_failed() is True
    assert "was not written" in caplog.text
    assert flagged.flag("F-OTH-SOW-1-2", FLAG_NOW).status == "open" and len(_events(flagged)) == 3


def test_the_flags_of_one_client_are_the_ones_not_resolved(flagged):
    assert [t.flag.flag_id for t in flagged.client_flags(" sow-1 ", FLAG_NOW)] == ["F-OTH-SOW-1-2", "F-HOU-SOW-1-3"]
    assert flagged.client_flags("C-9", FLAG_NOW) == [] and flagged.client_flags("", FLAG_NOW) == []
    flagged.update_flag("F-OTH-SOW-1-2", ADMIN, "resolved", "Checked with Adrian.", outcome="legit", now=FLAG_NOW)
    assert [t.flag.flag_id for t in flagged.client_flags("SOW-1", FLAG_NOW)] == ["F-HOU-SOW-1-3"]


def test_the_log_can_show_only_the_entries_behind_open_flags_and_counts_them(flagged):
    everything = flagged.audit_log(AuditFilter(), FLAG_NOW)
    assert (everything.total, everything.open_flags) == (3, 2)
    only = flagged.audit_log(AuditFilter(flagged_only=True), FLAG_NOW)
    assert [event.sequence for event in only.events] == [3, 2] and (only.total, only.open_flags) == (2, 2)
    assert everything.flagged == frozenset({2, 3}) and only.flagged == frozenset({2, 3})
    flagged.update_flag("F-HOU-SOW-1-3", ADMIN, "resolved", "Planned night work.", outcome="legit", now=FLAG_NOW)
    after = flagged.audit_log(AuditFilter(flagged_only=True), FLAG_NOW)
    assert [event.sequence for event in after.events] == [2] and after.open_flags == 1
    assert flagged.audit_log(AuditFilter(flagged_only=True, actor="Shareen"), FLAG_NOW).total == 0


def test_an_unreadable_client_database_is_written_to_the_log_once_per_request(app, tmp_path):
    _damage(tmp_path, "sow_cases.json")
    for call in (lambda: app.find_client("C-1"), app.all_clients, lambda: app.client_ref_taken("C-1")):
        with pytest.raises(ValueError, match="client database"):
            call()
    [line] = _events(app)
    assert (line.action, line.actor, line.client_ref, line.result, line.details) == \
        ("data_unavailable", App.UNKNOWN, "", "failed", {"what": "client records"})
    assert app.audit_write_failed() is False


def test_an_unreadable_assessment_database_is_written_to_the_log_with_who_asked(app, tmp_path):
    _damage(tmp_path, "ai_assessments.json")
    with pytest.raises(ValueError, match="saved assessments"):
        app.all_assessments()
    app.refused("Shareen", "something")                        # a new request starts
    with pytest.raises(ValueError, match="saved assessments"):
        app.archive_assessment("A-1", "", "Shareen")
    lines = [event for event in _events(app) if event.action == "data_unavailable"]
    assert [(e.actor, e.details) for e in lines] == [(App.UNKNOWN, {"what": "assessments"}),
                                                     ("Shareen", {"what": "assessments"})]


def test_a_read_failure_line_that_cannot_be_written_never_raises_and_does_not_hide_the_read_error(app, tmp_path):
    _damage(tmp_path, "sow_cases.json")
    break_audit(tmp_path)
    with pytest.raises(ValueError, match="client database"):          # the real problem, not an audit one
        app.find_client("C-1")
    assert app.audit_write_failed() is False


def test_the_read_failures_are_the_read_failed_bar_of_the_overview(app, tmp_path):
    _damage(tmp_path, "sow_cases.json")
    with pytest.raises(ValueError):
        app.all_clients()
    page = app.audit_overview()
    assert page.failures == 1 and page.failures_by_day[-1][1]["Read failed"] == 1


class _FailingRules:
    """Stands in for AuditInsights when the flag rules cannot run."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def flags(self):
        raise ValueError("made-up rule failure")


class _SkippingRules:
    """Stands in for AuditInsights when the rules found flags that could not be built."""
    skipped = 2

    def __init__(self, *args, **kwargs) -> None:
        pass

    def flags(self):
        return []


def _app_with_rules(tmp_path, monkeypatch, rules):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    return App(ai_caller=None, data_folder=str(tmp_path), rules=rules)


def test_the_flag_rules_must_be_a_class(tmp_path):
    with pytest.raises(ValueError, match="flag rules must be a class"):
        App(ai_caller=None, data_folder=str(tmp_path), rules="AuditInsights")
    with pytest.raises(ValueError, match="flag rules must be a class"):
        App(ai_caller=None, data_folder=str(tmp_path), rules=lambda *args: None)


def test_the_log_still_shows_its_events_when_the_flag_rules_fail(tmp_path, monkeypatch, caplog):
    app = _app_with_rules(tmp_path, monkeypatch, _FailingRules)
    app.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    log = app.audit_log(AuditFilter())
    assert log.total == 1 and log.flags_ok is False and log.open_flags is None and log.flagged == frozenset()
    assert "the flags could not be worked out" in caplog.text and "made-up rule failure" in caplog.text
    with pytest.raises(ValueError, match="flags could not be worked out"):
        app.audit_log(AuditFilter(flagged_only=True))
    with pytest.raises(ValueError, match="flags could not be worked out"):
        app.audit_overview()


def test_flags_that_could_not_be_built_are_logged_and_counted_on_the_pages(tmp_path, monkeypatch, caplog):
    app = _app_with_rules(tmp_path, monkeypatch, _SkippingRules)
    app.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    assert app.audit_log(AuditFilter()).flags_skipped == 2
    assert app.audit_overview().flags_skipped == 2
    assert "2 flag(s) found by the rules could not be built" in caplog.text


class _CountingRules:
    """The real flag rules, counting how many times they are run."""
    runs = 0

    def __init__(self, *args, **kwargs) -> None:
        _CountingRules.runs += 1
        self.__real = AuditInsights(*args, **kwargs)
        self.skipped = self.__real.skipped

    def flags(self):
        return self.__real.flags()


def test_the_open_flag_count_is_kept_until_the_log_changes(tmp_path, monkeypatch):
    _CountingRules.runs = 0
    app = _app_with_rules(tmp_path, monkeypatch, _CountingRules)
    seed_audit(tmp_path, NIGHT_OWNER)
    assert app.open_flag_count(FLAG_NOW) == 2 and _CountingRules.runs == 1
    assert app.open_flag_count(FLAG_NOW) == 2 and _CountingRules.runs == 1        # same log: no second run
    app.update_flag("F-HOU-SOW-1-3", ADMIN, "resolved", "Planned night work.", outcome="legit", now=FLAG_NOW)
    assert app.open_flag_count(FLAG_NOW) == 1                                      # a new line: worked out again
    runs = _CountingRules.runs
    assert runs > 1 and app.open_flag_count(FLAG_NOW) == 1 and _CountingRules.runs == runs


def test_an_open_flag_count_that_cannot_be_worked_out_is_none_not_zero(tmp_path, monkeypatch, caplog):
    app = _app_with_rules(tmp_path, monkeypatch, _FailingRules)
    seed_audit(tmp_path, NIGHT_OWNER)
    assert app.open_flag_count(FLAG_NOW) is None and "the open flags cannot be counted" in caplog.text
    assert app.open_flag_count(FLAG_NOW) is None                                   # a failure is never kept
    break_audit(tmp_path)
    assert app.open_flag_count(FLAG_NOW) is None


def test_an_empty_log_has_no_open_flags(app):
    assert app.open_flag_count() == 0


def test_a_read_failure_line_names_the_actor_the_request_began_with_and_each_request_gets_its_own_line(app, tmp_path):
    _damage(tmp_path, "sow_cases.json")
    app.begin_request("Shareen")
    with pytest.raises(ValueError, match="client database"):
        app.all_clients()
    with pytest.raises(ValueError, match="client database"):
        app.find_client("C-1")                                  # same request: no second line
    app.begin_request("Adrian")
    with pytest.raises(ValueError, match="client database"):
        app.all_clients()
    app.begin_request(App.UNKNOWN)
    with pytest.raises(ValueError, match="client database"):
        app.all_clients()
    lines = [event for event in _events(app) if event.action == "data_unavailable"]
    assert [event.actor for event in lines] == ["Shareen", "Adrian", App.UNKNOWN]


def test_begin_request_refuses_a_name_that_is_not_an_account_and_keeps_a_pending_audit_failure(app):
    with pytest.raises(ValueError, match="actor"):
        app.begin_request("Nobody Here")
    with pytest.raises(ValueError, match="actor"):
        app.begin_request(None)
    app.begin_request(App.TERMINAL)
    assert app.audit_write_failed() is False


def test_flags_to_handle_is_known_only_after_the_flags_were_worked_out_in_this_request(flagged):
    flagged.begin_request(ADMIN)
    assert flagged.flags_to_handle() is None
    flagged.client_flags("SOW-1", FLAG_NOW)
    assert isinstance(flagged.flags_to_handle(), int) and flagged.flags_to_handle() > 0
    flagged.begin_request(ADMIN)
    assert flagged.flags_to_handle() is None


# ----- menu 8: a client's history, assessments and archive/restore -------------------------------

CLIENT_REF = sample_case()["client_ref"]
LOOK = ("Orbit Officer",)


def _history_client(app, *, with_assessments=True):
    """A saved client (no audit line of its own) and, optionally, two forecast-only assessments of it."""
    assert app.clients().save(sample_case())
    if with_assessments:
        for number in (1, 2):
            assert app.assessments().save({"assessment_id": f"A{number}", "client_ref": CLIENT_REF, "kind": "onboarding",
                                           "assessed_at": f"2026-11-0{number}T00:00:00+00:00", "outcome": "PASSED",
                                           "assessment": {"assessed_on": f"2026-11-0{number}", "outcome": "PASSED"}})


def _run_menu(app, monkeypatch, capsys, *typed):
    capsys.readouterr()
    _answers(monkeypatch, *typed)
    app.run_menu()
    return capsys.readouterr().out


def _seed_history(tmp_path):
    seed_audit(tmp_path, [
        ("client_created", "2026-11-10T02:00:00Z", "Orbit Officer", CLIENT_REF, "ok", {}),
        ("client_edited", "2026-11-12T02:00:00Z", "Orbit Officer", CLIENT_REF, "ok", {"changes": [{}]}),
        ("assessment_run", "2026-11-12T09:30:00Z", "terminal", CLIENT_REF, "ok", {"outcome": "PASSED"}),
        ("client_created", "2026-11-12T03:00:00Z", "Orbit Officer", "CL-OTHER", "ok", {})])


def test_client_history_shows_the_audit_trail_by_day_newest_first(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert out.index("12 November 2026") < out.index("10 November 2026")
    assert out.index("Assessment saved for client") < out.index("Edited client") < out.index("Created client")
    assert "17:30  Assessment saved" in out and "by terminal" in out       # 09:30 UTC is 17:30 in Singapore
    assert "CL-OTHER" not in out
    assert "Showing: All, All time" in out


def test_client_history_shows_the_clients_assessments_with_archive_marks(app, monkeypatch, capsys):
    _history_client(app)
    app.archive_assessment("A1")
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF.lower(), "0", "0")
    assert "Saved assessments" in out
    assert out.count("(archived)") == 1


def test_the_history_filter_keeps_only_the_chosen_kind_of_event(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "3", "1", "0", "0")   # Assessments, all time
    assert "Showing: Assessments, All time" in out
    assert "Assessment saved for client" in out and "Edited client" not in out


def test_a_filter_with_no_match_says_no_history_matches_not_no_history_yet(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "4", "1", "0", "0")   # Documents, all time
    assert "Nothing matches these filters." in out and "No history recorded yet." not in out


def test_a_client_with_no_audit_lines_has_no_history_yet(app, monkeypatch, capsys):
    _history_client(app)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert "No history recorded yet." in out and "Nothing matches" not in out


def test_a_bad_custom_date_shows_the_models_message_and_asks_again(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "1", "5",
                    "11/12/2026", "", "2026-11-12", "2026-11-12", "0", "0")
    assert out.count("The dates must look like 2026-11-15") == 1
    assert "Showing: All, Pick dates… (2026-11-12 to 2026-11-12)" in out
    assert "12 November 2026" in out and "10 November 2026" not in out
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "1", "5", "2026-11-12", "2026-11-10", "2026-11-10", "2026-11-12", "0", "0")
    assert "The start date must be on or before the end date." in out


def test_entries_of_the_log_that_cannot_be_read_are_counted_in_the_history(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    path = tmp_path / "local database" / "audit_log.json"
    path.write_text(json.dumps(json.loads(path.read_text(encoding="utf-8")) + [{"action": "bogus"}]), encoding="utf-8")
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert "1 entry in the audit log can't be read, so this history may be incomplete." in out
    assert "Edited client" in out


def test_an_unreadable_audit_log_says_so_and_never_no_history(app, tmp_path, monkeypatch, capsys, caplog):
    _history_client(app)
    _damage(tmp_path, "audit_log.json")
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert App.AUDIT_UNAVAILABLE in out
    assert "No history" not in out
    assert "the audit log cannot be read" in caplog.text
    assert "Saved assessments" in out                        # the rest of the screen still works


def test_client_history_for_an_unknown_client_says_so(app, monkeypatch, capsys):
    out = _run_menu(app, monkeypatch, capsys, "8", "CL-NOPE", "0")
    assert "No client found with reference CL-NOPE." in out


def test_client_history_says_when_the_client_database_cannot_be_read(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "sow_cases.json")
    out = _run_menu(app, monkeypatch, capsys, "8", "CL-1", "0")
    assert App.CLIENTS_UNAVAILABLE in out and "No client found" not in out


def test_client_history_going_back_at_the_reference_returns_to_the_menu(app, monkeypatch, capsys):
    assert "Goodbye." in _run_menu(app, monkeypatch, capsys, "8", "0", "0")


def test_unreadable_saved_assessments_are_said_but_the_history_still_works(app, tmp_path, monkeypatch, capsys, caplog):
    _history_client(app, with_assessments=False)
    _seed_history(tmp_path)
    _damage(tmp_path, "ai_assessments.json")
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert App.ASSESSMENTS_UNAVAILABLE in out
    assert "Edited client" in out
    assert "Saved assessments" not in out and "No saved assessments" not in out
    assert "App.__show_client_assessments" in caplog.text


def test_a_client_assessment_can_be_opened_in_full_from_the_client_history(app, monkeypatch, capsys):
    saved = _saved_assessment(app)
    out = _run_menu(app, monkeypatch, capsys, "8", saved["client_ref"], "3", "1", "n", "0", "0")
    assert f"COMBINED ASSESSMENT  {saved['client_ref']}" in out


def test_an_assessment_is_archived_with_a_reason_from_the_client_history(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "1", "y", "client asked", "0", "0")
    assert "Assessment archived. It is hidden from the lists, not deleted." in out
    assert App.archive_state(app.assessments().find("A2")) == App.ARCHIVE_ARCHIVED
    assert out.count("(archived)") == 1                       # the list is shown again with the new mark
    events, _ = app.audit_trail(CLIENT_REF)
    assert events[0].action == "assessment_archived" and events[0].details["reason"] == "client asked"
    assert events[0].actor == App.TERMINAL


def test_a_bad_archive_reason_is_asked_again_and_nothing_is_archived_until_it_is_fine(app, monkeypatch, capsys):
    _history_client(app)
    too_long = "x" * (App.MAX_ARCHIVE_REASON + 1)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "1", "y", too_long, "short and fine", "0", "0")
    assert App.archive_reason_problem(too_long) in out
    assert "Assessment archived." in out
    assert app.assessments().find("A2")["archive_log"][-1]["reason"] == "short and fine"


def test_declining_the_archive_confirmation_changes_nothing(app, monkeypatch, capsys):
    _history_client(app)
    _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "1", "n", "0", "0")
    assert App.archive_state(app.assessments().find("A2")) == App.ARCHIVE_ACTIVE


def test_an_archived_assessment_is_restored_from_the_client_history(app, monkeypatch, capsys):
    _history_client(app)
    app.archive_assessment("A1")
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "2", "y", "0", "0")   # the older one, A1
    assert "Assessment restored." in out
    assert App.archive_state(app.assessments().find("A1")) == App.ARCHIVE_ACTIVE
    assert "(archived)" not in out.split("Assessment restored.")[1]


def test_an_assessment_whose_archive_record_is_damaged_cannot_be_changed(app, monkeypatch, capsys):
    _history_client(app, with_assessments=False)
    assert app.assessments().save({"assessment_id": "A9", "client_ref": CLIENT_REF, "kind": "onboarding",
                                   "archive_log": "broken", "outcome": "PASSED",
                                   "assessment": {"assessed_on": "2026-11-01", "outcome": "PASSED"}})
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "1", "0", "0")   # no y/n is asked
    assert "This assessment's archive record is damaged, so it cannot be changed." in out
    assert "(archive state unreadable)" in out


def test_an_archive_that_could_not_be_saved_says_it_was_not_archived(app, monkeypatch, capsys):
    _history_client(app)
    monkeypatch.setattr(app.assessments(), "_write_all", lambda records: False)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "1", "y", "", "0", "0")
    assert "The assessment was not archived because saving failed. Please try again later." in out
    assert "Assessment archived." not in out
    assert App.archive_state(app.assessments().find("A2")) == App.ARCHIVE_ACTIVE


def test_a_restore_that_could_not_be_saved_says_it_was_not_restored(app, monkeypatch, capsys):
    _history_client(app)
    app.archive_assessment("A1")
    monkeypatch.setattr(app.assessments(), "_write_all", lambda records: False)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "2", "y", "0", "0")
    assert "The assessment was not restored because saving failed. Please try again later." in out


def test_archiving_when_the_saved_assessments_cannot_be_read_gives_the_safe_message(app, monkeypatch, capsys, caplog):
    _history_client(app)

    def broken(*args, **kwargs):
        raise OSError("disk problem")
    monkeypatch.setattr(app.assessments(), "archive", broken)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "1", "y", "", "0", "0")
    assert App.ASSESSMENTS_UNAVAILABLE in out
    assert "Assessment archived." not in out and "disk problem" not in out
    assert "disk problem" in caplog.text


@pytest.mark.parametrize("result, message", [
    (App.ARCHIVE_NO_CHANGE, "This assessment is already archived."),
    (App.ARCHIVE_UNREADABLE, "This assessment's archive record is damaged, so it cannot be changed."),
    (App.ARCHIVE_NOT_FOUND, "That assessment could not be found, so nothing was changed."),
    (App.ARCHIVE_BAD_REASON, "Nothing was archived. "),
])
def test_every_other_archive_result_is_told_in_plain_words(app, monkeypatch, capsys, result, message):
    _history_client(app)
    monkeypatch.setattr(app, "archive_assessment", lambda assessment_id, reason="", actor="": result)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "4", "1", "y", "", "0", "0")
    assert message in out and "Assessment archived." not in out


def test_menu_5_can_archive_an_assessment_and_back_out(app, monkeypatch, capsys):
    _history_client(app)
    out = _run_menu(app, monkeypatch, capsys, "5", "1", "2", "1", "y", "no longer needed", "0")
    assert "Assessment archived." in out
    states = [App.archive_state(app.assessments().find(f"A{n}")) for n in (1, 2)]
    assert sorted(states) == [App.ARCHIVE_ACTIVE, App.ARCHIVE_ARCHIVED]
    _run_menu(app, monkeypatch, capsys, "5", "1", "0", "0")         # back at "What next?": nothing happens
    assert sorted(App.archive_state(app.assessments().find(f"A{n}")) for n in (1, 2)) == sorted(states)


def test_menu_5_shows_the_incomplete_tag_for_a_saved_combined_assessment(app, monkeypatch, capsys):
    saved = _saved_assessment(app)
    records = app.assessments().load()
    records[0]["report"]["header"]["incomplete"] = ["The peer benchmark"]
    assert app.assessments().save(records[0])
    out = _run_menu(app, monkeypatch, capsys, "5", "1", "0", "0")
    assert "(incomplete)" in out and saved["client_ref"] in out


def test_with_no_clients_the_client_list_does_not_read_the_audit_log(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "audit_log.json")
    out = _run_menu(app, monkeypatch, capsys, "6", "", "0")
    assert "No clients saved yet." in out
    assert App.AUDIT_UNAVAILABLE not in out


def test_a_custom_range_needs_both_dates_and_is_asked_again(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "1", "5",
                    "2026-11-12", "", "", "2026-11-12", "2026-11-10", "2026-11-12", "0", "0")
    assert out.count("Pick both a start and an end date.") == 2
    assert "Showing: All, Pick dates… (2026-11-10 to 2026-11-12)" in out
    assert "(2026-11-12 to ...)" not in out


def test_a_custom_range_ending_after_today_is_refused_and_asked_again(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "1", "5",
                    "2026-11-10", "2999-01-01", "2026-11-10", "2026-11-12", "0", "0")
    assert out.count("The dates cannot be in the future.") == 1
    assert "(2026-11-10 to 2026-11-12)" in out


def test_the_pick_list_shows_each_assessments_date_and_outcome_so_they_can_be_told_apart(app, monkeypatch, capsys):
    assert app.clients().save(sample_case())
    for number, outcome in ((1, "PASSED"), (2, "RISKY")):
        assert app.assessments().save({"assessment_id": f"P{number}", "client_ref": CLIENT_REF, "kind": "onboarding",
                                       "assessed_at": f"2026-11-0{number}T00:00:00+00:00", "outcome": outcome,
                                       "assessment": {"assessed_on": f"2026-11-0{number}", "outcome": outcome}})
    app.archive_assessment("P1")
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "3", "0", "0", "0")
    picks = [line for line in out.split("Which one?")[1].splitlines() if line.startswith("  ") and ". " in line][:2]
    assert len(set(picks)) == 2
    assert all("Assessment ID P" in p for p in picks)
    assert any("2026-11-02" in p and "RISKY" in p for p in picks)
    assert any("2026-11-01" in p and "PASSED" in p and "(archived)" in p for p in picks)


_UNREADABLE = "This saved assessment could not be read, so its report cannot be shown."


@pytest.mark.parametrize("extra", [{}, {"assessment": "text"}, {"assessment": {"outcome": "PASSED"}},
                                   {"report": {"header": {}}}])
def test_a_damaged_saved_assessment_is_reported_from_menu_8_and_never_ends_the_session(app, monkeypatch, capsys,
                                                                                      caplog, extra):
    _history_client(app, with_assessments=False)
    assert app.assessments().save({"assessment_id": "D1", "client_ref": CLIENT_REF, "kind": "combined",
                                   "verdict": {"assessed_on": "2026-11-01", "verdict": "PASSED"}, **extra})
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "3", "1", "0", "0")
    assert _UNREADABLE in out and "Goodbye." in out
    assert "COMBINED ASSESSMENT" not in out and "ONBOARDING" not in out
    assert "D1" in caplog.text and "ERROR" in caplog.text


def test_a_damaged_saved_assessment_is_reported_from_menu_5_too(app, monkeypatch, capsys, caplog):
    _history_client(app, with_assessments=False)
    assert app.assessments().save({"assessment_id": "D1", "client_ref": CLIENT_REF, "kind": "combined",
                                   "verdict": {"assessed_on": "2026-11-01", "verdict": "PASSED"}})
    out = _run_menu(app, monkeypatch, capsys, "5", "1", "1", "1", "0")
    assert _UNREADABLE in out and "Goodbye." in out
    assert "App.__open_assessment" in caplog.text and "Traceback" in caplog.text


def test_going_back_from_the_custom_dates_returns_to_the_period_question(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "1", "5", "0", "2", "0", "0")   # 0 at From, then 7 days
    assert out.count("Which period?") == 2
    assert "Showing: All, Last 7 days" in out
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "1", "5", "", "", "1", "0", "0")   # both blank, then all time
    assert out.count("Which period?") == 2 and "Showing: All, All time" in out
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "1", "5", "2026-11-10", "0", "3", "0", "0")
    assert out.count("Which period?") == 2 and "Showing: All, Last 30 days" in out


def test_todays_singapore_date_is_accepted_as_the_end_date(app, tmp_path, monkeypatch, capsys):
    from datetime import datetime, timezone
    _history_client(app)
    today = AuditFilter.singapore_day(datetime.now(timezone.utc)).isoformat()
    out = _run_menu(app, monkeypatch, capsys, "8", CLIENT_REF, "2", "1", "5", "2026-11-01", today, "0", "0")
    assert f"(2026-11-01 to {today})" in out and "cannot be in the future" not in out


def test_a_saved_report_without_its_evidence_prints_nothing_of_the_report(app, tmp_path, monkeypatch, capsys, caplog):
    saved = _saved_assessment(app)
    records = app.assessments().load()
    del records[0]["report"]["evidence"]
    with open(tmp_path / "local database" / "ai_assessments.json", "w", encoding="utf-8") as handle:
        json.dump(records, handle)
    out = _run_menu(app, monkeypatch, capsys, "8", saved["client_ref"], "3", "1", "0", "0")
    assert _UNREADABLE in out and "Goodbye." in out
    assert "COMBINED ASSESSMENT" not in out and "VERDICT:" not in out
    assert "App.__open_assessment" in caplog.text and "Traceback" in caplog.text
