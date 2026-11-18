"""AdminConsole: the admin's session on the terminal. It is driven with a ConsoleUI that reads made-up answers; the App
behind it keeps its files in a temporary folder, with a seeded audit log; the AI is not used."""

import os
import stat

import pytest

from app.application.app import App
from app.interface.admin_console import AdminConsole
from app.interface.admin_view import AdminView
from app.interface.console_ui import ConsoleUI
from app.model.audit_filter import AuditFilter
from tests.admin_session import ALL_RULES, account_named, make_app, screen, tamper, text_of
from tests.audit_files import audit_path, break_audit, seed_audit


@pytest.fixture
def app(tmp_path, monkeypatch):
    return make_app(tmp_path, monkeypatch)


def _run(application, *typed):
    """Run an admin session that types the answers given (end it with "0"). Returns everything it showed."""
    ui, shown, _, _ = screen(*typed)
    AdminConsole(application, ui, AdminView(ui), account_named(application, "admin")).run()
    return text_of(shown)


def _seed_nine_flags(tmp_path):
    lines = [("client_created", "2026-11-01T02:00:00Z", "Shareen", "SOW-1", "ok", {})]
    lines += [("assessment_run", f"2026-11-{day:02d}T16:30:00Z", "Shareen", "SOW-1", "ok",
               {"outcome": "PASSED", "assessment_id": f"A-{day}"}) for day in range(2, 10)]
    seed_audit(tmp_path, lines)


class _FailingRules:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def flags(self):
        raise ValueError("made-up rule failure")


# ----- who may open it --------------------------------------------------------------------------

def test_an_officer_account_cannot_open_the_admin_console(app):
    ui = ConsoleUI(read=lambda question="": "0")
    with pytest.raises(ValueError, match="admin"):
        AdminConsole(app, ui, AdminView(ui), account_named(app, "officer"))


def test_the_console_refuses_the_wrong_kinds_of_objects(app):
    ui = ConsoleUI(read=lambda question="": "0")
    admin = account_named(app, "admin")
    for arguments in (("app", ui, AdminView(ui), admin), (app, "ui", AdminView(ui), admin),
                      (app, ui, "view", admin), (app, ui, AdminView(ui), "admin")):
        with pytest.raises(ValueError):
            AdminConsole(*arguments)


def test_the_menu_greets_the_admin_and_signing_out_leaves(app):
    out = _run(app, "0")
    assert "Signed in as Orbit Admin (admin)." in out
    for line in ("1. Overview", "2. Open a flag", "3. A client's flags", "4. Activity log",
                 "5. Verify the audit log", "0. Sign out"):
        assert line in out


# ----- 1. the Overview --------------------------------------------------------------------------

def test_the_overview_asks_the_range_and_tab_then_shows_the_numbers(app):
    out = _run(app, "1", "4", "6", "0", "0")                 # 90 days, All, back, sign out
    assert "OVERVIEW  90 days" in out and "Flags to handle : 5" in out and "Log integrity   : Intact" in out
    assert "To handle 5  Open 5  In review 0  Following up 0  Resolved 0  All 5" in out
    assert "Flags: All" in out and "Showing 1-5 of 5   Page 1 of 1" in out


def test_the_overview_pages_forward_and_back(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, seeded=False)
    _seed_nine_flags(tmp_path)
    out = _run(application, "1", "4", "6", "1", "1", "0", "0")   # next page, previous page, back, sign out
    first, second = out.index("Showing 1-6 of 9"), out.index("Showing 7-9 of 9")
    assert first < second < out.rindex("Showing 1-6 of 9")
    assert "Page 2 of 2" in out


def test_an_overview_with_no_flags_says_so_and_is_not_an_error(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, seeded=False)
    out = _run(application, "1", "2", "1", "0", "0")         # 7 days, To handle
    assert "No flags to handle." in out and "[ERROR]" not in out


def test_a_flag_can_be_opened_from_the_overview_list_by_its_number(app):
    out = _run(app, "1", "4", "6", "1", "1", "0", "0", "0")    # open one, flag 1, no update, back, sign out
    assert "F-SHO-SOW-1-4  Verdict jump after edit" in out and "The 3 log entries behind this flag" in out


def test_an_unreadable_audit_log_gives_the_plain_message_never_an_empty_overview(app, tmp_path, caplog):
    break_audit(tmp_path)
    out = _run(app, "1", "4", "6", "0")
    assert f"[ERROR] {App.AUDIT_UNAVAILABLE}" in out
    assert "No flags" not in out and "Flags to handle" not in out and "No activity" not in out
    assert "the audit log cannot be read" in caplog.text           # the real reason is logged
    assert "ACTIVITY" not in out and "--- ADMIN" in out            # and the admin is back at the menu


def test_flags_that_cannot_be_worked_out_say_so_on_the_overview(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, rules=_FailingRules)
    out = _run(application, "1", "4", "6", "0")
    assert f"[ERROR] {App.FLAGS_UNAVAILABLE}" in out and "No flags" not in out


# ----- 2. one flag ------------------------------------------------------------------------------

def test_a_flag_is_opened_by_its_id_with_its_evidence(app):
    out = _run(app, "2", "F-HOU-SOW-1-7", "0", "0")
    assert "F-HOU-SOW-1-7  After-hours activity" in out and "Evidence" in out and "#7" in out


def test_a_typed_flag_id_that_matches_no_flag_says_no_flag_has_it_not_that_it_is_gone(app):
    out = _run(app, "2", "F-NOPE-99", "0")
    assert "No flag has the id F-NOPE-99. Check the id, or pick one from the Overview." in out
    assert App.FLAG_GONE not in out and "Evidence" not in out and "[ERROR]" not in out


def test_a_typed_flag_id_is_cleaned_before_it_is_shown(app):
    out = _run(app, "2", "F-\x1b[31mX", "0")
    assert "No flag has the id F-?[31mX." in out and "\x1b" not in out


def test_the_flag_prompt_can_be_left_with_zero(app):
    assert "Evidence" not in _run(app, "2", "0", "0")


def test_a_list_number_outside_the_list_is_asked_again(app):
    out = _run(app, "1", "4", "6", "1", "9", "2", "0", "0", "0")
    assert "Choose a number from 1 to 5, or type a flag id." in out and "F-OTH-SOW-1-3  Edited by non-owner" in out


def test_a_flag_that_cannot_be_looked_up_gives_the_plain_message(app, tmp_path):
    break_audit(tmp_path)
    out = _run(app, "2", "F-HOU-SOW-1-7", "0")
    assert f"[ERROR] {App.AUDIT_UNAVAILABLE}" in out and App.FLAG_GONE not in out


# ----- 3. a client's flags ----------------------------------------------------------------------

def test_a_clients_flags_are_listed(app):
    out = _run(app, "3", "sow-1", "0")
    assert "FLAGS FOR SOW-1  (4 flags not resolved)" in out and "F-SHO-SOW-1-4" in out


def test_a_client_with_no_flags_says_so(app):
    out = _run(app, "3", "CL-QUIET", "0")
    assert "No flags to handle for CL-QUIET." in out and "[ERROR]" not in out


def test_the_client_prompt_can_be_left_with_zero(app):
    assert "FLAGS FOR" not in _run(app, "3", "0", "0")


def test_a_clients_flags_that_cannot_be_worked_out_say_so(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, rules=_FailingRules)
    out = _run(application, "3", "SOW-1", "0")
    assert f"[ERROR] {App.FLAGS_UNAVAILABLE}" in out and "No flags to handle" not in out


# ----- 4. the activity log ----------------------------------------------------------------------
# answers: menu 4, range, groups, result, officer, client, search, order, flagged only

def _log(application, *filters, then=("0", "0")):
    return _run(application, "4", *filters, *then)


def test_the_activity_log_with_the_default_filters(app):
    out = _log(app, "4", "", "1", "0", "", "", "1", "n")
    assert "ACTIVITY LOG" in out and "10 events by 2 officers; 3 failed; 5 open flags" in out
    assert "Showing 1-10 of 10   Page 1 of 1" in out and "#10    2026-11-06 10:20  Adrian" in out


def test_the_result_filter_keeps_only_failed_or_only_ok_events(app):
    failed = _log(app, "4", "", "3", "0", "", "", "1", "n")
    assert "3 events" in failed and "Failed only" in failed and "#1     " not in failed
    ok = _log(app, "4", "", "2", "0", "", "", "1", "n")
    assert "7 events" in ok and "OK only" in ok and "0 failed" in ok


def test_the_officer_client_and_search_filters(app):
    out = _log(app, "4", "", "1", "3", "", "", "1", "n")
    assert "3 events by 1 officer" in out and "Officer: Adrian" in out
    out = _log(app, "4", "", "1", "0", "sow-1", "", "1", "n")
    assert "9 events" in out and "Client: SOW-1" in out
    out = _log(app, "4", "", "1", "0", "", "unreadable", "1", "n")
    assert "1 event by" in out and "Search: “unreadable”" in out and "#10 " in out


def test_the_group_filter_takes_numbers_and_asks_again_for_a_bad_one(app):
    out = _log(app, "4", "7", "4,9", "x", "²", "4", "1", "0", "", "", "1", "n")
    assert out.count("Enter numbers from 1 to 6 separated by commas, or press Enter for all.") == 4
    assert "Actions: Assessment" in out and "Action groups: 1. Sign-in" in out and "7 events" in out


def test_the_order_and_flagged_only_filters(app):
    out = _log(app, "4", "", "1", "0", "", "", "2", "y")
    assert "Oldest first" in out and "Flagged only" in out and "9 events" in out
    assert out.index("#2 ") < out.index("#9 ")                 # oldest first


def test_a_search_text_that_is_too_long_is_asked_again_with_the_filters_own_message(app):
    out = _log(app, "4", "", "1", "0", "", "x" * (AuditFilter.MAX_QUERY + 1), "crime", "1", "n")
    assert f"[ERROR] The search text must be printable text of at most {AuditFilter.MAX_QUERY} characters." in out
    assert "Search: “crime”" in out and "ACTIVITY LOG" in out


def test_the_officer_is_picked_from_the_list_the_web_offers_and_zero_means_everyone(app):
    names = [account.name for account in app.accounts()] + [App.TERMINAL, App.UNKNOWN]
    out = _log(app, "4", "", "1", "0", "", "", "1", "n")
    assert "  0. Everyone (no filter)" in out and all(f"  {n}. {name}" in out for n, name in enumerate(names, 1))
    assert "Officer:" not in out and "10 events by 2 officers" in out
    picked = _log(app, "4", "", "1", str(names.index("Shareen") + 1), "", "", "1", "n")
    assert "Officer: Shareen" in picked and "7 events by 1 officer" in picked
    assert "Officer: terminal" in _log(app, "4", "", "1", str(len(names) - 1), "", "", "1", "n")


def test_an_officer_number_outside_the_list_is_asked_again(app):
    out = _log(app, "4", "", "1", "99", "0", "", "", "1", "n")
    assert "[ERROR] Please enter" in out and "ACTIVITY LOG" in out


def test_custom_dates_are_asked_again_until_the_filter_accepts_them(app):
    out = _log(app, "5", "2026-13-45", "x", "2026-11-02", "", "2026-11-06", "2026-11-01",
               "2026-11-01", "2026-11-06", "", "1", "0", "", "", "1", "n")
    assert out.count("[ERROR]") == 3
    assert "The start date must look like 2026-11-15 (year-month-day)" in out
    assert AuditFilter.RULE_BOTH_DATES in out and "The start date must be on or before the end date." in out
    assert "1 November 2026 – 6 November 2026" in out and "10 events" in out


def test_custom_dates_in_the_future_are_refused(app):
    out = _log(app, "5", "2026-11-01", "2999-01-01", "2026-11-01", "2026-11-02", "", "1", "0", "", "", "1", "n")
    assert f"[ERROR] {AuditFilter.RULE_FUTURE}" in out


def test_custom_with_both_dates_blank_means_all_dates(app):
    out = _log(app, "5", "", "", "", "1", "0", "", "", "1", "n")
    assert "All dates" in out and "10 events" in out


def test_the_log_pages_at_twenty_five_and_pages_back(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, seeded=False)
    seed_audit(tmp_path, [("signed_in", f"2026-11-{1 + number // 20:02d}T0{number % 9}:00:00Z", "Adrian", "", "ok", {})
                          for number in range(30)])
    # page 1 -> Next page (1) -> page 2 -> Previous page (1, the only move that exists besides Change the filters)
    out = _log(application, "4", "", "1", "0", "", "", "1", "n", then=("1", "1", "0", "0"))
    assert out.index("Showing 1-25 of 30   Page 1 of 2") < out.index("Showing 26-30 of 30   Page 2 of 2")
    assert out.rindex("Showing 1-25 of 30   Page 1 of 2") > out.index("Showing 26-30 of 30   Page 2 of 2")


def test_the_filters_can_be_changed_after_a_page_is_shown(app):
    out = _log(app, "4", "", "1", "0", "", "", "1", "n", then=("1", "4", "", "3", "0", "", "", "1", "n", "0", "0"))
    assert out.count("ACTIVITY LOG") == 2 and "3 events" in out


def test_the_filters_can_be_left_with_zero(app):
    out = _run(app, "4", "0", "0")
    assert "ACTIVITY LOG" not in out


def test_an_empty_log_and_a_filter_matching_nothing_are_told_apart(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, seeded=False)
    assert "No activity recorded yet." in _log(application, "2", "", "1", "0", "", "", "1", "n")
    seed_audit(tmp_path, [("client_created", "2026-11-01T02:00:00Z", "Shareen", "SOW-1", "ok", {})])
    out = _log(application, "1", "", "1", "0", "", "", "1", "n")
    assert "No events match these filters." in out and "No activity recorded yet." not in out


def test_an_unreadable_log_never_reads_as_no_activity(app, tmp_path, caplog):
    break_audit(tmp_path)
    out = _log(app, "4", "", "1", "0", "", "", "1", "n", then=("0",))
    assert f"[ERROR] {App.AUDIT_UNAVAILABLE}" in out
    assert "No activity" not in out and "No events" not in out and "0 events" not in out
    assert "the audit log cannot be read" in caplog.text


def test_when_the_flags_fail_the_log_still_shows_with_the_flags_message(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, rules=_FailingRules)
    out = _log(application, "4", "", "1", "0", "", "", "1", "n")
    assert "The flags could not be worked out right now. The events below are still complete." in out
    assert "10 events" in out and "flags unknown" in out and "[ERROR]" not in out


def test_asking_for_flagged_events_when_the_flags_fail_says_the_flags_failed(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch, rules=_FailingRules)
    out = _log(application, "4", "", "1", "0", "", "", "1", "y", then=("0",))
    assert f"[ERROR] {App.FLAGS_UNAVAILABLE}" in out and App.AUDIT_UNAVAILABLE not in out


# ----- 5. verify --------------------------------------------------------------------------------

def test_verify_says_the_log_is_intact_and_writes_the_admins_line(app, tmp_path):
    out = _run(app, "5", "0")
    assert "OK: No changes found in the 10 entries." in out
    line = app.audit_log(AuditFilter("90")).events[0]
    assert line.action == "audit_verified" and line.actor == "Orbit Admin" and line.result == "ok"


def test_verify_says_which_entries_were_changed(tmp_path, monkeypatch):
    application = make_app(tmp_path, monkeypatch)
    tamper(tmp_path)
    out = _run(application, "5", "0")
    assert "WARNING: The log has been changed outside the app: entry 5 does not match." in out


def test_verify_on_an_unreadable_log_says_so(app, tmp_path):
    break_audit(tmp_path)
    out = _run(app, "5", "0")
    assert f"[ERROR] {App.AUDIT_UNAVAILABLE}" in out and "OK:" not in out


def test_verify_without_an_audit_key_says_the_log_is_not_set_up(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setenv("AUDIT_KEY", "short-secret")
    application = App(ai_caller=None, data_folder=str(tmp_path / "data"))
    out = _run(application, "5", "0")
    assert f"[ERROR] {App.AUDIT_KEY_MISSING}" in out and "AUDIT_KEY" not in out.replace(App.AUDIT_KEY_MISSING, "")


def test_a_verify_line_that_could_not_be_written_is_told(app, tmp_path):
    folder = os.path.dirname(audit_path(tmp_path))
    os.chmod(folder, stat.S_IRUSR | stat.S_IXUSR)               # the log can be read but not added to
    try:
        if os.access(folder, os.W_OK):
            pytest.skip("this account can write to a read-only folder")
        out = _run(app, "5", "0")
    finally:
        os.chmod(folder, stat.S_IRWXU)
    assert "OK: No changes found" in out and App.AUDIT_LINE_NOT_WRITTEN in out
    assert out.index(App.AUDIT_LINE_NOT_WRITTEN) < out.index("OK: No changes found")


def test_a_verify_line_that_was_written_gives_no_warning(app):
    assert App.AUDIT_LINE_NOT_WRITTEN not in _run(app, "5", "0")


# ----- who is the actor -------------------------------------------------------------------------

def test_every_pass_of_the_menu_is_a_new_request_for_the_admin(app, monkeypatch):
    started = []
    real = app.begin_request
    monkeypatch.setattr(app, "begin_request", lambda actor: started.append(actor) or real(actor))
    _run(app, "1", "0", "4", "0", "0")                              # Overview backed out of, then Activity log backed out of
    assert started == ["Orbit Admin"] * 3


def test_a_read_that_fails_is_recorded_as_the_admins(tmp_path, monkeypatch):
    """The "database unreadable" line a failed read writes belongs to the admin, not to the terminal."""
    application = make_app(tmp_path, monkeypatch)
    application.clients().save({"client_ref": "X"})            # any saved record, so a damaged file is noticed
    path = tmp_path / "local database" / "sow_cases.json"
    path.write_bytes(b"[{broken")
    application.begin_request("Orbit Admin")
    with pytest.raises(ValueError):
        application.all_clients()
    last = application.audit_log(AuditFilter("90")).events[0]
    assert last.action == "data_unavailable" and last.actor == "Orbit Admin"


# ----- typed answers never become "the audit log is unavailable" -------------------------------------------------

class _MadeUpApp(App):
    """An App whose overview or flag look-up fails with the error the test chooses."""
    overview_error: ValueError | None = None
    flag_error: ValueError | None = None

    def audit_overview(self, *args, **kwargs):
        if self.overview_error is not None:
            raise self.overview_error
        return super().audit_overview(*args, **kwargs)

    def flag_evidence(self, *args, **kwargs):
        if self.flag_error is not None:
            raise self.flag_error
        return super().flag_evidence(*args, **kwargs)


def _made_up_app(tmp_path, monkeypatch) -> _MadeUpApp:
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    seed_audit(tmp_path, ALL_RULES)
    return _MadeUpApp(ai_caller=None, data_folder=str(tmp_path))


def test_a_value_error_that_app_did_not_choose_is_an_unexpected_error_not_an_audit_log_problem(
        tmp_path, monkeypatch, caplog):
    application = _made_up_app(tmp_path, monkeypatch)
    application.overview_error = ValueError("made-up detail nobody should see")
    out = _run(application, "1", "4", "6", "0")
    assert "An unexpected error occurred" in out
    assert App.AUDIT_UNAVAILABLE not in out and "made-up detail" not in out
    assert "made-up detail nobody should see" in caplog.text and "--- ADMIN" in out


def test_a_digit_that_int_cannot_read_is_not_a_number_and_is_not_an_audit_log_problem(app):
    out = _run(app, "2", "²", "0", "0")                        # "²".isdigit() is True, int("²") raises
    assert App.AUDIT_UNAVAILABLE not in out and "unexpected" not in out
    assert "No flag has the id" in out                         # taken as a flag id, which does not exist
    out = _run(app, "1", "4", "6", "1", "²", "1", "1", "0", "0", "0")
    assert App.AUDIT_UNAVAILABLE not in out and "F-SHO-SOW-1-4  Verdict" in out


def test_a_group_number_that_int_cannot_read_is_asked_again(app):
    out = _log(app, "4", "²", "", "1", "0", "", "", "1", "n")
    assert "Enter numbers from 1 to 6" in out and App.AUDIT_UNAVAILABLE not in out and "ACTIVITY LOG" in out


def test_a_flag_number_with_no_overview_shown_says_to_show_it_first(app):
    out = _run(app, "2", "3", "F-HOU-SOW-1-7", "0", "0")
    assert "Show the Overview first to pick a flag by number, or type a flag id." in out
    assert App.FLAG_GONE not in out and "F-HOU-SOW-1-7  After-hours" in out


def test_an_error_opening_a_flag_from_the_overview_keeps_the_admin_on_that_page(tmp_path, monkeypatch):
    application = _made_up_app(tmp_path, monkeypatch)
    application.flag_error = ValueError(App.AUDIT_UNAVAILABLE)
    out = _run(application, "1", "4", "6", "1", "1", "0", "0")      # open a flag (fails), back, sign out
    assert f"[ERROR] {App.AUDIT_UNAVAILABLE}" in out
    assert out.count("OVERVIEW  90 days") == 2                       # shown again, not dropped to the menu
    assert out.index("[ERROR]") < out.rindex("OVERVIEW  90 days") < out.rindex("--- ADMIN")


def test_a_reload_that_fails_with_the_error_just_shown_is_not_shown_twice(tmp_path, monkeypatch):
    application = _made_up_app(tmp_path, monkeypatch)
    application.flag_error = ValueError(App.AUDIT_UNAVAILABLE)

    class _Reloading(type(application)):
        calls = 0

        def audit_overview(self, *args, **kwargs):
            _Reloading.calls += 1
            if _Reloading.calls > 1:                               # the first load works, the reload does not
                raise ValueError(App.AUDIT_UNAVAILABLE)
            return super().audit_overview(*args, **kwargs)

    application.__class__ = _Reloading
    out = _run(application, "1", "4", "6", "1", "1", "0")          # open a flag (fails), then sign out
    assert out.count(App.AUDIT_UNAVAILABLE) == 1 and out.rindex("--- ADMIN") > out.index(App.AUDIT_UNAVAILABLE)


def test_a_reload_that_fails_for_another_reason_is_still_shown(tmp_path, monkeypatch):
    application = _made_up_app(tmp_path, monkeypatch)
    application.flag_error = ValueError(App.AUDIT_UNAVAILABLE)

    class _Reloading(type(application)):
        calls = 0

        def audit_overview(self, *args, **kwargs):
            _Reloading.calls += 1
            if _Reloading.calls > 1:
                raise ValueError(App.FLAGS_UNAVAILABLE)
            return super().audit_overview(*args, **kwargs)

    application.__class__ = _Reloading
    out = _run(application, "1", "4", "6", "1", "1", "0")
    assert out.count(App.AUDIT_UNAVAILABLE) == 1 and out.count(App.FLAGS_UNAVAILABLE) == 1


# ----- 2b. updating a flag ----------------------------------------------------------------------

FLAG = "F-HOU-SOW-1-7"                                  # an Open flag in the seeded log
NOTE = "Asked the officer why."


def _update(application, *typed, flag=FLAG):
    """Open a flag by its id, choose "Update this flag" and type the answers; then leave the flag's menu (0) and
    sign out (0)."""
    return _run(application, "2", flag, "1", *typed, "0", "0")


def _state(application, flag=FLAG):
    ticket = application.flag(flag)
    return ticket.status, ticket.waiting_on, ticket.outcome, ticket.history[-1]["note"]


class _UpdateApp(App):
    """An App whose update_flag answers what the test chooses (or raises), and whose audit warning can be chosen."""
    answer: tuple | None = None
    error: ValueError | None = None
    warning: str = ""
    asked: list = []

    def update_flag(self, *args, **kwargs):
        self.asked.append(args)
        if self.error is not None:
            raise self.error
        return self.answer if self.answer is not None else super().update_flag(*args, **kwargs)

    def audit_failure_message(self):
        return self.warning or super().audit_failure_message()


def _update_app(tmp_path, monkeypatch, **chosen) -> _UpdateApp:
    application = _made_up_app(tmp_path, monkeypatch)
    application.__class__ = _UpdateApp
    application.asked = []
    for name, value in chosen.items():
        setattr(application, name, value)
    return application


def test_the_flag_page_offers_to_update_it_or_go_back(app):
    out = _run(app, "2", FLAG, "0", "0")
    assert "1. Update this flag" in out and "0. Back" in out and "Nothing was changed" not in out


def test_a_flag_is_moved_to_in_review_with_a_note(app):
    out = _update(app, "2", NOTE)
    assert f"{FLAG} is now In review. Saved in the audit log as entry #11." in out
    assert _state(app) == ("review", "", "", NOTE)
    assert out.count(f"{FLAG}  After-hours activity") == 2 and "In review" in out      # shown again, fresh


def test_following_up_asks_who_the_flag_waits_on(app):
    out = _update(app, "3", "3", NOTE)
    assert "Waiting on" in out and "3. IT support" in out
    assert f"{FLAG} is now Following up." in out and _state(app) == ("followup", "IT support", "", NOTE)


def test_resolving_asks_for_the_outcome(app):
    out = _update(app, "4", "2", NOTE)
    assert "Outcome" in out and "2. Fixed: the problem was corrected" in out
    assert f"{FLAG} is now Resolved." in out and _state(app) == ("resolved", "", "fixed", NOTE)


def test_reopening_needs_no_extra_question(app):
    _update(app, "4", "1", NOTE)
    out = _update(app, "1", "Reopened after a new call.")
    assert f"{FLAG} is now Open." in out and _state(app)[0] == "open"


def test_the_current_status_is_marked_and_picking_it_adds_only_a_note(app):
    out = _update(app, "1", NOTE)
    assert "1. Open (current)" in out and "Waiting on" not in out and "Outcome" not in out
    assert "Note added. Saved in the audit log as entry #11." in out and "is now" not in out
    assert _state(app) == ("open", "", "", NOTE)


def test_a_note_that_is_too_short_or_too_long_is_asked_again(app):
    ui, shown, asked, _ = screen("2", FLAG, "1", "2", "ok", "x" * 501, NOTE, "0", "0")
    AdminConsole(app, ui, AdminView(ui), account_named(app, "admin")).run()
    out = text_of(shown)
    assert "Please write a note of at least 5 characters" in out
    assert "Please keep the note to 500 characters or fewer." in out
    assert asked.count("Why (required, 5-500 characters; blank or 0 to cancel): ") == 3 and _state(app)[3] == NOTE


def test_a_note_of_exactly_five_and_of_five_hundred_characters_is_accepted(app):
    _update(app, "2", "x" * 500)
    assert _state(app)[3] == "x" * 500
    _update(app, "1", "12345")
    assert _state(app)[3] == "12345"


@pytest.mark.parametrize("typed", [
    ("0",),                                  # back at the status
    ("3", "0"),                              # back at "waiting on"
    ("4", "0"),                              # back at the outcome
    ("2", ""),                               # a blank note
    ("2", "0"),                              # 0 as the note
    ("3", "1", "0"),                         # 0 as the note after the choices
])
def test_backing_out_of_any_question_changes_nothing(app, typed):
    before = len(app.audit_log(AuditFilter("90")).events)
    out = _update(app, *typed)
    assert "Nothing was changed." in out and "Saved in the audit log" not in out
    assert len(app.audit_log(AuditFilter("90")).events) == before and _state(app)[0] == "open"


def test_an_update_is_written_in_the_admins_name(app):
    _update(app, "2", NOTE)
    event = app.audit_log(AuditFilter("90")).events[0]
    assert event.action == "flag_updated" and event.actor == "Orbit Admin"


def test_a_flag_that_is_gone_when_saving_says_it_was_not_saved(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch, answer=(None, [App.FLAG_GONE], 0))
    out = _update(application, "2", NOTE)
    assert f"[ERROR] {App.FLAG_GONE} Your update was not saved." in out and "Saved in the audit log" not in out
    assert out.count("--- ADMIN") == 2 and out.count(f"{FLAG}  After-hours") == 1      # back to the menu, no re-show


def test_several_problems_from_app_are_joined_and_say_not_saved(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch)
    application.answer = (application.flag(FLAG), ["First problem.", "Second problem."], 0)
    out = _update(application, "2", NOTE)
    assert "[ERROR] First problem. Second problem. Your update was not saved." in out


def test_no_flag_and_no_problem_from_app_is_still_shown_as_not_saved(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch, answer=(None, [], 0))
    out = _update(application, "2", NOTE)
    assert "[ERROR] That flag could not be found. Your update was not saved." in out


def test_the_not_saved_sentence_is_one_constant_of_the_console():
    assert AdminConsole.NOT_SAVED == "Your update was not saved."


def test_an_update_that_could_not_be_written_says_it_was_not_saved(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch)
    application.answer = (application.flag(FLAG), [App.FLAG_NOT_SAVED], 0)
    out = _update(application, "2", NOTE)
    assert f"[ERROR] {App.FLAG_NOT_SAVED}" in out and "Your update was not saved." in out
    assert "Saved in the audit log" not in out and out.count("Your update was not saved.") == 1


def test_a_problem_app_finds_is_shown_as_not_saved(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch)
    application.answer = (application.flag(FLAG), ["Choose a status: Open, In review, Following up or Resolved."], 0)
    out = _update(application, "2", NOTE)
    assert "[ERROR] Choose a status" in out and "Your update was not saved." in out


def test_a_log_that_cannot_be_read_when_saving_gives_the_plain_message_and_not_saved(tmp_path, monkeypatch, caplog):
    application = _update_app(tmp_path, monkeypatch, error=ValueError(App.AUDIT_UNAVAILABLE))
    out = _update(application, "2", NOTE)
    assert f"[ERROR] {App.AUDIT_UNAVAILABLE} Your update was not saved." in out
    assert "Saved in the audit log" not in out and "the audit log cannot be read" not in out
    assert out.rindex("What next?") > out.index("Your update was not saved.")      # still on the flag's menu
    assert "Update a flag failed: " + App.AUDIT_UNAVAILABLE in caplog.text and "could not be shown" not in caplog.text


def test_an_error_app_did_not_choose_is_unexpected_not_saved_and_logged(tmp_path, monkeypatch, caplog):
    application = _update_app(tmp_path, monkeypatch, error=ValueError("made-up detail nobody should see"))
    out = _update(application, "2", NOTE)
    assert "An unexpected error occurred" in out and "[ERROR] Your update was not saved." in out
    assert "made-up detail" not in out and "made-up detail nobody should see" in caplog.text


def test_a_saved_update_whose_number_cannot_be_read_back_still_says_it_was_saved(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch)
    application.answer = (application.flag(FLAG), [], 0)
    out = _update(application, "2", NOTE)
    assert "Your update was saved in the audit log." in out and "entry #" not in out and "[ERROR]" not in out


def test_an_update_that_really_cannot_be_written_shows_one_error_and_nothing_is_saved(app, tmp_path):
    folder = tmp_path / "local database"
    ui, shown, _, _ = screen("2", FLAG, "1", "2", NOTE, "0", "0")
    console = AdminConsole(app, ui, AdminView(ui), account_named(app, "admin"))
    before = len(app.audit_log(AuditFilter("90")).events)
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)                  # readable, but no new file can be made in it
    try:
        if os.access(folder, os.W_OK):
            pytest.skip("this account can write to a read-only folder")
        console.run()
    finally:
        folder.chmod(stat.S_IRWXU)
    out = text_of(shown)
    assert out.count("[ERROR]") == 1 and f"[ERROR] {App.FLAG_NOT_SAVED}" in out
    assert App.AUDIT_LINE_NOT_WRITTEN not in out and "Saved in the audit log" not in out
    assert len(app.audit_log(AuditFilter("90")).events) == before and _state(app)[0] == "open"


def test_an_update_that_is_not_valid_shows_the_flag_as_it_is_now(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch)
    application.answer = (application.flag(FLAG), ["Choose who you are waiting on."], 0)
    out = _update(application, "2", NOTE)
    assert "[ERROR] Choose who you are waiting on. Your update was not saved." in out
    assert out.count(f"{FLAG}  After-hours activity") == 2


@pytest.mark.parametrize("message", [App.FLAG_ADMIN_ONLY, App.AUDIT_KEY_MISSING, App.FLAGS_UNAVAILABLE])
def test_the_other_errors_app_can_raise_are_shown_plainly_and_not_saved(tmp_path, monkeypatch, message):
    application = _update_app(tmp_path, monkeypatch, error=ValueError(message))
    out = _update(application, "2", NOTE)
    assert f"[ERROR] {message} Your update was not saved." in out and "Saved in the audit log" not in out


def test_a_saved_update_whose_flag_cannot_be_shown_again_says_so_and_goes_back(tmp_path, monkeypatch, caplog):
    application = _update_app(tmp_path, monkeypatch)
    real = App.flag_evidence
    calls = []

    def evidence(self, *args, **kwargs):
        calls.append(1)
        if len(calls) > 1:                                    # the first look-up works, the one after the save does not
            raise ValueError(App.AUDIT_UNAVAILABLE)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(_UpdateApp, "flag_evidence", evidence)
    ui, shown, _, _ = screen("2", FLAG, "1", "2", NOTE, "0")
    AdminConsole(application, ui, AdminView(ui), account_named(application, "admin")).run()
    out = text_of(shown)
    assert "Saved in the audit log as entry #11." in out
    assert f"[ERROR] Your update was saved, but the flag can't be shown again right now. {App.AUDIT_UNAVAILABLE}" in out
    assert out.rindex("--- ADMIN") > out.index("can't be shown again")          # back at the menu, no flag menu
    assert "the flag could not be shown again after the update" in caplog.text
    assert _state(application)[0] == "review"


def test_the_audit_warning_is_shown_even_when_the_update_raised(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch, warning=App.AUDIT_LINE_NOT_WRITTEN,
                              error=ValueError(App.AUDIT_UNAVAILABLE))
    out = _update(application, "2", NOTE)
    assert out.index(App.AUDIT_LINE_NOT_WRITTEN) < out.index(App.AUDIT_UNAVAILABLE)


def test_no_warning_when_the_line_was_written(app):
    assert App.AUDIT_LINE_NOT_WRITTEN not in _update(app, "2", NOTE)


def test_the_update_is_asked_with_the_admins_name_and_the_chosen_answers(tmp_path, monkeypatch):
    application = _update_app(tmp_path, monkeypatch)
    _update(application, "4", "1", NOTE)
    flag_id, actor, status, note, waiting_on, outcome, _ = application.asked[0]
    assert (flag_id, actor, status, note, waiting_on, outcome) == (FLAG, "Orbit Admin", "resolved", NOTE, "", "legit")


def test_a_flag_can_be_updated_after_opening_it_from_the_overview(app):
    out = _run(app, "1", "4", "6", "1", "1", "1", "2", NOTE, "0", "0", "0")
    assert "F-SHO-SOW-1-4 is now In review." in out


def test_an_error_that_is_not_a_value_error_keeps_the_admin_in_the_menu(tmp_path, monkeypatch, caplog):
    application = _made_up_app(tmp_path, monkeypatch)
    application.overview_error = TypeError("made-up detail nobody should see")
    out = _run(application, "1", "4", "6", "5", "0")               # the overview fails, then verify still runs
    assert "An unexpected error occurred" in out and "made-up detail" not in out
    assert "made-up detail nobody should see" in caplog.text
    assert out.count("--- ADMIN: AUDIT AND FLAGS ---") == 3 and "VERIFY THE AUDIT LOG" in out
