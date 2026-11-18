"""AdminView: the admin screens as text. It is given real pages from an App with a seeded audit log; it prints
only through the ConsoleUI it is handed."""

import ast
import os
from datetime import datetime, timezone

import pytest

from app.interface.admin_view import AdminView
from app.interface.console_ui import ConsoleUI
from app.model.audit_filter import AuditFilter
from app.model.overview_page import OverviewPage
from tests.admin_session import make_app, screen, tamper, text_of
from tests.audit_files import break_audit, seed_audit

NOW = datetime.now(timezone.utc)


@pytest.fixture
def app(tmp_path, monkeypatch):
    return make_app(tmp_path, monkeypatch)


def test_the_overview_shows_the_numbers_the_failure_table_and_the_flags(app):
    text = AdminView().format_overview(app.audit_overview("90", "all", 1, NOW))
    assert "Flags to handle : 5  (5 not started, 0 in progress)" in text
    assert "Actions         : 10" in text and "Failures        : 3" in text
    assert "Log integrity   : Intact (10 entries checked)" in text and "No earlier data" in text
    day = next(line for line in text.splitlines() if line.strip().startswith("2026-11-06"))
    assert day.split() == ["2026-11-06", "2", "0", "1", "0", "3"]       # one line per day with failures, by kind
    assert "AI step not run" in text and "Read failed" in text
    assert "By priority: High 2, Medium 2, Low 1" in text and "Verdict jump after edit" in text
    assert "To handle 5  Open 5  In review 0  Following up 0  Resolved 0  All 5" in text
    assert "F-SHO-SOW-1-4  [High] Verdict jump after edit" in text
    assert "Showing 1-5 of 5   Page 1 of 1" in text
    assert "     System | Open | raised 2026-11-06 10:20" in text and "     Client SOW-1 | Open" in text


def test_the_overview_has_one_line_for_each_day_that_had_failures_and_counts_the_quiet_ones(app):
    text = AdminView().format_overview(app.audit_overview("90", "all", 1, NOW))
    assert "(89 days with no failures not listed)" in text or "days with no failures not listed" in text
    assert "2026-11-07" not in text


def test_the_overview_pages_through_the_flags_six_at_a_time(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, seeded=False)
    lines = [("client_created", "2026-11-01T02:00:00Z", "Shareen", "SOW-1", "ok", {})]
    lines += [("assessment_run", f"2026-11-{day:02d}T16:30:00Z", "Shareen", "SOW-1", "ok",
               {"outcome": "PASSED", "assessment_id": f"A-{day}"}) for day in range(2, 10)]
    seed_audit(tmp_path, lines)
    view = AdminView()
    assert "Showing 1-6 of 9   Page 1 of 2" in view.format_overview(application.audit_overview("90", "all", 1, NOW))
    assert "Showing 7-9 of 9   Page 2 of 2" in view.format_overview(application.audit_overview("90", "all", 2, NOW))


def test_an_overview_with_no_flags_says_so_plainly(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, seeded=False)
    text = AdminView().format_overview(application.audit_overview("7", "handle", 1, NOW))
    assert "No flags to handle." in text and "No open flags in this range." in text
    assert "No failures in these 7 days." in text and "0 flags   Page 1 of 1" in text


def test_an_empty_tab_says_there_are_no_flags_there(app):
    view = AdminView()
    assert "No flags here." in view.format_overview(app.audit_overview("90", "review", 1, NOW))
    assert "Nothing resolved yet." in view.format_overview(app.audit_overview("90", "resolved", 1, NOW))


def test_a_changed_log_is_flagged_on_the_overview(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch)
    tamper(tmp_path)
    text = AdminView().format_overview(application.audit_overview("90", "all", 1, NOW))
    assert "Entry #5 was changed outside the app" in text
    assert "Log integrity   : Changed outside the app at entry #5" in text


def test_a_flag_shows_what_happened_the_evidence_and_its_activity(app):
    ticket, evidence, entries = app.flag_evidence("F-SHO-SOW-1-4", NOW)
    text = AdminView().format_flag(ticket, evidence, entries)
    assert text.startswith("F-SHO-SOW-1-4  Verdict jump after edit")
    assert "Priority : High" in text and "Status   : Open" in text and "Client   : SOW-1" in text
    assert "Raised   : 2026-11-02 11:05 (Singapore time)" in text
    assert "claims.declared_net_worth: 2000000 -> 3500000" in text
    assert "The 3 log entries behind this flag (#2 #3 #4):" in text
    assert "#3     2026-11-02 11:00  Adrian" in text
    assert "System" in text and "Opened automatically by the rule." in text


def test_a_flag_whose_evidence_cannot_be_read_says_how_many_entries_are_missing(app):
    ticket, evidence, entries = app.flag_evidence("F-SHO-SOW-1-4", NOW)
    text = AdminView().format_flag(ticket, evidence[:1], entries)
    assert "2 entries behind this flag could not be read (10 entries in the log)." in text


def test_the_flags_of_one_client_and_the_empty_case(app):
    view = AdminView()
    text = view.format_client_flags("sow-1", app.client_flags("sow-1", NOW))
    assert text.startswith("FLAGS FOR SOW-1  (4 flags not resolved)") and "F-HOU-SOW-1-7" in text
    assert view.format_client_flags("NOBODY", []) == "No flags to handle for NOBODY."


def test_a_page_of_the_activity_log_shows_the_filter_the_summary_the_events_and_the_page(app):
    audit_filter = AuditFilter("90")
    text = AdminView().format_log_page(app.audit_log(audit_filter, NOW), audit_filter, NOW)
    assert "Showing: 90 days" in text and "Newest first" in text
    assert "In the last 90 days: 10 events by 2 officers; 3 failed; 5 open flags" in text
    assert "#10    2026-11-06 10:20  Adrian" in text and "[flagged]" in text
    assert "Showing 1-10 of 10   Page 1 of 1" in text


def test_the_log_filter_summary_names_each_active_filter(app):
    audit_filter = AuditFilter("30", result="failed", actor="Adrian", client_ref="sow-1", query="crime",
                               sort="asc", groups=["Assessment"], flagged_only=True)
    text = AdminView().format_log_page(app.audit_log(audit_filter, NOW), audit_filter, NOW)
    for part in ("Oldest first", "Officer: Adrian", "Actions: Assessment", "Client: SOW-1", "Failed only",
                 "Flagged only", "Search: “crime”"):
        assert part in text.splitlines()[2]


def test_an_empty_log_and_a_filter_that_matches_nothing_are_told_apart(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, seeded=False)
    view = AdminView()
    empty = AuditFilter("7")
    assert "No activity recorded yet." in view.format_log_page(application.audit_log(empty, NOW), empty, NOW)
    seed_audit(tmp_path, [("client_created", "2026-11-01T02:00:00Z", "Shareen", "SOW-1", "ok", {})])
    nothing = AuditFilter("1")
    text = view.format_log_page(application.audit_log(nothing, NOW), nothing, NOW)
    assert "No events match these filters." in text and "No activity recorded yet." not in text
    assert "Showing 0-0 of 0   Page 1 of 1" in text


def test_the_log_pages_at_twenty_five_events(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, seeded=False)
    seed_audit(tmp_path, [("signed_in", f"2026-11-{1 + number // 20:02d}T0{number % 9}:00:00Z", "Adrian", "", "ok", {})
                          for number in range(30)])
    audit_filter = AuditFilter("90", page=2)
    text = AdminView().format_log_page(application.audit_log(audit_filter, NOW), audit_filter, NOW)
    assert "Showing 26-30 of 30   Page 2 of 2" in text


def test_a_log_whose_flags_cannot_be_worked_out_still_lists_its_events_and_says_so(tmp_path, monkeypatch):
    class FailingRules:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def flags(self):
            raise ValueError("made-up rule failure")

    application = make_app(tmp_path, monkeypatch, rules=FailingRules)
    audit_filter = AuditFilter("90")
    text = AdminView().format_log_page(application.audit_log(audit_filter, NOW), audit_filter, NOW)
    assert "The flags could not be worked out right now. The events below are still complete." in text
    assert "flags unknown" in text and "10 events" in text and "[flagged]" not in text


def test_the_filters_own_problems_are_shown_on_the_page(app):
    audit_filter = AuditFilter.from_query({"preset": "yesterday"}, NOW)
    text = AdminView().format_log_page(app.audit_log(audit_filter, NOW), audit_filter, NOW)
    assert "! 'preset' must be one of 1, 7, 30, 90, custom" in text


def test_the_chain_result_when_intact_and_when_broken(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch)
    view = AdminView()
    assert view.format_chain(application.verify_audit_log("Orbit Admin")).splitlines()[-1] == \
        "OK: No changes found in the 10 entries."
    tamper(tmp_path)
    text = view.format_chain(application.verify_audit_log("Orbit Admin"))
    assert "WARNING: The log has been changed outside the app: entry 5 does not match." in text
    assert "Changed outside the app: " not in text


def test_show_methods_print_through_the_console_ui_only(app):
    ui, shown, _, _ = screen()
    view = AdminView(ui)
    view.show_overview(app.audit_overview("90", "all", 1, NOW))
    ticket, evidence, entries = app.flag_evidence("F-SHO-SOW-1-4", NOW)
    view.show_flag(ticket, evidence, entries)
    view.show_client_flags("SOW-1", app.client_flags("SOW-1", NOW))
    audit_filter = AuditFilter("90")
    view.show_log_page(app.audit_log(audit_filter, NOW), audit_filter, NOW)
    view.show_chain(app.verify_audit_log("Orbit Admin"))
    text = text_of(shown)
    for heading in ("OVERVIEW", "F-SHO-SOW-1-4  Verdict", "FLAGS FOR SOW-1", "ACTIVITY LOG", "VERIFY THE AUDIT LOG"):
        assert heading in text


def test_the_view_refuses_things_that_are_not_what_it_shows(app):
    with pytest.raises(ValueError):
        AdminView("a screen")
    view = AdminView()
    with pytest.raises(ValueError):
        view.format_overview("a page")
    with pytest.raises(ValueError):
        view.format_flag("a ticket", [], 0)
    with pytest.raises(ValueError):
        view.format_log_page("a page", AuditFilter(), NOW)
    with pytest.raises(ValueError):
        view.format_client_flags("SOW-1", "not a list")


def test_the_view_imports_neither_the_app_nor_the_logic_manager():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "interface",
                        "admin_view.py")
    with open(path, encoding="utf-8") as handle:
        modules = [node.module or "" for node in ast.walk(ast.parse(handle.read())) if isinstance(node, ast.ImportFrom)]
    assert not [m for m in modules if m.startswith(("app.application", "app.logic", "app.data", "app.ai"))]


def test_stored_text_cannot_carry_escape_or_control_characters_to_the_terminal(app, tmp_path):
    seed_audit(tmp_path, [("flag_updated", "2026-11-07T02:00:00Z", "Orbit Admin", "SOW-1", "ok",
                           {"flag_id": "F-SHO-SOW-1-4", "from": "open", "to": "review",
                            "note": "looked\x1b[31m red\nsecond line\r\x07", "waiting_on": "", "outcome": ""})])
    ticket, evidence, entries = app.flag_evidence("F-SHO-SOW-1-4", NOW)
    text = AdminView().format_flag(ticket, evidence, entries)
    lines = text.splitlines()
    assert "      looked?[31m red" in lines and "      second line" in lines    # the break makes a new line, ESC is "?"
    for char in ("\x1b", "\r", "\x07"):
        assert char not in text
    assert all(line.isprintable() for line in text.splitlines())
    audit_filter = AuditFilter("90", query="looked")
    page = app.audit_log(audit_filter, NOW)
    assert all(line.isprintable() for line in AdminView().format_log_page(page, audit_filter, NOW).splitlines())


def _note_text(app, tmp_path, note: str) -> str:
    seed_audit(tmp_path, [("flag_updated", "2026-11-07T02:00:00Z", "Orbit Admin", "SOW-1", "ok",
                           {"flag_id": "F-SHO-SOW-1-4", "from": "open", "to": "review", "note": note,
                            "waiting_on": "", "outcome": ""})])
    ticket, evidence, entries = app.flag_evidence("F-SHO-SOW-1-4", NOW)
    return AdminView().format_flag(ticket, evidence, entries)


def test_a_note_written_in_a_browser_with_windows_line_breaks_prints_as_indented_lines(app, tmp_path):
    lines = _note_text(app, tmp_path, "first line\r\n\r\nsecond line").splitlines()
    assert lines.count("      first line") == 1 and lines.count("      second line") == 1
    assert not any("?" in line for line in lines if "line" in line)


def test_the_no_flags_line_for_a_client_is_cleaned_too():
    text = AdminView().format_client_flags("SOW\x1b[31m-1", [])
    assert text == "No flags to handle for SOW?[31m-1."


def test_every_filter_code_has_a_name_for_the_menus_and_the_filter_line():
    for names, codes in ((AdminView.LOG_PRESET_NAMES, AuditFilter.PRESETS),
                         (AdminView.RESULT_NAMES, AuditFilter.RESULT_CHOICES),
                         (AdminView.SORT_NAMES, AuditFilter.SORT_CHOICES)):
        assert set(names) == set(codes) and all(names[code] for code in codes)
    assert AdminView.LOG_PRESET_NAMES["custom"] == "Custom dates"
