"""ReportView: the layout of what the officer reads."""

import pytest

from app.interface.console_ui import ConsoleUI
from app.interface.report_view import ReportView
from app.logic.benchmark import Benchmark
from app.logic.crime_scan import CrimeScan
from app.logic.document_evidence import DocumentEvidence
from app.logic.forecast import Forecast
from app.logic.verdict_engine import VerdictEngine
from app.model.client_record import ClientRecord
from tests import fake_ai
from tests.logic_fixtures import CONFIG, POLICY, sample_case, sample_forecast


def _view():
    return ReportView(ConsoleUI())


def _report():
    case = sample_case()
    forecast = sample_forecast(case)
    feature = Forecast(POLICY, CONFIG)
    assessment = feature.run(case, {"forecast": forecast})
    engine = VerdictEngine([CrimeScan(POLICY), DocumentEvidence(POLICY), Benchmark(POLICY, CONFIG), feature], CONFIG)
    return engine.combine(case, {"forecast": forecast, "forecast_assessment": assessment,
                                 "markets": forecast["markets"], "declaration": forecast["declaration"]})


def test_the_verdict_report_names_the_client_and_the_verdict():
    verdict = _report()
    text = _view().format_verdict_report(verdict)
    assert verdict.client_ref in text
    assert verdict.explanation["verdict_label"] in text
    assert verdict.next_step in text and verdict.next_review_date in text
    for part in verdict.report["sections"]:
        if part["items"] and part["title"] != "Crime - known patterns for his industry":
            assert part["title"].upper() in text


def test_the_report_is_read_from_the_verdict_object():
    verdict = _report()
    verdict.report = {**verdict.report, "header": {**verdict.report["header"], "summary": "Summary from the report."}}
    assert "Summary from the report." in _view().format_verdict_report(verdict)


def test_the_evidence_is_laid_out_under_its_titles():
    verdict = _report()
    text = _view().format_evidence(verdict)
    assert verdict.client_ref in text
    assert all(title in text for title in verdict.report["evidence_titles"])


def test_showing_a_verdict_prints_the_report_then_asks_for_the_evidence(capsys, monkeypatch):
    verdict = _report()
    asked = []
    monkeypatch.setattr("builtins.input", lambda question="": asked.append(question) or "y")
    _view().show_verdict_report(verdict)
    out = capsys.readouterr().out
    assert "COMBINED ASSESSMENT" in out and "FULL EVIDENCE  " in out
    assert out.index("FULL EVIDENCE  ") > out.index("COMBINED ASSESSMENT")
    assert any("Show the full evidence?" in question for question in asked)


def test_the_evidence_is_not_offered_when_not_asked_for(capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda question="": (_ for _ in ()).throw(AssertionError(question)))
    _view().show_verdict_report(_report(), ask_for_evidence=False)
    assert "FULL EVIDENCE  " not in capsys.readouterr().out


def test_an_empty_assessment_list_says_so():
    assert _view().format_assessment_list([]) == "No saved assessments match."


def test_the_assessment_list_shows_one_line_per_assessment():
    records = [{"client_ref": "SOW-1", "kind": "combined", "verdict": {"assessed_on": "2026-09-24", "verdict": "RISKY"}},
               {"client_ref": "SOW-2", "kind": "onboarding", "assessment": {"assessed_on": "2026-09-25", "outcome": "PASSED"}}]
    lines = _view().format_assessment_list(records).splitlines()
    assert len(lines) == 3
    assert "SOW-1" in lines[1] and ReportView.OUTCOME_LABELS["RISKY"] in lines[1]
    assert "2026-09-25" in lines[2]


def test_archived_and_damaged_assessments_are_marked_in_the_list_when_states_are_given():
    records = [{"assessment_id": "A1", "client_ref": "SOW-1", "kind": "onboarding", "assessment": {"outcome": "PASSED"}},
               {"assessment_id": "A2", "client_ref": "SOW-2", "kind": "onboarding", "assessment": {"outcome": "PASSED"}},
               {"assessment_id": "A3", "client_ref": "SOW-3", "kind": "onboarding", "assessment": {"outcome": "PASSED"}}]
    states = ["active", "archived", "unreadable"]               # one per record, in the same order
    lines = _view().format_assessment_list(records, states).splitlines()
    assert "archived" not in lines[1] and "unreadable" not in lines[1]
    assert lines[2].endswith(" (archived)")
    assert lines[3].endswith(" (archive state unreadable)")
    assert "(archived)" not in "".join(_view().format_assessment_list(records).splitlines())


def test_records_with_the_same_missing_id_each_get_their_own_mark():
    records = [{"client_ref": "SOW-1", "kind": "onboarding", "assessment": {"outcome": "PASSED"}},
               {"client_ref": "SOW-1", "kind": "onboarding", "assessment": {"outcome": "PASSED"}}]
    lines = _view().format_assessment_list(records, ["archived", "active"]).splitlines()
    assert lines[1].endswith(" (archived)")
    assert "archived" not in lines[2]


def test_showing_a_client_record_prints_through_the_console(capsys):
    record = ClientRecord.from_dict({"client_ref": "SOW-1", "name": "Daniel Tan", "nationality": "Malaysian",
                                     "career": {"occupation": "COO"}, "career_history": [], "investments": [],
                                     "claims": {}, "sow_declaration": "Salary savings."})
    assert _view().display_client_record(record) is None
    out = capsys.readouterr().out
    assert "Daniel Tan" in out and "SOW-1" in out and "Salary savings." in out


def test_a_client_record_lists_its_claim_problems_to_fix(capsys):
    record = ClientRecord.from_dict({"client_ref": "SOW-1", "name": "Daniel Tan", "nationality": "Malaysian",
                                     "career": {"occupation": "COO"}, "career_history": [], "investments": [],
                                     "claims": {"pep_status": ""}, "sow_declaration": "Salary savings."})
    _view().display_client_record(record)
    out = capsys.readouterr().out
    assert "TO FIX" in out
    assert "The PEP question is not answered" in out and "Declared net worth is missing: enter an amount greater than 0." in out


def test_a_complete_client_record_shows_nothing_to_fix(capsys):
    _view().display_client_record(ClientRecord.from_dict(sample_case()))
    assert "TO FIX" not in capsys.readouterr().out


def test_a_client_record_shows_every_job_asset_and_document(capsys):
    _view().display_client_record(ClientRecord.from_dict({**sample_case(), "supporting_documents": [
        {"file_name": "payslip.pdf", "file_id": "f1"}]}))
    out = capsys.readouterr().out
    assert "--- Job 2 ---" in out and "--- Investment 1 ---" in out
    assert "present (current job)" in out
    assert "1. payslip.pdf" in out and "File ID: f1" in out


UNNAMED = {"sources": [{"source_id": "S1", "source_type": "advisory_fees", "counterparty": None,
                        "amount_sgd": None, "occupation_mismatch": False, "jurisdiction": "HK"}]}


def _crime_scan():
    """The crime scan's own objects for the sample: the verified Typologies and the crime result."""
    scan = CrimeScan(POLICY)
    typologies = scan.verify_typology_sources(fake_ai.typologies()["sector_typologies"],
                                              scan.verify_research(fake_ai.research()))
    return typologies, scan.run(sample_case(), {"typologies": typologies, "declaration": UNNAMED})


def test_the_crime_section_is_laid_out_from_the_typology_objects():
    typologies, crime_result = _crime_scan()
    text = _view().format_verdict_report(_report(), crime_result=crime_result, typologies=typologies)
    typology = typologies[0]
    assert "CRIME - KNOWN PATTERNS FOR HIS INDUSTRY" in text
    assert "1 typologies  \u00b7  1 matched  \u00b7  0 no match" in text
    assert f"[HIGH MATCH]  {typology.name}" in text
    assert "    Core:        \u2713 Money from unnamed counterparty" in text
    assert "    Supporting:  \u2713 Source with no declared amount" in text
    assert typology.description.split(".")[0] in text                       # read from the Typology
    assert f'"{typology.source_quotes[0]["quote"]}"  [R1]' in text


def test_an_unchecked_typology_is_marked_in_the_crime_section():
    typologies, crime_result = _crime_scan()
    unchecked = CrimeScan(POLICY).read_typologies(fake_ai.typologies()["sector_typologies"])
    crime_result = CrimeScan(POLICY).run(sample_case(), {"typologies": unchecked, "declaration": UNNAMED})
    text = _view().format_verdict_report(_report(), crime_result=crime_result, typologies=unchecked)
    assert f"[HIGH MATCH]  {unchecked[0].name}  (not checked against research)" in text
    checked = _view().format_verdict_report(_report(), crime_result=_crime_scan()[1], typologies=typologies)
    assert "not checked against research" not in checked
    # the mark comes from the match's own typology, so it shows even without the typology list
    without_list = _view().format_verdict_report(_report(), crime_result=crime_result, typologies=[])
    assert "(not checked against research)" in without_list


def test_a_match_whose_typology_is_not_listed_shows_no_description_or_quote():
    typologies, crime_result = _crime_scan()
    text = _view().format_verdict_report(_report(), crime_result=crime_result, typologies=[])
    assert f"[HIGH MATCH]  {typologies[0].name}" in text
    assert typologies[0].description.split(".")[0] not in text
    assert typologies[0].source_quotes[0]["quote"] not in text


def test_the_report_is_laid_out_at_the_width_it_is_given():
    """96 characters unless another width is handed in; the crime section follows the same width."""
    typologies, crime_result = _crime_scan()
    for width in (96, 60):
        view = ReportView(ConsoleUI(), width) if width != 96 else _view()
        text = view.format_verdict_report(_report(), crime_result=crime_result, typologies=typologies)
        text += "\n" + view.format_evidence(_report())
        assert "═" * width + "\n" in text and "═" * (width + 1) not in text
        assert "  " + "─" * (width - 2) in text


@pytest.mark.parametrize("width", [19, "96"])
def test_an_impossible_report_width_is_refused(width):
    with pytest.raises(ValueError, match="the report width must be a whole number of at least 20"):
        ReportView(ConsoleUI(), width)


def test_show_client_list_says_so_when_no_clients_are_saved(capsys):
    _view().show_client_list([])
    assert "No clients saved yet." in capsys.readouterr().out


def test_show_client_list_has_a_row_for_every_client(capsys):
    _view().show_client_list([
        {"client_ref": "CL-1", "name": "Ada Tan", "career": {"industry": "Banking"}},
        {"client_ref": "CL-2", "client_profile": {"full_name": "Ben Lim", "industry": "Shipping"}}])
    shown = capsys.readouterr().out
    assert "CL-1" in shown and "Ada Tan" in shown and "Banking" in shown
    assert "CL-2" in shown and "Ben Lim" in shown and "Shipping" in shown


def test_a_report_with_parts_that_did_not_run_says_it_is_incomplete_above_the_verdict():
    verdict = _report()
    verdict.report = {**verdict.report, "header": {**verdict.report["header"],
                                                   "incomplete": ["The forecast", "The peer benchmark"]}}
    text = _view().format_verdict_report(verdict)
    assert "INCOMPLETE ASSESSMENT" in text
    assert "Did not run: The forecast; The peer benchmark." in " ".join(text.split())
    assert text.index("INCOMPLETE ASSESSMENT") < text.index("VERDICT:")


def test_a_complete_or_older_report_has_no_incomplete_warning():
    verdict = _report()
    assert "INCOMPLETE ASSESSMENT" not in _view().format_verdict_report(verdict)
    header = {key: value for key, value in verdict.report["header"].items() if key != "incomplete"}
    verdict.report = {**verdict.report, "header": header}           # saved before the field existed
    assert "INCOMPLETE ASSESSMENT" not in _view().format_verdict_report(verdict)
    verdict.report = {**verdict.report, "header": {**header, "incomplete": "damaged"}}
    assert "INCOMPLETE ASSESSMENT" not in _view().format_verdict_report(verdict)


def test_a_report_saved_before_the_field_existed_is_incomplete_when_it_lists_parts_that_could_not_run():
    verdict = _report()
    header = {key: value for key, value in verdict.report["header"].items() if key != "incomplete"}
    could_not_run = {"title": "Could not run", "items": [{"mark": "skip", "text": "The forecast", "sub": []}]}
    verdict.report = {**verdict.report, "header": header, "sections": verdict.report["sections"] + [could_not_run]}
    text = " ".join(_view().format_verdict_report(verdict).split())
    assert "INCOMPLETE ASSESSMENT" in text and "Did not run: The forecast." in text


@pytest.mark.parametrize("damaged", [{"The forecast": 1}, [""], [None], [3]])
def test_a_damaged_list_of_parts_that_did_not_run_is_logged_and_shows_no_empty_warning(damaged, caplog):
    verdict = _report()
    verdict.report = {**verdict.report, "header": {**verdict.report["header"], "incomplete": damaged}}
    assert "INCOMPLETE ASSESSMENT" not in _view().format_verdict_report(verdict)
    assert "damaged" in caplog.text


# ----- the (incomplete) tag in the assessment list ------------------------------------------------

def _combined(incomplete=None, sections=None):
    header = {"verdict": "PASSED"} if incomplete is None else {"verdict": "PASSED", "incomplete": incomplete}
    return {"assessment_id": "A1", "client_ref": "SOW-1", "kind": "combined",
            "verdict": {"assessed_on": "2026-09-24", "verdict": "PASSED"},
            "report": {"header": header, "sections": sections or []}}


def test_a_combined_assessment_with_parts_that_did_not_run_is_tagged_incomplete_in_the_list():
    lines = _view().format_assessment_list([_combined(["The forecast"]), _combined([])]).splitlines()
    assert lines[1].endswith("PASSED (incomplete)")
    assert lines[2].endswith("PASSED")


def test_the_incomplete_tag_comes_before_the_archive_mark():
    lines = _view().format_assessment_list([_combined(["The forecast"])], ["archived"]).splitlines()
    assert lines[1].endswith("PASSED (incomplete) (archived)")


def test_an_older_report_is_tagged_from_its_could_not_run_section():
    could_not_run = {"title": "Could not run", "items": [{"mark": "skip", "text": "The forecast", "sub": []}]}
    record = _combined(sections=[could_not_run])
    assert "(incomplete)" in _view().format_assessment_list([record]).splitlines()[1]


@pytest.mark.parametrize("damaged", [{"The forecast": 1}, [""], [None], "damaged"])
def test_a_damaged_list_of_parts_that_did_not_run_adds_no_tag_and_is_logged(damaged, caplog):
    text = _view().format_assessment_list([_combined(damaged)])
    assert "(incomplete)" not in text
    assert "damaged" in caplog.text


def test_a_forecast_only_record_has_no_incomplete_tag():
    records = [{"assessment_id": "A2", "client_ref": "SOW-2", "kind": "onboarding",
                "assessment": {"assessed_on": "2026-09-25", "outcome": "PASSED"}}]
    assert "(incomplete)" not in _view().format_assessment_list(records, ["archived"])


# ----- last activity in the client list -----------------------------------------------------------

def _event(action="client_edited", at="2026-11-16T06:02:11Z", actor="terminal", client="CL-1", result="ok",
           details=None):
    from app.model.audit_event import AuditEvent
    return AuditEvent(at=at, actor=actor, action=action, client_ref=client, result=result, details=details or {})


def test_the_client_list_shows_each_clients_last_activity_in_singapore_time(capsys):
    records = [{"client_ref": "CL-1", "name": "Ada Tan", "career": {"industry": "Banking"}},
               {"client_ref": "CL-2", "name": "Ben Lim", "career": {"industry": "Shipping"}}]
    _view().show_client_list(records, {"cl-1": _event()})
    lines = capsys.readouterr().out.splitlines()
    assert any("Last activity" in line for line in lines)
    row_1 = next(line for line in lines if "CL-1" in line)
    row_2 = next(line for line in lines if "CL-2" in line)
    assert "16 Nov 14:02" in row_1 and "Client edited" in row_1      # 06:02 UTC is 14:02 in Singapore
    assert row_2.rstrip().endswith("—")


def test_the_client_list_says_why_the_activity_is_missing_when_the_log_could_not_be_read(capsys):
    _view().show_client_list([{"client_ref": "CL-1", "name": "Ada Tan", "career": {"industry": "Banking"}}],
                             None, "We can't load the audit log right now.")
    out = capsys.readouterr().out
    assert "Ada Tan" in out and "We can't load the audit log right now." in out
    assert "Last activity" not in out


# ----- a client's history -------------------------------------------------------------------------

def test_a_clients_history_is_grouped_by_singapore_day_newest_first():
    events = [_event("assessment_run", "2026-11-16T17:30:00Z", "Orbit Officer", details={"outcome": "PASSED"}),
              _event("client_edited", "2026-11-16T06:02:11Z", "terminal", details={"changes": [1, 2]}),
              _event("client_created", "2026-11-15T01:00:00Z", "Orbit Officer")]
    text = _view().format_client_history(events)
    assert text.index("17 November 2026") < text.index("16 November 2026") < text.index("15 November 2026")
    assert "01:30  Assessment saved for client CL-1: PASSED  |  by Orbit Officer" in text
    assert "14:02  Edited client CL-1 (2 fields changed)  |  by terminal" in text
    assert "No history" not in text and "Nothing matches" not in text and "incomplete" not in text


def test_a_failed_event_is_shown_as_failed():
    text = _view().format_client_history([_event("assessment_failed", result="failed")])
    assert text.count("failed") == 1 and "FAILED" not in text and "|  OK" not in text


def test_a_history_says_when_entries_of_the_log_could_not_be_read():
    one = _view().format_client_history([_event()], 1, 1)
    assert "1 entry in the audit log can't be read, so this history may be incomplete." in one
    many = _view().format_client_history([_event()], 1, 3)
    assert "3 entries in the audit log can't be read, so this history may be incomplete." in many
    assert "3 entries in the audit log" in _view().format_client_history([], 0, 3)       # even with nothing else to show


def test_a_history_tells_no_history_yet_from_no_match():
    assert _view().format_client_history([], 0) == "No history recorded yet."
    assert _view().format_client_history([], 4) == 'Nothing matches these filters. Try "All" or "All time".'


def test_showing_a_history_prints_it(capsys):
    _view().show_client_history([_event()])
    assert "Edited client CL-1" in capsys.readouterr().out


# ----- damaged saved records never stop the list ------------------------------------------------

@pytest.mark.parametrize("sections", [None, 5, "text", {"a": 1}])
def test_a_damaged_sections_value_never_crashes_the_list_and_adds_no_tag(sections):
    record = _combined(sections=None)
    record["report"] = {"header": {"verdict": "PASSED"}, "sections": sections}
    assert "(incomplete)" not in _view().format_assessment_list([record])


@pytest.mark.parametrize("items", [None, 5, "text", {"a": 1}])
def test_a_damaged_items_value_never_crashes_the_list_and_adds_no_tag(items):
    record = _combined(sections=[{"title": "Could not run", "items": items}])
    assert "(incomplete)" not in _view().format_assessment_list([record])


@pytest.mark.parametrize("sections, items", [(None, None), (5, None), ("x", None), ([{"title": "Could not run", "items": None}], None)])
def test_a_damaged_report_does_not_crash_the_verdict_report_either(sections, items):
    verdict = _report()
    header = {key: value for key, value in verdict.report["header"].items() if key != "incomplete"}
    verdict.report = {**verdict.report, "header": header, "sections": sections}
    # the report body needs its sections, so only the "what did not run" part is checked
    assert ReportView._ReportView__missing_parts(verdict.report) == []


@pytest.mark.parametrize("change", [
    {"verdict": "damaged"}, {"verdict": {"assessed_on": None, "verdict": "PASSED"}},
    {"verdict": {"assessed_on": 5, "verdict": "PASSED"}}, {"kind": None}, {"client_ref": 7}, {"client_ref": None},
    {"verdict": ["x"]}, {"verdict": None, "assessment": "bad"}])
def test_a_damaged_saved_record_shows_question_marks_and_is_logged_without_stopping_the_list(change, caplog):
    good = {"client_ref": "SOW-2", "kind": "onboarding", "assessment": {"assessed_on": "2026-09-25", "outcome": "PASSED"}}
    bad = {**_combined(), **change}
    lines = _view().format_assessment_list([bad, good]).splitlines()
    assert len(lines) == 3 and "SOW-2" in lines[2] and "PASSED" in lines[2]
    assert "?" in lines[1] and "damaged" in caplog.text


def test_a_saved_record_without_its_reference_or_kind_is_shown_with_question_marks():
    lines = _view().format_assessment_list([{"assessment": {"assessed_on": "2026-09-25", "outcome": "PASSED"}}])
    assert lines.splitlines()[1].startswith("?")


def test_a_row_that_is_not_a_record_is_shown_as_unknown():
    assert len(_view().format_assessment_list(["junk", None]).splitlines()) == 3


# ----- long values, and one row for the list and for picking --------------------------------------

def test_a_long_name_or_industry_is_cut_with_an_ellipsis_and_never_runs_into_the_next_column(capsys):
    record = {"client_ref": "CL-1", "name": "Marcus Lim Wei Jie test test eddit more",
              "career": {"industry": "Industrial parts distribution and more"}}
    _view().show_client_list([record], {"cl-1": _event()})
    row = next(line for line in capsys.readouterr().out.splitlines() if "CL-1" in line)
    name_start = row.index("Marcus")
    assert row[name_start + 27] == " " and "…" in row[name_start:name_start + 27]
    industry_start = name_start + 28
    assert row[industry_start:industry_start + 20].endswith("… ")
    assert "16 Nov 14:02" in row and "distribution16" not in row.replace(" ", "")


def test_a_short_value_is_not_cut(capsys):
    _view().show_client_list([{"client_ref": "CL-1", "name": "Ada Tan", "career": {"industry": "Banking"}}])
    assert "…" not in capsys.readouterr().out


def test_the_row_used_for_picking_is_the_row_of_the_list_and_tells_assessments_apart():
    first = {**_combined(["The forecast"]), "verdict": {"assessed_on": "2026-09-24", "verdict": "RISKY"}}
    second = {**_combined([]), "verdict": {"assessed_on": "2026-09-25", "verdict": "PASSED"}}
    rows = [ReportView.format_assessment_row(first, "archived").rstrip(), ReportView.format_assessment_row(second)]
    assert rows[0] != rows[1]
    assert "2026-09-24" in rows[0] and "RISKY (incomplete) (archived)" in rows[0]
    assert _view().format_assessment_list([first, second], ["archived", ""]).splitlines()[1:] == \
        [ReportView.format_assessment_row(first, "archived"), ReportView.format_assessment_row(second)]


# ----- the assessment id on each row ------------------------------------------------------------

def test_the_list_has_an_assessment_id_column_between_date_and_outcome():
    record = {**_combined(["The forecast"]), "assessment_id": "a72de5e5-1111-2222-3333-444455556666"}
    head, row = _view().format_assessment_list([record], ["archived"]).splitlines()
    assert head.split() == ["Client", "Kind", "Date", "Assessment", "ID", "Outcome"]
    assert head.index("Assessment ID") > head.index("Date") and head.index("Outcome") > head.index("Assessment ID")
    assert row.split()[:5] == ["SOW-1", "combined", "2026-09-24", "a72de5e5", "PASSED"]
    assert "a72de5e5-" not in row and row.endswith("PASSED (incomplete) (archived)")


def test_a_pick_line_labels_the_assessment_id():
    record = {**_combined(), "assessment_id": "a72de5e5-1111"}
    line = ReportView.format_assessment_row(record, "", labelled=True)
    assert "Assessment ID a72de5e5" in line and line.rstrip().endswith("PASSED")


@pytest.mark.parametrize("bad", [None, "", "   ", 5, ["x"]])
def test_a_record_without_a_usable_id_says_so_and_never_invents_one(bad):
    record = {**_combined(), "assessment_id": bad}
    assert "no ID" in ReportView.format_assessment_row(record)
    assert "Assessment ID: none" in ReportView.format_assessment_row(record, labelled=True)
    assert "no ID" in _view().format_assessment_list([record])
    del record["assessment_id"]
    assert "no ID" in ReportView.format_assessment_row(record)


def test_a_long_reference_still_finds_its_last_activity(capsys):
    ref = "CL-" + "X" * 20
    _view().show_client_list([{"client_ref": ref, "name": "Ada Tan", "career": {"industry": "Banking"}}],
                             {ref.casefold(): _event(client=ref[:40])})
    row = next(line for line in capsys.readouterr().out.splitlines() if "CL-X" in line)
    assert "…" in row and "16 Nov 14:02" in row and not row.rstrip().endswith("—")


def test_a_long_client_reference_or_kind_is_cut_so_the_columns_stay_in_place():
    record = {**_combined(), "client_ref": "CL-" + "X" * 30, "kind": "k" * 40, "assessment_id": "abcdef123456"}
    row = ReportView.format_assessment_row(record)
    assert row.index("2026-09-24") == 16 + 1 + 20 + 1 and "abcdef12" in row
    assert row.count("…") == 2


def test_a_damaged_onboarding_record_shows_nothing_and_raises_before_printing(capsys):
    with pytest.raises((KeyError, TypeError)):
        _view().show_onboarding({"outcome": "PASSED"})
    assert capsys.readouterr().out == ""


def test_a_history_line_cannot_carry_escape_characters_to_the_terminal():
    event = _event(action="document_uploaded", details={"file_id": "id\x1b[31m\u202e-1\n"})
    text = _view().format_client_history([event])
    assert "id?[31m?-1?" in text and "\x1b" not in text and "\u202e" not in text
    assert all(line.isprintable() for line in text.splitlines())

