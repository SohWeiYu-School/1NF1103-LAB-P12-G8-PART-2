"""
Tests for the combined assessment: the documents, the crime scan, the forecast and the benchmark
working as ONE feature with ONE verdict, (the command line and the web app
are compared in test_application_cli_and_web.py).

No API key and no network: every test runs a real App whose AI is a made-up caller
(tests/fake_ai.caller); the forecast runs on made-up saved replies through its real checks.
"""

import copy
import datetime
import json
import logging
import os
from unittest.mock import patch

import pytest

from app.ai import forecast_ai as forecast_ai_module
from app.ai.ai_caller import openai_caller
from app.ai.benchmark_ai import BenchmarkAI
from app.ai.document_ai import DocumentAI
from app.ai.forecast_ai import ForecastAI
from app.ai.response_cache import ResponseCache
from app.application.app import App
from app.data.document_store import DocumentStore
from app.logic.benchmark import Benchmark
from app.logic.career_savings import CareerSavings
from app.logic.case_reader import CaseReader
from app.logic.crime_scan import CrimeScan
from app.logic.document_record_builder import DocumentRecordBuilder
from app.logic.forecast import Forecast
from app.logic.verdict_engine import VerdictEngine
from app.model.declaration import Declaration
from app.model.verdict import Verdict
from tests import fake_ai, fake_services
from tests.logic_fixtures import CONFIG, POLICY, sample_case

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEVERITY = Verdict.SEVERITY


class Run:
    """Runs assessments through a real App whose AI is a made-up caller (fake_ai.caller).
    Everything it saves goes to a temporary folder."""

    def __init__(self, folder) -> None:
        self.folder = folder

    def app(self, **replies) -> App:
        caller = fake_ai.caller(**replies)
        self.last_caller = caller                       # the made-up AI, so a test can read what it was asked
        return App(caller, data_folder=str(self.folder))

    def save_fake_forecast(self, record: dict, **options) -> dict:
        """Save made-up forecast replies for this client, as if the AI had answered before."""
        case, missing = CaseReader(self.app().today()).forecasting_case(record)
        assert missing == []
        application = self.app()
        documents = application.documents().read_all(record.get("supporting_documents") or [])
        fake_services.save_forecast_replies(application.response_cache(), case, documents, **options)
        return case

    def cache(self) -> ResponseCache:
        return self.app().response_cache()

    def __call__(self, case: dict, benchmark=None, typologies=None, documents=None, **replies) -> dict:
        if benchmark is not None:
            replies["benchmark_reply"] = benchmark
        if typologies is not None:
            replies["typologies_reply"] = typologies
        application = self.app(**replies)
        return application.assess(case, documents, show_failures=False)


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setattr(forecast_ai_module.time, "sleep", lambda seconds: None)   # no waiting between retries
    return Run(tmp_path)


def client_record(**claims) -> dict:
    record = sample_case()
    record["claims"].update({"biggest_wealth_jump": 3_000_000, "wealth_jump_years": 2,
                             "declared_counterparties": ["Straits Harbour Logistics Pte Ltd"], **claims})
    return record


def check(verdict: dict, feature: str, name: str) -> dict:
    return next(c for c in verdict[feature] if c["check"] == name)


# ---------------------------------------------------------------------------
# One verdict from all three features
# ---------------------------------------------------------------------------

def test_one_verdict_with_reasons_from_every_feature(run):
    case = run.save_fake_forecast(client_record())
    result = run(case)
    assert isinstance(result["verdict"], Verdict)        # the object, carrying its report
    verdict = result["verdict"].details()
    assert verdict["verdict"] in ("PASSED", "MANUAL_REVIEW", "RISKY", "SERIOUS_RISK")
    assert verdict["reasons"], "the verdict must say why"
    assert {c["feature"] for c in verdict["benchmark"]} == {"benchmark"}
    assert verdict["forecast"] and verdict["crime"]
    assert verdict["not_run"] == []
    titles = [s["title"] for s in result["verdict"].report["sections"]]
    assert titles[0] == "Why"
    assert any(t.startswith("Benchmark") for t in titles) and any(t.startswith("Forecast") for t in titles)
    assert any(t.startswith("Crime") for t in titles)


def test_crime_type_is_built_from_the_researched_typology(run):
    case = run.save_fake_forecast(client_record())
    verdict = run(case)["verdict"].details()
    t2 = next(t for t in verdict["types"] if t["type_id"] == "T2")
    assert t2["typology_id"] == "trade_based_laundering"
    assert t2["match"] == "high"                      # its warning signs fired in the declaration
    t3 = next(t for t in verdict["types"] if t["type_id"] == "T3")
    assert t3["typology_id"] is None                  # no researched pattern behind it
    assert any(c["check"] == "UNBACKED_TYPE" and c["label"].startswith("T3") for c in verdict["crime"])


def test_serious_risk_needs_the_honest_story_to_fail_and_a_second_feature(run):
    # tiny honest pay, big crime money: only T2 explains him, and its warning signs fired
    case = run.save_fake_forecast(client_record(), pay_scale=0.2, crime_money=900_000)
    verdict = run(case)["verdict"].details()
    assert verdict["verdict"] == "SERIOUS_RISK"
    assert "another check agrees" in verdict["summary"]


def test_without_a_second_feature_it_stays_risky(run):
    # same money, but the pattern's warning signs can't fire and the benchmark finds nothing unexplained
    case = run.save_fake_forecast(client_record(), pay_scale=0.2, crime_money=900_000)
    quiet = fake_ai.typologies()
    quiet["sector_typologies"][0]["indicators"] = [{"indicator": "related_party_transaction", "weight": "core"},
                                                   {"indicator": "gift_or_inheritance_unnamed", "weight": "supporting"}]
    peers = fake_ai.benchmark(expected_wealth=20_000_000)
    peers.update(expected_velocity=5_000_000, expected_counterparties=["Straits Harbour Logistics Pte Ltd"],
                 expected_jurisdiction=["Singapore", "Hong Kong", "United Arab Emirates"])
    verdict = run(case, benchmark=peers, typologies=quiet)["verdict"].details()
    assert verdict["verdict"] == "RISKY"
    assert "no other check agrees" in verdict["summary"]


def test_a_benchmark_failure_the_forecast_explains_does_not_count(run):
    case = run.save_fake_forecast(client_record())
    verdict = run(case)["verdict"].details()                    # peers have ~2.4M, he declares 16.5M
    total = check(verdict, "benchmark", "TOTAL_WEALTH")
    assert total["status"] == "explained"            # ...but the honest forecast reaches it
    assert total["explanation"].startswith("Explained")
    assert all("total wealth" not in r["text"].lower() for r in verdict["reasons"])


def test_new_benchmark_checks_are_there(run):
    case = run.save_fake_forecast(client_record())
    verdict = run(case)["verdict"].details()
    names = {c["check"] for c in verdict["benchmark"]}
    assert {"PEP_STATUS", "AUM_FUNDING", "UNEXPLAINED_GAP", "JUMP_VS_ECONOMY"} <= names
    assert {"WEALTH_JUMP", "LIQUID_WEALTH"} <= {c["check"] for c in verdict["forecast"]}


def test_a_pep_is_never_passed(run):
    case = run.save_fake_forecast(client_record(pep_status="Foreign PEP"))
    verdict = run(case)["verdict"].details()
    assert check(verdict, "benchmark", "PEP_STATUS")["status"] == "failed"
    assert SEVERITY[verdict["verdict"]] >= SEVERITY["MANUAL_REVIEW"]
    assert any("PEP" in r["text"] for r in verdict["reasons"])


def test_a_blank_pep_answer_is_never_passed_and_says_why(run):
    answered = run(run.save_fake_forecast(client_record(pep_status="None")))["verdict"].details()
    case = run.save_fake_forecast(client_record(pep_status="None"))
    case["claims"]["pep_status"] = ""        # a case that reaches the engine with the question unanswered
    blank = run(case)["verdict"].details()
    assert check(answered, "benchmark", "PEP_STATUS")["status"] == "passed"
    assert check(blank, "benchmark", "PEP_STATUS")["status"] == "skipped"
    assert SEVERITY[blank["verdict"]] >= SEVERITY["MANUAL_REVIEW"]
    assert any("PEP status is not answered" in r["text"] for r in blank["reasons"])
    assert not any("PEP status is not answered" in r["text"] for r in answered["reasons"])


def test_money_for_the_bank_he_cant_fund_is_risky(run):
    case = run.save_fake_forecast(client_record(expected_aum=30_000_000))
    verdict = run(case)["verdict"].details()
    assert check(verdict, "benchmark", "AUM_FUNDING")["status"] == "failed"
    assert SEVERITY[verdict["verdict"]] >= SEVERITY["RISKY"]


def test_a_part_that_cant_run_means_a_person_must_look(run):
    case = run.save_fake_forecast(client_record())
    verdict = run(case, benchmark_reply=None)["verdict"].details()
    assert "The peer benchmark" in verdict["not_run"]
    assert SEVERITY[verdict["verdict"]] >= SEVERITY["MANUAL_REVIEW"]
    # the checks that don't need the peer benchmark still run
    assert check(verdict, "benchmark", "UNEXPLAINED_GAP")["status"] in ("passed", "failed")


def test_same_inputs_give_the_same_verdict(run):
    case = run.save_fake_forecast(client_record())
    assert run(case)["verdict"].report == run(case)["verdict"].report


# ---------------------------------------------------------------------------
# The pieces that link the features
# ---------------------------------------------------------------------------

def test_cli_record_without_the_current_job_in_history_gives_a_case():
    record = client_record()
    history = record["career_history"]
    record["career_history"] = history[:-1]           # the command line keeps the current job in "career"
    case, missing = CaseReader("2026-10-14").forecasting_case(record)
    assert missing == []
    assert case["career_history"][-1]["end_year"] is None
    assert case["career_history"][-1]["start_year"] == history[-2]["end_year"]
    assert case["current_date"] == "2026-10-14"


def test_incomplete_record_says_what_is_missing():
    record = client_record()
    record["claims"]["declared_net_worth"] = ""
    case, missing = CaseReader("2026-10-14").forecasting_case(record)
    assert case is None and "declared net worth" in missing


def test_declaration_is_read_once_and_reused_by_the_crime_scan():
    declaration = json.loads(fake_ai.forecast_replies(client_record() | {"current_date": "2026-10-14"})
                             ["step0_declaration"])
    rows, warnings = CrimeScan(POLICY).crime_declaration(Declaration.from_dict(declaration))
    salary, advisory = rows.to_scan_dict()["sources"]
    assert salary["amount_explained_by_forecast"] is True      # the forecast works out what the job paid
    assert advisory["counterparty"] is None and advisory["amount_explained_by_forecast"] is False
    assert warnings == []


def test_old_saved_declaration_without_counterparties_does_not_count_as_unnamed():
    old = {"claimed_sources": [{"source_id": "S1", "source_type": "other", "description": "x", "start_year": None,
                                "end_year": None, "amount": None, "country": "Singapore",
                                "linked_position_index": None, "linked_asset_index": None, "quote": "x"}]}
    rows, warnings = CrimeScan(POLICY).crime_declaration(Declaration.from_dict(old))
    assert rows.to_scan_dict()["sources"][0]["counterparty"] == "(not read)"
    assert warnings


def test_person_types_are_linked_to_typologies_by_id_or_category():
    researched = [{"typology_id": "tbml", "crime_category": "TRADE_BASED_ML"},
                  {"typology_id": "bribes", "crime_category": "BRIBERY_CORRUPTION"}]
    data = {"person_types": [{"type_id": "T1", "category": "HONEST", "typology_id": None},
                             {"type_id": "T2", "category": "TRADE_BASED_ML", "typology_id": "made_up"},
                             {"type_id": "T3", "category": "TAX_EVASION", "typology_id": "bribes"}]}
    linked = fake_services.forecast_ai()._link_typologies(data, researched)["person_types"]
    assert linked[1]["typology_id"] == "tbml"                  # unknown id -> linked by its category
    assert linked[2]["typology_id"] == "bribes"
    assert linked[2]["category"] == "BRIBERY_CORRUPTION"      # takes its typology's category


def test_person_types_request_gets_the_typologies():
    case, _ = CaseReader("2026-10-14").forecasting_case(client_record())
    replies = fake_ai.forecast_replies(case)
    with patch.object(ForecastAI, "_ask", autospec=True, side_effect=ForecastAI._ask) as spy:
        run_result = fake_services.forecast_ai().run(
            {"record": case, "cache": replies, "typologies": fake_ai.typologies()["sector_typologies"]})
    assert run_result["ok"]
    sent = next(c.args[4] for c in spy.call_args_list if c.args[1] == "call3_types.list")
    assert sent["researched_typologies"][0]["typology_id"] == "trade_based_laundering"
    assert sent["researched_typologies"][0]["crime_category"] == "TRADE_BASED_ML"


def test_benchmark_sees_the_economy_but_never_his_figures():
    economy = {"markets": [{"name": "Container shipping", "country": "World", "indicator": "freight index",
                            "yearly_change_pct": {"2020": -12.0}}], "country_listings": []}
    data = {"occupation": "COO", "industry": "Shipping", "age": 51, "career_start_year": 1998,
            "country": "Singapore", "declared_net_worth": 16_500_000, "cash": 20}
    prompts = []

    def caller(prompt, schema, options):
        prompts.append(prompt)
        return json.dumps(fake_ai.benchmark())

    assert BenchmarkAI("fake", caller, "fake", 0.0).run({"client": data, "economy": economy}) is not None
    prompt = prompts[0]
    assert "Container shipping" in prompt and "-12.0" in prompt
    assert "16500000" not in prompt and "declared_net_worth" not in prompt
    assert "prompt_version" not in prompt                      # notes in the prompt file aren't sent


def test_economy_brief_has_no_client_figures():
    case, _ = CaseReader("2026-10-14").forecasting_case(client_record())
    replies = fake_ai.forecast_replies(case)
    markets = {**json.loads(replies["call1_markets.list"]), "series": {
        m: json.loads(replies[f"call1_markets.series.{m}"]) for m in ("ECO_SG", "IND_SHIP", "PROP_SG", "FX_AUD")}}
    brief = Forecast(POLICY, CONFIG).economy_brief(markets)
    text = json.dumps(brief)
    assert "Singapore economy" in text
    for figure in ("16500000", "5000000", "declared"):
        assert figure not in text


def test_typology_schema_requires_a_crime_category(tmp_path):
    with open(os.path.join(ROOT, "app", "schemas", "typology_response.schema.json"), encoding="utf-8") as handle:
        schema = json.load(handle)
    assert "crime_category" in schema["properties"]["sector_typologies"]["items"]["required"]
    runner, cache, services = fake_services.runner(tmp_path)
    case = sample_case()
    fake_services.save_forecast_replies(cache, case)
    runner.run(case)
    categories = services["typologies"].sources[0]["categories"]
    assert "HONEST" not in categories and "TRADE_BASED_ML" in categories


# ---------------------------------------------------------------------------
# The documents layer, pay from documents, and the report layout
# ---------------------------------------------------------------------------

MARCUS = os.path.join(os.path.dirname(__file__), "documents", "marcus_lim")


def marcus() -> tuple[dict, dict]:
    """The Marcus Lim specimen: (client record as the form saves it, the correct reading of his documents)."""
    with open(MARCUS + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    builder = DocumentRecordBuilder(CONFIG, datetime.date.today().isoformat())   # assessments are dated today
    record, _, _ = builder.build(reading, "CL-MARCUS")
    record = builder.finish(builder.set_path(record, ["investments", 2, "income_produced"], 0)).to_dict()
    record["supporting_documents"] = [{"file_name": os.path.basename(path), "file_path": path}
                                      for path in DocumentStore().list_folder(MARCUS)]
    return record, reading


def quiet_peers() -> tuple[dict, dict]:
    """A benchmark and typologies that find nothing, so only the documents can add evidence."""
    peers = fake_ai.benchmark(expected_wealth=14_000_000)
    peers.update(expected_velocity=5_000_000, expected_counterparties=["Straits Harbour Logistics Pte Ltd"],
                 expected_jurisdiction=["Singapore"])
    quiet = fake_ai.typologies()
    quiet["sector_typologies"][0]["indicators"] = [{"indicator": "related_party_transaction", "weight": "core"},
                                                   {"indicator": "gift_or_inheritance_unnamed", "weight": "supporting"}]
    return peers, quiet


def run_marcus(run: Run, record: dict, reading: dict, benchmark=None, typologies=None, **options) -> dict:
    case = run.save_fake_forecast(record, **options)
    result = run(case, benchmark, typologies, record["supporting_documents"], documents_reply=reading)
    caller = run.last_caller
    sent = [options for key, options in caller.asked if key == "jobs"][0]["parts"]
    documents = [part for part in sent if part["type"] == "text" and part["text"].startswith("<document")]
    assert len(documents) == 9                                     # every document is read, as text
    return result


def test_marcus_lim_documents_make_it_serious_risk(run):
    record, reading = marcus()
    record["claims"]["expected_aum"] = 3_000_000     # fundable, so only the documents can add evidence
    peers, quiet = quiet_peers()
    verdict = run_marcus(run, record, reading, peers, quiet)["verdict"].details()
    assert verdict["verdict"] == "SERIOUS_RISK"
    assert any(r["level"] == "SERIOUS_RISK" and "documents contradict his declaration" in r["text"]
               for r in verdict["reasons"])
    kinds = {c["check"] for c in verdict["document_findings"] if c["status"] == "failed"}
    assert {"UNDECLARED_COMPANY", "UNDECLARED_INCOME", "FUNDING_CONFLICT", "CASH_STRUCTURING"} <= kinds
    needed = [d["document"] for d in verdict["documents"]]
    assert "Beneficial ownership declaration" in needed


def test_without_documents_the_same_client_is_not_serious(run):
    record, reading = marcus()
    record["claims"]["expected_aum"] = 3_000_000
    case = run.save_fake_forecast(record)
    peers, quiet = quiet_peers()
    verdict = run(case, peers, quiet)["verdict"].details()
    assert verdict["verdict"] != "SERIOUS_RISK"
    assert verdict["document_findings"][0]["check"] == "NO_DOCUMENTS"


def test_unreadable_documents_mean_a_person_must_look(run):
    record, reading = marcus()
    case = run.save_fake_forecast(record)
    verdict = run(case, documents=record["supporting_documents"], documents_reply=None)["verdict"].details()
    assert "Reading the submitted documents" in verdict["not_run"]
    assert SEVERITY[verdict["verdict"]] >= SEVERITY["MANUAL_REVIEW"]


def test_pay_comes_from_his_tax_notices_not_the_ai_guess(run):
    record, reading = marcus()
    result = run_marcus(run, record, reading, pay_scale=0.5)
    line = check(result["verdict"].details(), "forecast", "PAY_FROM_DOCUMENTS")
    assert "S$186,000" in line["detail"]
    case = result["case"]
    forecast, adjusted = Forecast(POLICY, CONFIG).calibrate_pay(
        case, copy.deepcopy(result["forecast"]), result["evidence"]["documented_pay"])
    assert adjusted == []                          # already calibrated: applying it again changes nothing
    current = next(p for p in result["forecast"]["earnings"]["positions"]
                   if p["position_index"] == len(case["career_history"]) - 1)
    row = next(r for r in current["yearly"] if r["year"] == 2025)
    assert CareerSavings().pay_total(row, "typical") == pytest.approx(186_000, rel=0.05)


def test_document_reading_is_saved_and_reused(run):
    store = DocumentStore()
    documents = [store.read_for_extraction(path) for path in store.list_folder(MARCUS)]
    with open(MARCUS + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    calls = []

    def caller(prompt, schema, options):
        calls.append(prompt)
        return json.dumps(reading)

    saved = {}
    first = DocumentAI("fake", caller, "fake", 0.0).run({"documents": documents, "saved_replies": saved})
    second = DocumentAI("fake", caller, "fake", 0.0).run({"documents": documents, "saved_replies": saved})
    assert len(calls) == 1 and first == second == reading


def test_loan_financed_purchases_dont_push_cash_below_zero(run):
    record, reading = marcus()
    verdict = run_marcus(run, record, reading)["verdict"].details()
    funding = check(verdict, "benchmark", "AUM_FUNDING")
    liquid = check(verdict, "forecast", "LIQUID_WEALTH")
    assert "-S$" not in liquid["detail"].split(" to ")[-1]          # the optimistic end is not negative
    assert funding["status"] in ("passed", "failed")


def test_banks_and_law_firms_are_not_unusual_counterparties(run):
    record, reading = marcus()                    # declared: Meridian Harbour Bank, Tan & Rao LLP
    verdict = run_marcus(run, record, reading)["verdict"].details()
    counterparties = check(verdict, "benchmark", "COUNTERPARTIES")
    assert counterparties["status"] == "passed"
    assert "Meridian Harbour Bank" in counterparties["detail"] and "left out" in counterparties["detail"]


def test_benchmark_always_shows_its_9_original_checks(run):
    case = run.save_fake_forecast(client_record())
    report = run(case)["verdict"].report
    benchmark = next(s for s in report["sections"] if s["title"].startswith("Benchmark"))
    for item, rule in zip(benchmark["items"][:9], VerdictEngine.ORIGINAL_BENCHMARK):
        assert item["text"].startswith(Benchmark.BENCHMARK_LABELS[rule] + ":"), item["text"]
    assert any(item["mark"] == "pass" for item in benchmark["items"][:9])     # passed ones are shown too
    assert "Declared S$" in benchmark["items"][0]["text"]                      # with their numbers
    forecast = next(s for s in report["sections"] if s["title"].startswith("Forecast"))
    assert all(item["mark"] != "pass" or "Stability" in item["text"] for item in forecast["items"])
    titles = [s["title"] for s in report["sections"]]
    assert "Where the checks agree" not in titles                   # merged into Why
    assert "Documents - what his papers show" in titles
    assert report["evidence_titles"] and all(
        "converted to" not in line for part in report["evidence"] for line in part["lines"])


def test_the_reader_is_told_to_fill_gaps_from_any_document():
    with open(os.path.join(ROOT, "app", "prompts", "document_extract.txt"), encoding="utf-8") as handle:
        prompt = handle.read()
    assert "Read EVERY document for every field" in prompt
    assert "EVIDENCE" in prompt and "documented_pay" in prompt



# ---------------------------------------------------------------------------
# One model, web search from .env, repairs and fail-safes
# ---------------------------------------------------------------------------

def test_every_ai_call_uses_the_one_model(run, tmp_path):
    record, reading = marcus()
    case = run.save_fake_forecast(record)
    run(case, documents=record["supporting_documents"], documents_reply=reading)
    caller = run.last_caller
    asked = {key for key, _ in caller.asked}
    assert {"reports", "sector_typologies", "expected_wealth", "jobs"} <= asked
    assert {options.get("model") for _, options in caller.asked} == {"fake-model"}


def test_web_search_is_switched_from_env(run, monkeypatch):
    application = run.app()
    monkeypatch.setenv("FORECAST_WEB_SEARCH", "on")
    assert application.forecast_settings()["web_search"] is True
    monkeypatch.setenv("FORECAST_WEB_SEARCH", "off")
    assert application.forecast_settings()["web_search"] is False
    monkeypatch.delenv("FORECAST_WEB_SEARCH")
    assert application.forecast_settings()["web_search"] == POLICY["forecasting"]["web_search"]


def test_the_bishan_reply_from_the_log_is_repaired_not_rejected(run):
    case = run.save_fake_forecast(client_record())
    replies = fake_ai.forecast_replies(case)
    listing = json.loads(replies["call1_markets.list"])
    for m in ("PROP_BISHAN", "FX_SGD", "IND_PARTS", "STOCK_SG"):
        listing["relevant_markets"].append({**listing["relevant_markets"][0], "market_id": m})
        replies[f"call1_markets.series.{m}"] = json.dumps({**json.loads(replies["call1_markets.series.ECO_SG"]),
                                                           "market_id": m})
    replies["call1_markets.list"] = json.dumps(listing)
    markets = {m["market_id"] for m in listing["relevant_markets"]}
    reply = json.loads(replies["call2_earnings.asset.0"])
    reply.update(exposures=[{"market_id": m, "sensitivity": {"low": 2, "typical": 5 - n * 0.5, "high": 10}}
                            for n, m in enumerate(sorted(markets))],
                 valuation_basis="Bishan property index")
    replies["call2_earnings.asset.0"] = json.dumps(reply)
    result = fake_services.forecast_ai().run({"record": case, "cache": replies})
    assert result["ok"] and result["results"]["call2_earnings.asset.0"]["from_cache"]   # passed after the repair
    repaired = result["forecast"]["earnings"]["assets"][0]
    assert len(repaired["exposures"]) == POLICY["forecasting"]["max_asset_exposures"]
    assert all(v <= 3.0 for e in repaired["exposures"] for v in e["sensitivity"].values())


def test_one_asset_the_ai_cant_describe_doesnt_stop_the_forecast(run):
    unusable = {"call2_earnings.asset.0": json.dumps({"asset_index": 0})}       # unusable, and no API key
    case = run.save_fake_forecast(client_record(), overrides=unusable)
    result = run(case)
    assert result["forecast"] is not None                                          # the forecast finished
    item = check(result["verdict"].details(), "forecast", "ASSET_NOT_MODELLED")
    assert "purchase price" in item["detail"]
    assert all(c["asset_index"] != 0 for c in result["forecast_assessment"]["asset_checks"])


def test_the_report_says_why_the_forecast_stopped(run):
    unusable = {"call3_types.list": json.dumps({"person_types": []})}             # unusable, and no API key
    case = run.save_fake_forecast(client_record(), overrides=unusable)
    verdict = run(case)["verdict"].details()
    item = check(verdict, "forecast", "FORECAST")
    assert "the list of person types" in item["detail"] and "the AI service is not available right now" in item["detail"]
    assert ".)" not in item["detail"] and ".," not in item["detail"]
    assert "The forecast" in verdict["not_run"]


def test_benchmark_shows_its_9_checks_even_when_it_couldnt_run(run):
    case = run.save_fake_forecast(client_record())
    report = run(case, benchmark_reply=None)["verdict"].report
    benchmark = next(s for s in report["sections"] if s["title"].startswith("Benchmark"))
    first_nine = benchmark["items"][:9]
    assert all(item["mark"] == "skip" and "couldn't run" in item["text"] for item in first_nine)


def test_growth_speed_is_shown_when_no_jump_was_recorded(run):
    case = run.save_fake_forecast(client_record(biggest_wealth_jump=None, wealth_jump_years=None))
    report = run(case)["verdict"].report
    benchmark = next(s for s in report["sections"] if s["title"].startswith("Benchmark"))
    speed = next(item for item in benchmark["items"] if item["text"].startswith("Wealth growth speed"))
    assert speed["mark"] == "skip" and "No biggest wealth jump" in speed["text"]



def test_one_ai_client_is_reused_so_none_is_closed_mid_log(monkeypatch):
    made = []

    class _OpenAI:
        def __init__(self, api_key=None):
            made.append(api_key)
            self.chat = None

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("openai.OpenAI", _OpenAI)
    caller = openai_caller()
    caller("first question", None, {})
    caller("second question", None, {})
    assert made == ["test-key"]                       # one client for every question this caller asks


def test_network_libraries_dont_flood_the_log(run):
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    try:
        run.app().start(["--demo"])                  # starting the app sets up logging, then stops at the unknown option
        for name in ("httpx", "httpcore", "openai"):
            assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
