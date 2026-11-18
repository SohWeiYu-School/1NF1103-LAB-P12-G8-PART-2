"""TerminalApp: the command line front end. It is driven with a ConsoleUI that reads made-up answers; the AI is a
made-up caller or saved sample replies; no network."""

import json
import os

import pytest

from app.application.app import App
from app.interface.console_ui import ConsoleUI
from app.interface.terminal_app import TerminalApp
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.client_record import ClientRecord
from app.model.verdict import Verdict
from tests import fake_ai, fake_services
from tests.audit_files import seed_audit
from tests.logic_fixtures import sample_case


@pytest.fixture
def app(tmp_path, monkeypatch):
    """An App that keeps its records, documents and saved replies in a temporary folder and has no AI."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    return App(ai_caller=None, data_folder=str(tmp_path))


def _terminal(app, *typed):
    """A TerminalApp whose screen reads the answers given, one for each question, in order."""
    waiting = iter(typed)
    return TerminalApp(app, ConsoleUI(read=lambda question="": next(waiting)))


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
    _terminal(app, "1", "1", "1", "y").list_assessments()         # every outcome, open one, the first, the evidence
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
    _terminal(app, "1", "1", "1").list_assessments()
    out = capsys.readouterr().out
    assert "This saved assessment could not be read" in out
    assert "COMBINED ASSESSMENT" not in out
    assert saved["assessment_id"] in caplog.text and "FINE" in caplog.text


def test_the_menu_can_list_clients_and_leave(app, monkeypatch, capsys):
    app.clients().save(sample_case())
    _terminal(app, "6", "", "0").run_menu()
    out = capsys.readouterr().out
    assert sample_case()["client_ref"] in out
    assert "Goodbye." in out


def test_the_client_list_in_the_menu_shows_each_clients_last_activity(app, monkeypatch, capsys):
    app.save_client(ClientRecord.from_dict(sample_case()), new_client=True)
    app.clients().save({**sample_case(), "client_ref": "CL-QUIET"})
    capsys.readouterr()
    _terminal(app, "6", "", "0").run_menu()
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
    _terminal(app, "6", "", "0").run_menu()
    out = capsys.readouterr().out
    assert sample_case()["client_ref"] in out
    assert App.AUDIT_UNAVAILABLE in out
    assert "Last activity" not in out and "No activity" not in out
    assert f"{App.AUDIT_UNAVAILABLE} The last activity of each client cannot be shown." in out
    assert "the audit log cannot be read" in caplog.text


def test_an_invalid_menu_choice_is_asked_again(app, monkeypatch, capsys):
    _terminal(app, "99", "abc", "0").run_menu()
    assert "Goodbye." in capsys.readouterr().out


def _broken_record() -> dict:
    """A saved record with an impossible value: ClientRecord cannot be built from it."""
    record = sample_case()
    record["career"]["age"] = 5
    return record


def test_the_menu_reports_a_client_that_cannot_be_read_and_carries_on(app, monkeypatch, capsys):
    app.clients().save(_broken_record())
    _terminal(app, "4", sample_case()["client_ref"], "0").run_menu()
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
    _terminal(app, "2", folder, "0", "1", "3", "0").run_menu()
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
    _terminal(app, "2", folder, "45", "0", "1", "3", "0").run_menu()
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
    _terminal(app, "2", folder, "0", "2003", "1", "3", "0").run_menu()
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
    _terminal(app, "2", folder, "0", "", "1", "3", "0").run_menu()
    assert "Client saved. Reference: CL-" in capsys.readouterr().out
    assert app.clients().load()[0]["career_history"][0]["end_year"] is None


def _damage(tmp_path, name):
    path = tmp_path / "local database" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"[{broken")
    return path


def test_the_menu_tells_the_user_when_the_client_database_cannot_be_read(app, tmp_path, monkeypatch, capsys, caplog):
    path = _damage(tmp_path, "sow_cases.json")
    _terminal(app, "6", "0").run_menu()
    out = capsys.readouterr().out
    assert App.CLIENTS_UNAVAILABLE in out
    assert "No clients saved yet" not in out
    assert "damaged" in caplog.text                               # the real details are logged
    assert "damaged" not in out and "JSONDecodeError" not in out  # and not shown
    assert path.read_bytes() == b"[{broken"


def test_the_menu_tells_the_user_when_the_saved_assessments_cannot_be_read(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "ai_assessments.json")
    _terminal(app, "5", "1", "0").run_menu()
    out = capsys.readouterr().out
    assert out.count(App.ASSESSMENTS_UNAVAILABLE) == 2           # at start-up, and when listing
    assert "saved assessment(s) loaded" not in out
    assert "No assessments" not in out


def test_menu_find_client_shows_the_message_not_no_client_found(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "sow_cases.json")
    _terminal(app, "4", "CL-1", "0").run_menu()
    out = capsys.readouterr().out
    assert App.CLIENTS_UNAVAILABLE in out and "No client found" not in out


def _two_saved(app):
    for number in (1, 2):
        assert app.assessments().save({"assessment_id": f"A{number}", "client_ref": "C-1", "kind": "onboarding",
                                       "assessed_at": f"2025-0{number}-01T00:00:00+00:00", "outcome": "PASSED"})


def test_the_menu_can_list_archived_assessments_too_and_marks_them(app, monkeypatch, capsys):
    _two_saved(app)
    app.archive_assessment("A1")
    app.assessments().save({"assessment_id": "A3", "client_ref": "C-3", "kind": "onboarding",
                            "archive_log": "broken", "outcome": "PASSED"})
    capsys.readouterr()
    _terminal(app, "1", "0").list_assessments()                   # every outcome: archived and damaged ones are hidden
    out = capsys.readouterr().out
    assert "(archived)" not in out and "unreadable" not in out and "C-3" not in out
    _terminal(app, str(len(Verdict.OUTCOMES) + 2), "0").list_assessments()     # the last option
    out = capsys.readouterr().out
    assert out.count("(archived)") == 1 and out.count("(archive state unreadable)") == 1 and "C-3" in out


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


def test_the_menu_flow_that_reads_documents_records_every_step(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setattr("app.interface.client_form.tk", None)
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "marcus_lim")
    with open(folder + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    app = App(fake_ai.caller(documents_reply=reading), data_folder=str(tmp_path))
    _terminal(app, "2", folder, "0", "1", "3", "0").run_menu()
    actions = _actions(app)
    assert actions[0] == "autofill_used" and actions[-1] == "client_created"
    assert actions.count("document_uploaded") == len(os.listdir(folder))
    assert {event.actor for event in _events(app)} == {App.TERMINAL}
    assert App.AUDIT_NOT_WRITTEN not in capsys.readouterr().out


def test_the_terminal_is_told_when_the_outcome_could_not_be_written(app, tmp_path, capsys, monkeypatch):
    record = ClientRecord.from_dict(sample_case())
    app.save_client(record)
    case, _ = app.read_case(record)
    fake_services.save_forecast_replies(app.response_cache(), case)
    _damage(tmp_path, "sow_cases.json")
    answers = TerminalApp(app, ConsoleUI(read=lambda question='': 'n'))        # the report asks about evidence
    assert answers.assess_client_record(record) is not None
    out = capsys.readouterr().out
    assert "Assessment saved." in out and App.OUTCOME_NOT_UPDATED in out


CLIENT_REF = sample_case()["client_ref"]


def _history_client(app, *, with_assessments=True):
    """A saved client (no audit line of its own) and, optionally, two forecast-only assessments of it."""
    assert app.clients().save(sample_case())
    if with_assessments:
        for number in (1, 2):
            assert app.assessments().save({"assessment_id": f"A{number}", "client_ref": CLIENT_REF, "kind": "onboarding",
                                           "assessed_at": f"2026-11-0{number}T00:00:00+00:00", "outcome": "PASSED",
                                           "assessment": {"assessed_on": f"2026-11-0{number}", "outcome": "PASSED"}})


def _run_menu(app, capsys, *typed):
    capsys.readouterr()
    _terminal(app, *typed).run_menu()
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
    out = _run_menu(app, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert out.index("12 November 2026") < out.index("10 November 2026")
    assert out.index("Assessment saved for client") < out.index("Edited client") < out.index("Created client")
    assert "17:30  Assessment saved" in out and "by terminal" in out       # 09:30 UTC is 17:30 in Singapore
    assert "CL-OTHER" not in out
    assert "Showing: All, All time" in out


def test_client_history_shows_the_clients_assessments_with_archive_marks(app, monkeypatch, capsys):
    _history_client(app)
    app.archive_assessment("A1")
    out = _run_menu(app, capsys, "8", CLIENT_REF.lower(), "0", "0")
    assert "Saved assessments" in out
    assert out.count("(archived)") == 1


def test_the_history_filter_keeps_only_the_chosen_kind_of_event(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "3", "1", "0", "0")   # Assessments, all time
    assert "Showing: Assessments, All time" in out
    assert "Assessment saved for client" in out and "Edited client" not in out


def test_a_filter_with_no_match_says_no_history_matches_not_no_history_yet(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "4", "1", "0", "0")   # Documents, all time
    assert "Nothing matches these filters." in out and "No history recorded yet." not in out


def test_a_client_with_no_audit_lines_has_no_history_yet(app, monkeypatch, capsys):
    _history_client(app)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert "No history recorded yet." in out and "Nothing matches" not in out


def test_a_bad_custom_date_shows_the_models_message_and_asks_again(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "1", "5",
                    "11/12/2026", "", "2026-11-12", "2026-11-12", "0", "0")
    assert out.count("The dates must look like 2026-11-15") == 1
    assert "Showing: All, Pick dates… (2026-11-12 to 2026-11-12)" in out
    assert "12 November 2026" in out and "10 November 2026" not in out
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "1", "5", "2026-11-12", "2026-11-10", "2026-11-10", "2026-11-12", "0", "0")
    assert "The start date must be on or before the end date." in out


def test_entries_of_the_log_that_cannot_be_read_are_counted_in_the_history(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    path = tmp_path / "local database" / "audit_log.json"
    path.write_text(json.dumps(json.loads(path.read_text(encoding="utf-8")) + [{"action": "bogus"}]), encoding="utf-8")
    out = _run_menu(app, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert "1 entry in the audit log can't be read, so this history may be incomplete." in out
    assert "Edited client" in out


def test_an_unreadable_audit_log_says_so_and_never_no_history(app, tmp_path, monkeypatch, capsys, caplog):
    _history_client(app)
    _damage(tmp_path, "audit_log.json")
    out = _run_menu(app, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert App.AUDIT_UNAVAILABLE in out
    assert "No history" not in out
    assert "the audit log cannot be read" in caplog.text
    assert "Saved assessments" in out                        # the rest of the screen still works


def test_client_history_for_an_unknown_client_says_so(app, monkeypatch, capsys):
    out = _run_menu(app, capsys, "8", "CL-NOPE", "0")
    assert "No client found with reference CL-NOPE." in out


def test_client_history_says_when_the_client_database_cannot_be_read(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "sow_cases.json")
    out = _run_menu(app, capsys, "8", "CL-1", "0")
    assert App.CLIENTS_UNAVAILABLE in out and "No client found" not in out


def test_client_history_going_back_at_the_reference_returns_to_the_menu(app, monkeypatch, capsys):
    assert "Goodbye." in _run_menu(app, capsys, "8", "0", "0")


def test_unreadable_saved_assessments_are_said_but_the_history_still_works(app, tmp_path, monkeypatch, capsys, caplog):
    _history_client(app, with_assessments=False)
    _seed_history(tmp_path)
    _damage(tmp_path, "ai_assessments.json")
    out = _run_menu(app, capsys, "8", CLIENT_REF, "1", "0", "0")
    assert App.ASSESSMENTS_UNAVAILABLE in out
    assert "Edited client" in out
    assert "Saved assessments" not in out and "No saved assessments" not in out
    assert "TerminalApp.__show_client_assessments" in caplog.text


def test_a_client_assessment_can_be_opened_in_full_from_the_client_history(app, monkeypatch, capsys):
    saved = _saved_assessment(app)
    out = _run_menu(app, capsys, "8", saved["client_ref"], "3", "1", "n", "0", "0")
    assert f"COMBINED ASSESSMENT  {saved['client_ref']}" in out


def test_an_assessment_is_archived_with_a_reason_from_the_client_history(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "4", "1", "y", "client asked", "0", "0")
    assert "Assessment archived. It is hidden from the lists, not deleted." in out
    assert App.archive_state(app.assessments().find("A2")) == App.ARCHIVE_ARCHIVED
    assert out.count("(archived)") == 1                       # the list is shown again with the new mark
    events, _ = app.audit_trail(CLIENT_REF)
    assert events[0].action == "assessment_archived" and events[0].details["reason"] == "client asked"
    assert events[0].actor == App.TERMINAL


def test_a_bad_archive_reason_is_asked_again_and_nothing_is_archived_until_it_is_fine(app, monkeypatch, capsys):
    _history_client(app)
    too_long = "x" * (App.MAX_ARCHIVE_REASON + 1)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "4", "1", "y", too_long, "short and fine", "0", "0")
    assert App.archive_reason_problem(too_long) in out
    assert "Assessment archived." in out
    assert app.assessments().find("A2")["archive_log"][-1]["reason"] == "short and fine"


def test_declining_the_archive_confirmation_changes_nothing(app, monkeypatch, capsys):
    _history_client(app)
    _run_menu(app, capsys, "8", CLIENT_REF, "4", "1", "n", "0", "0")
    assert App.archive_state(app.assessments().find("A2")) == App.ARCHIVE_ACTIVE


def test_an_archived_assessment_is_restored_from_the_client_history(app, monkeypatch, capsys):
    _history_client(app)
    app.archive_assessment("A1")
    out = _run_menu(app, capsys, "8", CLIENT_REF, "4", "2", "y", "0", "0")   # the older one, A1
    assert "Assessment restored." in out
    assert App.archive_state(app.assessments().find("A1")) == App.ARCHIVE_ACTIVE
    assert "(archived)" not in out.split("Assessment restored.")[1]


def test_an_assessment_whose_archive_record_is_damaged_cannot_be_changed(app, monkeypatch, capsys):
    _history_client(app, with_assessments=False)
    assert app.assessments().save({"assessment_id": "A9", "client_ref": CLIENT_REF, "kind": "onboarding",
                                   "archive_log": "broken", "outcome": "PASSED",
                                   "assessment": {"assessed_on": "2026-11-01", "outcome": "PASSED"}})
    out = _run_menu(app, capsys, "8", CLIENT_REF, "4", "1", "0", "0")   # no y/n is asked
    assert "This assessment's archive record is damaged, so it cannot be changed." in out
    assert "(archive state unreadable)" in out


def test_an_archive_that_could_not_be_saved_says_it_was_not_archived(app, monkeypatch, capsys):
    _history_client(app)
    monkeypatch.setattr(app.assessments(), "_write_all", lambda records: False)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "4", "1", "y", "", "0", "0")
    assert "The assessment was not archived because saving failed. Please try again later." in out
    assert "Assessment archived." not in out
    assert App.archive_state(app.assessments().find("A2")) == App.ARCHIVE_ACTIVE


def test_a_restore_that_could_not_be_saved_says_it_was_not_restored(app, monkeypatch, capsys):
    _history_client(app)
    app.archive_assessment("A1")
    monkeypatch.setattr(app.assessments(), "_write_all", lambda records: False)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "4", "2", "y", "0", "0")
    assert "The assessment was not restored because saving failed. Please try again later." in out


def test_archiving_when_the_saved_assessments_cannot_be_read_gives_the_safe_message(app, monkeypatch, capsys, caplog):
    _history_client(app)

    def broken(*args, **kwargs):
        raise OSError("disk problem")
    monkeypatch.setattr(app.assessments(), "archive", broken)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "4", "1", "y", "", "0", "0")
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
    out = _run_menu(app, capsys, "8", CLIENT_REF, "4", "1", "y", "", "0", "0")
    assert message in out and "Assessment archived." not in out


def test_menu_5_can_archive_an_assessment_and_back_out(app, monkeypatch, capsys):
    _history_client(app)
    out = _run_menu(app, capsys, "5", "1", "2", "1", "y", "no longer needed", "0")
    assert "Assessment archived." in out
    states = [App.archive_state(app.assessments().find(f"A{n}")) for n in (1, 2)]
    assert sorted(states) == [App.ARCHIVE_ACTIVE, App.ARCHIVE_ARCHIVED]
    _run_menu(app, capsys, "5", "1", "0", "0")         # back at "What next?": nothing happens
    assert sorted(App.archive_state(app.assessments().find(f"A{n}")) for n in (1, 2)) == sorted(states)


def test_menu_5_shows_the_incomplete_tag_for_a_saved_combined_assessment(app, monkeypatch, capsys):
    saved = _saved_assessment(app)
    records = app.assessments().load()
    records[0]["report"]["header"]["incomplete"] = ["The peer benchmark"]
    assert app.assessments().save(records[0])
    out = _run_menu(app, capsys, "5", "1", "0", "0")
    assert "(incomplete)" in out and saved["client_ref"] in out


def test_with_no_clients_the_client_list_does_not_read_the_audit_log(app, tmp_path, monkeypatch, capsys):
    _damage(tmp_path, "audit_log.json")
    out = _run_menu(app, capsys, "6", "", "0")
    assert "No clients saved yet." in out
    assert App.AUDIT_UNAVAILABLE not in out


def test_a_custom_range_needs_both_dates_and_is_asked_again(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "1", "5",
                    "2026-11-12", "", "", "2026-11-12", "2026-11-10", "2026-11-12", "0", "0")
    assert out.count("Pick both a start and an end date.") == 2
    assert "Showing: All, Pick dates… (2026-11-10 to 2026-11-12)" in out
    assert "(2026-11-12 to ...)" not in out


def test_a_custom_range_ending_after_today_is_refused_and_asked_again(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "1", "5",
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
    out = _run_menu(app, capsys, "8", CLIENT_REF, "3", "0", "0", "0")
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
    out = _run_menu(app, capsys, "8", CLIENT_REF, "3", "1", "0", "0")
    assert _UNREADABLE in out and "Goodbye." in out
    assert "COMBINED ASSESSMENT" not in out and "ONBOARDING" not in out
    assert "D1" in caplog.text and "ERROR" in caplog.text


def test_a_damaged_saved_assessment_is_reported_from_menu_5_too(app, monkeypatch, capsys, caplog):
    _history_client(app, with_assessments=False)
    assert app.assessments().save({"assessment_id": "D1", "client_ref": CLIENT_REF, "kind": "combined",
                                   "verdict": {"assessed_on": "2026-11-01", "verdict": "PASSED"}})
    out = _run_menu(app, capsys, "5", "1", "1", "1", "0")
    assert _UNREADABLE in out and "Goodbye." in out
    assert "TerminalApp.__open_assessment" in caplog.text and "Traceback" in caplog.text


def test_going_back_from_the_custom_dates_returns_to_the_period_question(app, tmp_path, monkeypatch, capsys):
    _history_client(app)
    _seed_history(tmp_path)
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "1", "5", "0", "2", "0", "0")   # 0 at From, then 7 days
    assert out.count("Which period?") == 2
    assert "Showing: All, Last 7 days" in out
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "1", "5", "", "", "1", "0", "0")   # both blank, then all time
    assert out.count("Which period?") == 2 and "Showing: All, All time" in out
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "1", "5", "2026-11-10", "0", "3", "0", "0")
    assert out.count("Which period?") == 2 and "Showing: All, Last 30 days" in out


def test_todays_singapore_date_is_accepted_as_the_end_date(app, tmp_path, monkeypatch, capsys):
    from datetime import datetime, timezone
    _history_client(app)
    today = AuditFilter.singapore_day(datetime.now(timezone.utc)).isoformat()
    out = _run_menu(app, capsys, "8", CLIENT_REF, "2", "1", "5", "2026-11-01", today, "0", "0")
    assert f"(2026-11-01 to {today})" in out and "cannot be in the future" not in out


def test_a_saved_report_without_its_evidence_prints_nothing_of_the_report(app, tmp_path, monkeypatch, capsys, caplog):
    saved = _saved_assessment(app)
    records = app.assessments().load()
    del records[0]["report"]["evidence"]
    with open(tmp_path / "local database" / "ai_assessments.json", "w", encoding="utf-8") as handle:
        json.dump(records, handle)
    out = _run_menu(app, capsys, "8", saved["client_ref"], "3", "1", "0", "0")
    assert _UNREADABLE in out and "Goodbye." in out
    assert "COMBINED ASSESSMENT" not in out and "VERDICT:" not in out
    assert "TerminalApp.__open_assessment" in caplog.text and "Traceback" in caplog.text


def test_the_terminal_refuses_to_assess_when_the_settings_could_not_be_loaded(tmp_path, monkeypatch):
    import shutil
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    root = tmp_path / "root"
    shutil.copytree("config", root / "config")
    (root / "config" / "policy.json").write_text("{broken")
    application = App(ai_caller=fake_ai.caller, root=str(root), data_folder=str(tmp_path / "data"))
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(sample_case()))
    terminal = _terminal(application)
    with pytest.raises(RuntimeError, match="settings could not be loaded"):
        terminal.run_case_file(str(case_path))
    with pytest.raises(RuntimeError, match="settings could not be loaded"):
        terminal.assess_client_record(ClientRecord.from_dict(sample_case()))


def test_a_terminal_needs_an_app():
    with pytest.raises(ValueError):
        TerminalApp("not an app")


def test_start_stops_cleanly_on_ctrl_c_and_reports_an_unexpected_error_without_details(app, capsys, caplog):
    def interrupt(question=""):
        raise KeyboardInterrupt

    assert TerminalApp(app, ConsoleUI(read=interrupt)).start([]) == 130
    assert "Stopped." in capsys.readouterr().out

    def break_down(question=""):
        raise RuntimeError("secret detail")

    assert TerminalApp(app, ConsoleUI(read=break_down)).start([]) == 1
    out = capsys.readouterr().out
    assert "An unexpected error occurred" in out and "secret detail" not in out
    assert "secret detail" in caplog.text


def test_start_says_when_there_is_no_ai_key_and_still_runs_the_menu(app, capsys):
    assert TerminalApp(app, ConsoleUI(read=lambda question="": "0")).start([]) == 0
    out = capsys.readouterr().out
    assert "No OPENAI_API_KEY set: only saved AI replies can be used." in out and "Goodbye." in out


def test_start_needs_a_file_after_case(app, capsys):
    assert _terminal(app).start(["--case"]) == 1
    assert "--case needs a file path" in capsys.readouterr().out


def test_quit_says_thank_you_and_goodbye(app, capsys):
    _terminal(app, "0").run_menu()
    assert "Thank you for using Orbit. Goodbye." in capsys.readouterr().out


def _ends_after(*typed):
    """A screen that answers what is given and then reaches the end of input, as Ctrl-D does."""
    waiting = iter(typed)

    def read(question=""):
        try:
            return next(waiting)
        except StopIteration:
            raise EOFError from None

    return ConsoleUI(read=read)


@pytest.mark.parametrize("typed", [(), ("1",), ("5", "1"), ("8", "CL-1"), ("6",)])
def test_the_end_of_input_anywhere_leaves_cleanly_with_exit_code_0(app, capsys, caplog, typed):
    import logging
    with caplog.at_level(logging.INFO):
        assert TerminalApp(app, _ends_after(*typed)).start([]) == 0
    out = capsys.readouterr().out
    assert "Thank you for using Orbit. Goodbye." in out
    assert "unexpected error" not in out.lower()
    assert "reached" in caplog.text and "ERROR" not in caplog.text


def test_the_end_of_input_while_asking_for_a_client_reference_also_leaves_cleanly(app, tmp_path, capsys):
    app.clients().save(sample_case())
    code = TerminalApp(app, _ends_after("4")).start([])        # asked for a client reference, then Ctrl-D
    assert code == 0 and "Thank you for using Orbit. Goodbye." in capsys.readouterr().out


def test_the_end_of_input_inside_a_case_file_run_is_an_unexpected_error_not_a_clean_goodbye(app, tmp_path, capsys, caplog):
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(sample_case()))
    seen = []

    def write(text):
        seen.append(text)
        if "Assessing" in text:
            raise EOFError                       # something below ran out of input where no question is asked

    code = TerminalApp(app, ConsoleUI(write=write)).start(["--case", str(case_path)])
    assert code == 1
    assert not any("Thank you for using Orbit" in text for text in seen)
    assert any("unexpected error" in text.lower() for text in seen)
    assert "EOFError" in caplog.text


def test_zero_at_the_archive_reason_cancels_and_is_not_saved_as_the_reason(app, capsys):
    _history_client(app)
    asked = []
    waiting = iter(["8", CLIENT_REF, "4", "1", "y", "0", "0", "0"])

    def read(question=""):
        asked.append(question)
        return next(waiting)

    capsys.readouterr()
    TerminalApp(app, ConsoleUI(read=read)).run_menu()
    out = capsys.readouterr().out
    assert any("0 to cancel" in question for question in asked)
    assert "Nothing was archived." in out and "Assessment archived." not in out
    assert all(App.archive_state(app.assessments().find(f"A{n}")) == App.ARCHIVE_ACTIVE for n in (1, 2))
    assert app.assessments().find("A2").get("archive_log") is None
