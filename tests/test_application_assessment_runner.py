"""AssessmentRunner: one assessment from made-up AI services, including the ways a step can fail."""

import copy

from app.ai.response_cache import ResponseCache
from app.application.assessment_runner import AssessmentRunner
from app.data.document_store import DocumentStore
from app.model.config import Config
from app.model.declaration import Declaration
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
    assert "the AI service is not available right now" in failures[0][1]
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


def test_the_crime_scan_reads_the_forecasts_declaration_with_iso_jurisdictions(tmp_path):
    result, _ = _run(tmp_path)
    crime = result["crime_declaration"]
    assert isinstance(crime, Declaration)
    assert [source.source_id for source in crime.sources()] == ["S1", "S2"]
    assert [source.country for source in crime.sources()] == ["SG", "HK"]        # "Singapore", "Hong Kong"
    assert any("converted to 'SG'" in note for note in result["verdict"].notes)


def test_without_research_the_typologies_are_taken_unchecked(tmp_path):
    result, _ = _run(tmp_path, research=None)
    typologies = result["typologies"]
    assert all(isinstance(typology, Typology) and not typology.verified for typology in typologies)
    assert [typology.to_dict() for typology in typologies] == fake_ai.typologies()["sector_typologies"]


def test_failed_research_is_a_step_that_did_not_run_and_the_verdict_is_not_passed(tmp_path):
    failures = []
    result, _ = _run(tmp_path, research=None, on_failure=lambda step, reason: failures.append(step) or True)
    verdict = result["verdict"]
    research_step = AssessmentRunner.RESEARCH_STEP
    assert research_step == "The crime scan's research (sources to check the typologies)"
    assert failures == [research_step]
    assert research_step in verdict.not_run
    assert verdict.outcome != "PASSED"
    assert f"{research_step} couldn't run" in str(verdict.explanation)     # the reason a person must check
    evidence = {part["title"]: part["lines"] for part in verdict.report["evidence"]}
    assert all(line.endswith("(not checked against research)")
               for line in evidence["Sector typologies"] if not line.startswith("    "))
    assert evidence["Sector typologies"]                     # still shown, so the officer sees them


def test_the_run_stops_when_on_failure_says_stop_at_failed_research(tmp_path):
    result, _ = _run(tmp_path, research=None, on_failure=lambda step, reason: False)
    assert result is None


def test_research_that_ran_and_found_no_trusted_reports_is_not_a_failure(tmp_path):
    result, _ = _run(tmp_path, research={**fake_ai.research(), "reports": [], "api_sources": []})
    assert not any("research" in step for step in result["verdict"].not_run)
    assert result["typologies"] == []                        # nothing could be checked, so nothing is kept


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


def test_parallel_runs_never_use_the_shared_forecast_at_the_same_time(tmp_path, monkeypatch):
    """Forecast keeps the forecast it is working on while run() or honest_numbers() works, so two
    parallel runs on one runner must take turns; otherwise one client's figures could end up in the
    other client's verdict. The Forecast is slowed down here so that, without the lock, they overlap."""
    import threading
    import time
    from app.logic.forecast import Forecast
    runner, cache, _ = fake_services.runner(tmp_path)
    fake_services.save_forecast_replies(cache, sample_case())
    spans, guard = [], threading.Lock()

    def slowed(original):
        def work(self, *args):
            start = time.monotonic()
            found = original(self, *args)
            time.sleep(0.2)
            with guard:
                spans.append((start, time.monotonic()))
            return found
        return work

    for name in ("run", "honest_numbers"):
        monkeypatch.setattr(Forecast, name, slowed(getattr(Forecast, name)))
    threads = [threading.Thread(target=runner.run, args=(sample_case(),)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(spans) >= 2
    spans.sort()
    for (_, earlier_end), (later_start, _) in zip(spans, spans[1:]):
        assert later_start >= earlier_end       # the Forecast was never used by two runs at once


def test_the_files_handed_in_are_read_by_the_document_reader(tmp_path):
    """run(case, files=...): every saved document is opened and sent to the document reader; with
    no files it is never asked. Here the reader gives no answer, so the step is reported as failed."""
    runner, cache, fakes = fake_services.runner(tmp_path)
    case = sample_case()
    fake_services.save_forecast_replies(cache, case)
    runner.run(case)
    assert fakes["documents"].sources == []
    failed = []
    result = runner.run(case, files=[{"file_name": "payslip.pdf", "file_path": "data/documents/payslip.pdf"}],
                        on_failure=lambda step, error: failed.append(step) or True)
    assert len(fakes["documents"].sources) == 1
    assert failed[0] == "Reading the submitted documents"
    assert "Reading the submitted documents" in result["verdict"].not_run


def _forecast_stop_reason(tmp_path, forecast_caller):
    """Run with a forecast AI that has this caller and no saved replies; return (reason told to on_failure, notes, verdict)."""
    from app.ai.response_cache import ResponseCache
    from app.data.document_store import DocumentStore
    from tests.logic_fixtures import CONFIG
    cache = ResponseCache(str(tmp_path / "cache"))
    runner = AssessmentRunner(CONFIG, fake_services.FixedAI(fake_ai.research()), fake_services.FixedAI(fake_ai.typologies()),
                              fake_services.FixedAI(fake_ai.benchmark()), fake_services.FixedAI(None),
                              fake_services.forecast_ai(forecast_caller),
                              DocumentStore("data/documents", root=str(tmp_path)), cache)
    reasons = []
    result = runner.run(sample_case(), on_failure=lambda step, reason: reasons.append((step, reason)) or True)
    forecast_reasons = [reason for step, reason in reasons if step == "The forecast"]
    assert len(forecast_reasons) == 1
    return forecast_reasons[0], result["verdict"].notes, result["verdict"]


def test_a_forecast_reply_that_fails_its_checks_is_shown_as_plain_words_and_logged(tmp_path, caplog):
    reason, notes, verdict = _forecast_stop_reason(tmp_path, lambda prompt, schema=None, options=None: '{"bad": 1}')
    assert "could not be used, so this step did not run" in reason
    assert "reply failed checks" not in reason + " ".join(notes) + str(verdict.report)
    assert "reply failed checks" in caplog.text                       # the real details are in the log
    assert "The forecast" in verdict.not_run
    assert verdict.outcome != "PASSED"


def test_a_missing_ai_service_is_shown_as_plain_words(tmp_path):
    reason, notes, verdict = _forecast_stop_reason(tmp_path, None)
    assert "the AI service is not available right now" in reason and "," not in reason
    sentence = next(note for note in notes if note.startswith("The forecast stopped at"))
    assert ".)" not in sentence and ")." in sentence and ". ." not in sentence      # reads cleanly, no double stops
    assert "OPENAI_API_KEY" not in reason + " ".join(notes) + str(verdict.report)
    assert verdict.outcome != "PASSED"



def test_a_verdict_that_cannot_be_worked_out_is_reported_in_plain_words(tmp_path):
    policy = copy.deepcopy(fake_services.CONFIG.policy)
    del policy["verdict"]["max_documents"]                  # a setting only the verdict needs
    _, cache, _ = fake_services.runner(tmp_path)
    runner = AssessmentRunner(Config(policy, fake_services.CONFIG.vocabulary),
                              fake_services.FixedAI(fake_ai.research()), fake_services.FixedAI(fake_ai.typologies()),
                              fake_services.FixedAI(fake_ai.benchmark()), fake_services.FixedAI(None),
                              fake_services.forecast_ai(), DocumentStore("data/documents", root=str(tmp_path)),
                              cache)
    case = sample_case()
    fake_services.save_forecast_replies(cache, case)
    failures = []
    assert runner.run(case, on_failure=lambda step, reason: failures.append((step, reason)) or True) is None
    assert failures[-1] == ("Deciding the verdict", "the verdict could not be worked out")


# ----- saved replies belong to one client, and only while the client is unchanged ---------------

def _services_with(tmp_path, call):
    """A runner whose research, typology, benchmark, document and forecast services are the REAL
    ones, asking the made-up caller `call` (which counts every question). The saved replies live in
    tmp_path/cache. Returns (runner, cache). Each call is a new runner: a new run of the app."""
    from app.ai.benchmark_ai import BenchmarkAI
    from app.ai.document_ai import DocumentAI
    from app.ai.research_ai import ResearchAI
    from app.ai.response_cache import ResponseCache
    from app.ai.typology_ai import TypologyAI
    from tests.logic_fixtures import CONFIG
    cache = ResponseCache(str(tmp_path / "cache"))
    built = AssessmentRunner(CONFIG, ResearchAI("fake", call, "fake-model", 0.0, 8, 5),
                             TypologyAI("fake", call, "fake-model", 0.0, 5), BenchmarkAI("fake", call, "fake-model", 0.0),
                             DocumentAI("fake", call, "fake-model", 0.0), fake_services.forecast_ai(),
                             DocumentStore("data/documents", root=str(tmp_path)), cache)
    return built, cache


def _document(tmp_path, text="payslip: salary 9000"):
    path = tmp_path / "payslip.txt"
    path.write_text(text, encoding="utf-8")
    return [{"file_name": "payslip.txt", "file_path": str(path)}]


def _reading() -> dict:
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "documents", "marcus_lim_expected_extract.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _assess(tmp_path, case, files=None, call=None, saved_forecast=True, on_failure=None):
    """One run of the app on this case. The forecast can only be answered from its saved replies.
    Returns (result, call): call.asked lists every question the AI was asked."""
    call = call or fake_ai.caller(documents_reply=_reading())
    built, cache = _services_with(tmp_path, call)
    if saved_forecast:
        documents = fake_services.DocumentStore("data/documents", root=str(tmp_path)).read_all(files) if files else []
        if cache.load_client_replies(case["client_ref"], cache.fingerprint(case, documents)) == {}:
            fake_services.save_forecast_replies(cache, case, documents)
    result = built.run(case, files=files, on_failure=on_failure or (lambda step, reason: True))
    return result, call


def _asked(call) -> list[str]:
    return [key for key, _ in call.asked]


def test_an_unchanged_client_is_not_asked_again_at_any_step(tmp_path):
    case, files = sample_case(), _document(tmp_path)
    first, call = _assess(tmp_path, case, files)
    assert sorted(_asked(call)) == ["expected_wealth", "jobs", "reports", "sector_typologies"]
    assert first["verdict"].not_run == []
    second, again = _assess(tmp_path, case, files)
    assert again.asked == []                                   # no AI call at all
    assert second["verdict"].outcome == first["verdict"].outcome
    assert second["verdict"].not_run == []


def test_a_run_a_day_later_still_counts_as_the_same_client(tmp_path):
    case = sample_case()
    _assess(tmp_path, case)
    _, again = _assess(tmp_path, {**case, "current_date": "2026-09-25"})
    assert again.asked == []


def test_a_one_letter_change_asks_every_step_again(tmp_path):
    case, files = sample_case(), _document(tmp_path)
    _assess(tmp_path, case, files)
    changed = {**case, "name": case["name"] + "x"}
    result, call = _assess(tmp_path, changed, files, saved_forecast=False)
    asked = _asked(call)
    for step in ("jobs", "reports", "sector_typologies", "expected_wealth"):
        assert step in asked
    assert "The forecast" in result["verdict"].not_run


def test_a_changed_declaration_with_the_ai_down_does_not_reuse_the_old_forecast(tmp_path):
    """The bug: the forecast's saved replies were filed under the client's reference only, so a client
    whose declaration was rewritten still got the AI's reading of the OLD declaration, even with the AI down."""
    case = sample_case()
    first, _ = _assess(tmp_path, case)
    assert first["verdict"].not_run == []
    rewritten = {**case, "sow_declaration": "I won the lottery in 2022 and bought shares."}
    result, call = _assess(tmp_path, rewritten, call=fake_ai.caller(None, None, None), saved_forecast=False)
    verdict = result["verdict"]
    assert "The forecast" in verdict.not_run
    assert any(step.startswith("The crime scan") for step in verdict.not_run)
    assert verdict.outcome != "PASSED"
    assert result["forecast"] is None and result["crime_result"] is None


def test_a_changed_document_asks_every_step_again(tmp_path):
    case = sample_case()
    _assess(tmp_path, case, _document(tmp_path))
    result, call = _assess(tmp_path, case, _document(tmp_path, "payslip: salary 9001"), saved_forecast=False)
    asked = _asked(call)
    for step in ("jobs", "reports", "sector_typologies", "expected_wealth"):
        assert step in asked
    assert "The forecast" in result["verdict"].not_run


def test_two_clients_with_the_same_industry_and_documents_share_nothing(tmp_path):
    first = sample_case()
    second = {**first, "client_ref": "SOW-OTHER"}
    files = _document(tmp_path)
    _assess(tmp_path, first, files)
    result, call = _assess(tmp_path, second, files, saved_forecast=False)
    asked = _asked(call)
    for step in ("jobs", "reports", "sector_typologies", "expected_wealth"):
        assert step in asked
    assert "The forecast" in result["verdict"].not_run
    assert sorted(path.name for path in (tmp_path / "cache" / "clients").iterdir()) == ["SOW-2026-0142.json",
                                                                                         "SOW-OTHER.json"]


def test_a_run_that_stops_half_way_keeps_what_finished_and_the_next_run_carries_on(tmp_path):
    case, files = sample_case(), _document(tmp_path)
    stopped, call = _assess(tmp_path, case, files, call=fake_ai.caller(documents_reply=_reading(), research_reply=None),
                            on_failure=lambda step, reason: False)
    assert stopped is None                                     # the research failed and the caller stopped the run
    assert _asked(call).count("jobs") == 1
    assert (tmp_path / "cache" / "clients" / f"{case['client_ref']}.json").is_file()      # saved although it stopped
    _, again = _assess(tmp_path, case, files)
    asked = _asked(again)
    assert "jobs" not in asked                                 # the documents were already read
    assert "reports" in asked                                  # the research is asked again


def test_each_step_gets_the_clients_saved_replies_and_the_replies_are_saved_together(tmp_path):
    import json
    case = sample_case()
    _assess(tmp_path, case)
    with open(tmp_path / "cache" / "clients" / f"{case['client_ref']}.json", encoding="utf-8") as handle:
        saved = json.load(handle)
    assert set(saved["replies"]) == {"research", "typology", "benchmark", "forecast"}
    assert saved["fingerprint"] == ResponseCache(str(tmp_path / "cache")).fingerprint(case, [])
    assert "step0_declaration" in saved["replies"]["forecast"]


def test_a_client_ref_that_is_not_safe_as_a_file_name_runs_without_saving(tmp_path, caplog):
    case = {**sample_case(), "client_ref": "../escape"}
    with caplog.at_level("WARNING"):
        result, call = _assess(tmp_path, case, saved_forecast=False)
    assert result is not None
    assert "reports" in _asked(call)
    assert "not used for client" in caplog.text
    assert not (tmp_path / "cache").exists() and not (tmp_path / "escape.json").exists()


def test_a_save_that_fails_does_not_change_the_assessment(tmp_path, caplog):
    case = sample_case()
    blocker = tmp_path / "cache"
    blocker.write_text("a file, not a folder", encoding="utf-8")        # the folder cannot be made
    with caplog.at_level("WARNING"):
        result, _ = _assess(tmp_path, case, saved_forecast=False)
    assert result is not None and "could not write" in caplog.text


def _forecast_runner(tmp_path, forecast_caller=None):
    from tests.logic_fixtures import CONFIG
    cache = ResponseCache(str(tmp_path / "cache"))
    built = AssessmentRunner(CONFIG, fake_services.FixedAI(fake_ai.research()),
                             fake_services.FixedAI(fake_ai.typologies()),
                             fake_services.FixedAI(fake_ai.benchmark()), fake_services.FixedAI(None),
                             fake_services.forecast_ai(forecast_caller),
                             DocumentStore("data/documents", root=str(tmp_path)), cache)
    return built, cache


def _saved_file(tmp_path, case):
    import json
    with open(tmp_path / "cache" / "clients" / f"{case['client_ref']}.json", encoding="utf-8") as handle:
        return json.load(handle)


def test_saved_forecast_pieces_that_are_not_text_are_dropped_and_asked_again(tmp_path, caplog):
    case = sample_case()
    built, cache = _forecast_runner(tmp_path)
    replies = fake_ai.forecast_replies(case)
    damaged = {**replies, "step0_declaration": 5, "call1_markets.list": "", "call2_earnings.future_pay": None}
    cache.save_client_replies(case["client_ref"], cache.fingerprint(case, []), {"forecast": damaged})
    with caplog.at_level("WARNING"):
        result = built.run(case, on_failure=lambda step, reason: True)     # must not raise
    assert result is not None and "3 saved forecast piece(s)" in caplog.text
    assert "The forecast" in result["verdict"].not_run                     # no AI to ask again, honestly reported
    assert set(_saved_file(tmp_path, case)["replies"]["forecast"]) >= {"call1_markets.series.ECO_SG"}
    assert all(isinstance(name, str) and isinstance(reply, str) and reply
               for name, reply in _saved_file(tmp_path, case)["replies"]["forecast"].items())


def test_a_saved_forecast_that_is_not_a_set_of_pieces_counts_as_nothing_saved(tmp_path, caplog):
    case = sample_case()
    built, cache = _forecast_runner(tmp_path)
    cache.save_client_replies(case["client_ref"], cache.fingerprint(case, []), {"forecast": ["not", "a", "dict"]})
    with caplog.at_level("WARNING"):
        result = built.run(case, on_failure=lambda step, reason: True)
    assert result is not None and "not a set of pieces" in caplog.text
    assert "The forecast" in result["verdict"].not_run


def test_a_case_the_fingerprint_cannot_read_still_runs_without_saving(tmp_path, caplog):
    case = sample_case()
    case = {**case, "claims": {**case.get("claims", {}), 1: "x"}}
    built, _ = _forecast_runner(tmp_path)
    with caplog.at_level("WARNING"):
        result = built.run(case, on_failure=lambda step, reason: True)     # must not raise
    assert result is not None and "saved replies are not used" in caplog.text
    assert not (tmp_path / "cache").exists()


def test_a_stopped_forecast_keeps_the_pieces_after_the_stop_and_the_next_run_asks_only_the_missing_one(tmp_path):
    case = sample_case()
    replies = fake_ai.forecast_replies(case)
    stop_at, good = "call2_earnings.position.2", replies["call2_earnings.position.2"]
    built, cache = _forecast_runner(tmp_path)
    cache.save_client_replies(case["client_ref"], cache.fingerprint(case, []),
                              {"forecast": {**replies, stop_at: "not json"}})
    first = built.run(case, on_failure=lambda step, reason: True)          # no AI: stops at the damaged piece
    assert "The forecast" in first["verdict"].not_run
    kept = _saved_file(tmp_path, case)["replies"]["forecast"]
    assert kept["step0_declaration"] == replies["step0_declaration"]       # earlier pieces are still saved
    assert kept["call3_types.behaviour.T1"] == replies["call3_types.behaviour.T1"]   # and the ones after the stop

    asked = []

    def caller(prompt, schema=None, options=None):
        asked.append(prompt)
        return good
    again, _ = _forecast_runner(tmp_path, caller)
    result = again.run(case, on_failure=lambda step, reason: True)
    assert len(asked) == 1                                                  # only the missing piece was asked
    assert result["forecast"] is not None and "The forecast" not in result["verdict"].not_run
    assert _saved_file(tmp_path, case)["replies"]["forecast"][stop_at] == good
