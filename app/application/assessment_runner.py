"""AssessmentRunner: runs one assessment, step by step."""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Callable

from app.ai.benchmark_ai import BenchmarkAI
from app.ai.document_ai import DocumentAI
from app.ai.forecast_ai import ForecastAI
from app.ai.research_ai import ResearchAI
from app.ai.response_cache import ResponseCache
from app.ai.typology_ai import TypologyAI
from app.data.document_store import DocumentStore
from app.logic.benchmark import Benchmark
from app.logic.case_reader import CaseReader
from app.logic.crime_scan import CrimeScan
from app.logic.document_evidence import DocumentEvidence
from app.logic.forecast import Forecast
from app.logic.verdict_engine import VerdictEngine
from app.model.config import Config
from app.model.declaration import Declaration

logger = logging.getLogger(__name__)


class AssessmentRunner:
    """Runs the documents, the crime scan, the forecast and the benchmark as ONE assessment
    and asks the VerdictEngine for ONE verdict.

    It only coordinates: each step asks an AI service for data, hands the data to a Logic
    feature, and passes the result on. The AI services, the DocumentStore and the
    ResponseCache are handed in; the runner creates and owns the four features and the
    VerdictEngine that reads them.

    When a step cannot be completed the runner does not decide what to do. It tells its
    caller through on_failure(step, reason), and carries on only if the caller says so.
    """

    # The steps the command line and the web app's loading page both show, in order.
    STEPS: tuple[str, ...] = (
        "Reading the submitted documents",
        "Searching trusted sources for typology reports",
        "Checking the research sources",
        "Describing sector typologies",
        "Checking the typology quotes",
        "Reading the source of wealth declaration",
        "Forecasting the economy",
        "Forecasting pay and assets",
        "Building person types from the typologies",
        "Forecasting behaviour and future events",
        "Comparing with peers in the same economy",
        "Testing every story",
        "Deciding the verdict",
        "Saving the assessment",
    )
    # Which numbered step each stage of the forecast is shown as.
    FORECAST_STEP: dict[str, int] = {"step0_declaration": 6, "call1_markets": 7, "call2_earnings": 8,
                                     "call3_types": 9, "call4_events": 10}

    def __init__(self, config: Config | None = None, research_ai: ResearchAI | None = None, typology_ai: TypologyAI | None = None,
                 benchmark_ai: BenchmarkAI | None = None, document_ai: DocumentAI | None = None, forecast_ai: ForecastAI | None = None,
                 document_store: DocumentStore | None = None, response_cache: ResponseCache | None = None) -> None:
        self.__config: Config = config or Config()
        self.__research_ai: ResearchAI | None = research_ai
        self.__typology_ai: TypologyAI | None = typology_ai
        self.__benchmark_ai: BenchmarkAI | None = benchmark_ai
        self.__document_ai: DocumentAI | None = document_ai
        self.__forecast_ai: ForecastAI | None = forecast_ai
        self.__document_store: DocumentStore | None = document_store
        self.__response_cache: ResponseCache | None = response_cache
        policy = self.__config.policy
        self.__case_reader: CaseReader = CaseReader()
        self.__crime_scan: CrimeScan = CrimeScan(policy)
        # The web app runs assessments in parallel threads on this one runner. CrimeScan keeps the
        # warnings of its last check, so a check and the reading of its warnings must not interleave.
        self.__crime_scan_lock: threading.Lock = threading.Lock()
        self.__documents: DocumentEvidence = DocumentEvidence(policy)
        self.__benchmark: Benchmark = Benchmark(policy, self.__config)
        self.__forecast: Forecast = Forecast(policy, self.__config)
        self.__engine: VerdictEngine = VerdictEngine(
            [self.__crime_scan, self.__documents, self.__benchmark, self.__forecast], self.__config)

    def engine(self) -> VerdictEngine:
        return self.__engine

    def run(self, case: dict, supporting_documents: list[dict] | None = None,
            on_step: Callable[[int, str], None] | None = None,
            on_failure: Callable[[str, str], bool] | None = None) -> dict | None:
        """Assess one case. Nothing is printed and nothing is saved here.

        supporting_documents  the client record's saved documents; every one is read.
        on_step(number, label)  is told each step in STEPS as it starts.
        on_failure(step, reason)  is told each step that could not be completed and answers
                                  True to carry on without it or False to stop.
        Returns the result: the Verdict (under "verdict", with its report) and the evidence
        behind it (case, research, typologies, crime result, benchmark, forecast ...), which
        App saves and the web page shows. None if on_failure stopped the assessment.
        "typologies" is a list of Typology objects (None if the typology step failed); the web
        page gets their to_dict() layout. The typology reply itself is saved as it came.
        The Verdict is given a new assessment id and the time it was made here, because the
        VerdictEngine makes no ids and reads no clock.
        """
        def step(number: int) -> None:
            if on_step is not None:
                on_step(number, AssessmentRunner.STEPS[number - 1])

        notes: list[str] = []
        not_run: list[str] = []

        def failed(what: str, reason: str) -> bool:
            """Record a step that did not complete. False means the caller wants to stop."""
            not_run.append(what)
            logger.warning("AssessmentRunner: %s did not complete: %s", what, reason)
            return on_failure(what, reason) if on_failure is not None else True

        policy = self.__config.policy
        ref = case["client_ref"]
        crime_input = self.__case_reader.crime_scan_input(case)

        # 1. Documents: what every submitted document shows (compared later with what he declared)
        step(1)
        files = [str(document.get("file_name") or "document") for document in supporting_documents or []]
        extracted = None
        if files:
            extracted = self.__document_ai.run({"documents": self.__document_store.read_all(supporting_documents)})
            notes += self.__document_ai.warnings()
            if extracted is None and not failed("Reading the submitted documents", "the AI gave no usable reading"):
                return None
        evidence = self.__documents.run(case, {"extracted": extracted, "files": files})

        # 2-5. Crime scan context: what published reports say about his industry
        step(2)
        research = self.__research_ai.run({"case": crime_input, "domains": policy.get("trusted_sources", [])})
        notes += self.__research_ai.warnings()
        step(3)
        reports = None
        if research is not None:
            with self.__crime_scan_lock:
                reports = self.__crime_scan.verify_research(research)
                notes += self.__crime_scan.warnings()
        step(4)
        typology_response = self.__typology_ai.run({"case": crime_input, "research": research,
                                                    "categories": self.__crime_categories()})
        notes += self.__typology_ai.warnings()
        step(5)
        typologies = None
        if typology_response is None:
            if not failed("The crime scan (sector typologies)", "the AI gave no usable typologies"):
                return None
        else:
            found = typology_response.get("sector_typologies", [])
            with self.__crime_scan_lock:
                if reports is not None:
                    typologies = self.__crime_scan.verify_typology_sources(found, reports)
                else:                               # no research to check them against: taken as they are
                    typologies = self.__crime_scan.read_typologies(found)
                notes += self.__crime_scan.warnings()

        # 6-10. Forecast: the declaration is read once here, and the crime types are built from the typologies
        run = self.__forecast_ai.run({
            "record": case, "cache": self.__response_cache.load_raw_replies(ref),
            "typologies": None if typologies is None else [typology.to_dict() for typology in typologies],
            "on_step": lambda stage: step(AssessmentRunner.FORECAST_STEP[stage])})
        self.__response_cache.save_raw_replies(ref, run["results"])
        partial = run["partial"]
        forecast = run["forecast"] if run["ok"] else None
        stopped_at = None
        if forecast is None:
            stopped_at = (f"{self.__engine.describe_piece(case, run.get('failed_piece'))} "
                          f"({run.get('failed_error') or 'unknown error'})")
            notes.append(f"The forecast stopped at {stopped_at}. Finished AI replies are saved, "
                         "so running again carries on from there.")
            if not failed("The forecast", stopped_at):
                return None
        # his real pay, from his tax notices / employment letter, replaces the AI's guess
        pay_adjustments = []
        if forecast is not None:
            forecast, pay_adjustments = self.__forecast.calibrate_pay(case, forecast, evidence["documented_pay"])

        # 11. Benchmark: peers in the same economy (the forecast's markets, never his own figures)
        step(11)
        bench_input, unreadable = self.__case_reader.benchmark_input(case, crime_input)
        bench_ai = findings = None
        reason = "the AI gave no usable benchmark"
        if unreadable:
            reason = f"can't read {', '.join(unreadable)} from the case"
            notes.append(f"Peer benchmark skipped: {reason}.")
        else:
            bench_ai = self.__benchmark_ai.run({"client": bench_input,
                                                "economy": self.__forecast.economy_brief(partial.get("markets"))})
            if bench_ai is not None:
                try:
                    findings = self.__benchmark.run(case, {"benchmark_input": bench_input,
                                                           "benchmark_ai": bench_ai})["findings"]
                except (ZeroDivisionError, KeyError, TypeError) as error:
                    reason = f"the AI's reply could not be worked out ({error!r})"
                    notes.append(f"Peer benchmark couldn't be worked out from the AI's reply ({error!r}).")
        if findings is None and not failed("The peer benchmark", reason):
            return None

        # 12. Test every story
        step(12)
        forecast_assessment = self.__forecast.run(case, {"forecast": forecast}) if forecast else None
        declaration = partial.get("declaration")
        crime_declaration, warnings = self.__crime_scan.crime_declaration(
            Declaration.from_dict(declaration) if declaration else None)
        notes += warnings
        crime_result = None
        if typologies is not None and crime_declaration is not None:
            crime_declaration, warnings = self.__crime_scan.normalise_jurisdictions(crime_declaration)
            notes += warnings
            crime_result = self.__crime_scan.run(crime_input, {
                "typologies": typologies, "declaration": crime_declaration})
        elif typologies is not None:
            if not failed("The crime scan's warning signs (the declaration couldn't be read)",
                          "the declaration could not be read"):
                return None

        # 13. One verdict, and the report both front ends show
        step(13)
        try:
            verdict = self.__engine.combine(case, {
                "reports": reports,
                "typologies": typologies, "crime_result": crime_result, "declaration": declaration,
                "benchmark_input": bench_input, "benchmark_ai": bench_ai, "benchmark_findings": findings,
                "forecast": forecast, "forecast_assessment": forecast_assessment,
                "markets": partial.get("markets"), "evidence": evidence, "pay_adjustments": pay_adjustments,
                "failed_step": stopped_at, "not_run": not_run, "notes": notes,
                "assessment_id": str(uuid.uuid4()), "assessed_at": datetime.now(timezone.utc).isoformat(),
            })
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            logger.exception("AssessmentRunner: the verdict could not be worked out")
            failed("Deciding the verdict", repr(error))
            return None
        return {
            "case": case,
            "research": research,
            "typology_response": typology_response,
            "typologies": typologies,
            "declaration": declaration,
            "crime_declaration": crime_declaration,
            "crime_result": crime_result,
            "benchmark": {"input": bench_input, "expected": bench_ai, "findings": findings},
            "forecast": forecast,
            "forecast_assessment": forecast_assessment,
            "evidence": evidence,
            "verdict": verdict,
        }

    def __crime_categories(self) -> dict:
        """{code: description} of the crime categories a typology may belong to (every one but the honest one)."""
        honest = self.__config.policy["forecasting"]["honest_category"]
        return {code: text for code, text in self.__config.vocabulary.get("crime_categories", {}).items()
                if code != honest}
