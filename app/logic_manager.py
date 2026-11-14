"""
logic_manager.py - the old function names of the logic layer.

The work now lives in the classes in app/logic (the Logic Manager):
    VerdictEngine                          one verdict from every feature's checks
    Feature                                the abstract parent of the four features:
      CrimeScan, DocumentEvidence,
      Benchmark, Forecast
    Indicator and its five children        the warning signs the crime scan looks for
    MarketModel, CareerSavings, AssetPath,
    FuturePaths, OnboardingAssessor,
    PayCalibrator                          the forecast arithmetic
    CaseReader, DocumentRecordBuilder      reading records and building them from documents
    Formatter, CaseTimeline                small helpers

The functions below only build one of those classes and call it, so main.py, the
web app and the older tests keep working while the rest of the refactor is done.
This file is deleted once App calls the classes directly.

Everything here is pure: no file access, no network, no printing.
"""

import logging

from app import utilities
from app.logic.career_savings import CareerSavings
from app.logic.pay_calibrator import PayCalibrator
from app.logic.forecast import Forecast
from app.logic.crime_scan import CrimeScan
from app.logic.case_reader import CaseReader
from app.logic.document_evidence import DocumentEvidence
from app.logic.benchmark import Benchmark
from app.logic.verdict_engine import VerdictEngine
from app.logic.document_record_builder import DocumentRecordBuilder
from app.model.band import Band
from app.model.config import Config
from app.model.verdict import Verdict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared — limits used across all features
# ---------------------------------------------------------------------------

LIMITS = Benchmark.LIMITS

# ---------------------------------------------------------------------------
# Benchmark Section
# ---------------------------------------------------------------------------


_COMPOSITION_PARTS = Benchmark._COMPOSITION_PARTS


#=============================================================================#


def crime_scan_input(record: dict) -> dict:
    """The crime scan input from a saved client record (used by both the CLI and the web app).
    Raises KeyError if the record has no career or no source of wealth declaration."""
    return CaseReader().crime_scan_input(record)


def benchmark_input(record: dict, case_input: dict) -> tuple[dict, list[str]]:
    """The benchmark's input built from a saved client record - the CLI and the web app both use this,
    so the same client always gets the same benchmark. Composition is in whole percents (45 = 45%),
    the unit run_benchmark and the benchmark prompt expect.
    Returns (input, names of the required values that are missing)."""
    return CaseReader().benchmark_input(record, case_input)


def run_benchmark(client_data: dict, ai_data: dict, policy: dict | None = None):
    """Run all benchmark checks for a client."""

    return Benchmark(policy)._run_rules(client_data, ai_data)

    
# ---------------------------------------------------------------------------
# Crime Scan Section — Research & Source Verification
# ---------------------------------------------------------------------------

# Filter AI research reports: keep only grounded, trusted-domain, non-duplicate URLs.
def verify_research(research: dict, policy: dict) -> tuple[dict, list[str]]:
    """Filter research reports by grounding, domain trust, and uniqueness.

    Pure function — no I/O, no network.

    Rules applied in order per report:
    1. URL must be in research["api_sources"] (actually retrieved by web search).
    2. URL domain must be in policy["trusted_sources"].
    3. Duplicate URLs are dropped (first kept).
    4. Surviving reports are renumbered R1, R2, ...

    Returns (clean_research_dict, warnings).
    """
    return CrimeScan(policy).verify_research(research)


# Drop typology quotes not found verbatim in cited reports; drop typologies with nothing left.
def verify_typology_sources(
    typologies: list[dict],
    clean_research: dict,
    policy: dict,
) -> tuple[list[dict], list[str]]:
    """Verify and clean AI typology source citations against filtered research reports.

    Pure function — no I/O, no network.

    For each typology:
    1. source_ids not found in clean_research are removed.
    2. source_quotes whose quote does not appear (after normalisation) in the
       cited report's excerpts are removed.
    3. Typologies with no verified quotes left are dropped entirely.
    4. corroborated: warns if fewer than 2 independent-org sources remain.
    5. outdated: warns if a source exceeds policy[source_max_age_years].
    6. unknown_age: reports with missing/invalid year are noted, not outdated.

    Returns (cleaned_typologies, warnings).
    """
    return CrimeScan(policy).verify_typology_sources(typologies, clean_research)


# Normalise text for quote matching. ResearchReport (Domain Model) owns the matching;
# this function stays until verify_typology_sources moves into CrimeScan.


# Check if a URL's domain is in the trusted sources list (including subdomains).


# Split a combined organisation string into individual names for corroboration checks.


# ---------------------------------------------------------------------------
# # Crime Scan Section — Typologies Check
# ---------------------------------------------------------------------------

# Orchestrate the full crime scan: normalise case → match typologies → count breaches.
def assess_typology_case(
    case_input: dict,
    typology_response: dict | None,
    declaration: dict | None,
    policy: dict,
) -> dict:
    """Run the full Sector Crime Scan assessment for a single case.

    Returns a dict with keys: outcome, findings, documents, match_results.
    """

    # If either AI call failed entirely (returned None), skip assessment
    return CrimeScan(policy)._assess(case_input, typology_response, declaration)


# The five warning signs are the Indicator classes in app/logic/indicator.py.
# These functions keep their old names until match_typologies moves into CrimeScan.


# Map fired indicator counts to a severity category.


# Run all 5 indicators against the client; a typology breaches when every core indicator fires.
def match_typologies(
    typologies: list[dict],
    declaration: dict,
    clean_case: dict,
    policy: dict,
) -> list[dict]:
    """Match each typology's indicators against client data. Pure function.

    A typology breaches when ALL its core indicators fire.
    Returns a list of match result dicts, one per typology.
    """
    return CrimeScan(policy).match_typologies(typologies, declaration, clean_case)


# ---------------------------------------------------------------------------
# # Crime Scan Section — data normalisation helpers
# ---------------------------------------------------------------------------

_COUNTRY_TO_ISO = CrimeScan._COUNTRY_TO_ISO


# Convert a country name or short code to ISO 3166-1 alpha-2, with a warning if unrecognised.


# Safely cast a value to int, returning default if None or conversion fails.


# Normalise a client record (ISO codes, int fields, all_jurisdictions) ready for typology matching.
def prepare_case_for_matching(record: dict) -> tuple[dict, list[str]]:
    """Normalize a client record for typology matching. Pure function.

    Returns (normalized_record, warnings).

    1. Coerces age, career_start_year to int.
    2. Converts country/country_of_residence to ISO-2.
    3. Builds all_jurisdictions: sorted deduplicated list of ISO-2 codes from
       country, country_of_residence, wealth_countries, career_timeline,
       asset_timeline, and declarations.wealth_countries.
    4. Extracts declared_net_worth_sgd from whichever location has it.
    5. Extracts reference_year from record or date fields.
    Does NOT mutate the original record or any sub-dicts.
    """
    return CrimeScan()._prepare_case(record)


# Convert jurisdiction strings in a parsed AI declaration to ISO-2 codes.
def normalize_declaration_jurisdictions(declaration: dict) -> tuple[dict, list[str]]:
    """Post-process AI declaration output to ensure jurisdiction fields are ISO-2.

    Pure function. Called after schema validation succeeds.
    Per source:
    - Valid ISO-2 (2 uppercase letters) → kept.
    - Full name in _COUNTRY_TO_ISO → converted + warning.
    - 2 lowercase letters → uppercased + warning.
    - Unrecognizable string → set to None + warning.
    - None → kept.
    Returns (cleaned_declaration, warnings).
    """
    return CrimeScan().normalise_jurisdictions(declaration)

# ===========================================================================
# Forecasting Section (runs after the benchmark)
# ===========================================================================

PASSED, MANUAL_REVIEW, RISKY, SERIOUS_RISK = Verdict.OUTCOMES
SEVERITY = {PASSED: 0, MANUAL_REVIEW: 1, RISKY: 2, SERIOUS_RISK: 3}

# Every money result is kept at three levels. The Band class (Domain Model) owns the arithmetic;
# these names stay until the forecast code moves into its own classes.
BANDS = Band.LEVELS
MONEY_IN = Band.MONEY_IN
MONEY_OUT = Band.MONEY_OUT


# ============================================================================
# Small helpers
# ============================================================================


# ============================================================================
# 1. Markets (from Call 1)
# ============================================================================


# ============================================================================
# 2. Savings from his jobs (from Call 2)
# ============================================================================

def pay_total(pay: dict, level: str) -> float:
    return CareerSavings().pay_total(pay, level)


# ============================================================================
# 3. Assets (Call 2 behaviour + Call 1 markets)
# ============================================================================


# ============================================================================
# 4. Wealth of every type, past years (back-test)
# ============================================================================


# ============================================================================
# 5. Onboarding checks
# ============================================================================


# ============================================================================
# 6. The future: forward paths, events, divergence
# ============================================================================


# ============================================================================
# Onboarding: the full assessment
# ============================================================================

def assess_onboarding(record: dict, forecast: dict, policy: dict | None = None) -> dict:
    """Measure the client against the forecasts and decide. No AI involved."""
    policy = policy or utilities.policy()
    feature = Forecast(policy, Config(policy, utilities.vocabulary()))
    return feature.run(record, {"forecast": forecast})


# ============================================================================
# 4. New client from documents (CLI) - turning the AI's reading of the client's
#    documents into a client record, and finding what's still missing.
#    Pure functions: no printing, no files, no AI.
# ============================================================================

COMPOSITION_KEYS = CaseReader.COMPOSITION_KEYS


def record_from_documents(extracted: dict, client_ref: str, today: str) -> tuple[dict, list[str]]:
    """Build a client record (the same layout the New Client form saves) from the AI's
    reading of the documents. Returns (record, paths of the fields that came from the documents).

    Every job, including the current one (end_year None), goes into career_history;
    finish_document_record then copies the current job into "career".
    """
    return DocumentRecordBuilder(today=today).build(extracted, client_ref)


def set_path(record: dict, path: list, value) -> dict:
    """Return a copy of record with the value at path replaced."""
    return DocumentRecordBuilder().set_path(record, path, value)


def missing_client_fields(record: dict) -> list[dict]:
    """The required fields still empty (or unusable) after reading the documents, in form order."""
    return DocumentRecordBuilder().missing_fields(record)


def finish_document_record(record: dict) -> dict:
    """Copy the current job (the one with no end year) into "career", and the first job's start year
    into career_start_year - the same layout the New Client form saves."""
    return DocumentRecordBuilder().finish(record)


def check_document_record(record: dict, today: str, policy: dict | None = None) -> list[str]:
    """Things worth a second look in a record filled from documents. Empty list = nothing spotted."""
    return DocumentRecordBuilder(Config(policy or {}, {}), today).check(record)


SUMMARY_SECTIONS = DocumentRecordBuilder.SUMMARY_SECTIONS


def summarise_document_record(record: dict, doc_record: dict) -> list[dict]:
    """One row per field for the officer to check: its value and where it came from.

    source: "documents" (read from the documents, unchanged), "edited" (read from the documents,
    then changed by the officer), "entered" (typed by the officer) or "blank".
    """
    return DocumentRecordBuilder().summarise(record, doc_record)


CAREER_JOB_KEYS = DocumentRecordBuilder.CAREER_JOB_KEYS


def sync_after_edit(before: dict, after: dict) -> dict:
    """After the officer edits the record, keep "career" and the current job in career_history the same.
    If the profile screen changed "career", copy that into the current job; otherwise copy the
    (possibly edited) current job into "career"."""
    return DocumentRecordBuilder().sync_after_edit(before, after)

# ============================================================================
# COMBINED ASSESSMENT - one verdict from the crime scan, the benchmark and the forecast
# ============================================================================
# The three features test the same set of "possible stories" for the client: the forecast's
# person types (T1 = his wealth came exactly as declared, T2+ = crime stories).
#
#   Crime scan   is a crime story a known pattern for his industry, and did its warning
#                signs fire in his declaration?            (typologies -> person types)
#   Forecast     could the money add up under each story?  (pay, assets, the economy)
#   Benchmark    is he unusual next to peers in the same economy, and does the honest
#                story explain it?                         (economy -> benchmark)
#
# combined_verdict() turns all three into ONE verdict with reasons, and verdict_report()
# turns that into the report the command line prints and the web app shows (same text).
# Everything here is pure: no files, no network, no printing.

VERDICT_LABELS = VerdictEngine.VERDICT_LABELS

# Crime-scan match levels where every core warning sign fired
FULL_MATCH = CrimeScan.FULL_MATCH
WEAK_MATCH = CrimeScan.WEAK_MATCH
MATCH_LABELS = CrimeScan.MATCH_LABELS

# The six themes a finding can belong to (used to show where the checks agree)
THEMES = VerdictEngine.THEMES

# The crime scan's warning signs, which theme each belongs to, and how to say it
SIGN_THEMES = CrimeScan.SIGN_THEMES
SIGN_LABELS = CrimeScan.SIGN_LABELS

BENCHMARK_LABELS = Benchmark.BENCHMARK_LABELS
# Benchmark checks worked out from the forecast's honest story, so they can't "agree" with it
FORECAST_DERIVED = Benchmark.FORECAST_DERIVED
COMPOSITION_RULES = Benchmark.COMPOSITION_RULES

# Status of one check: failed (counts), weak (a loose end), explained (failed on its own, but
# another feature explains it, so it doesn't count), passed, skipped (couldn't run), info.


# ---------------------------------------------------------------------------
# 1. The client record -> the forecasting case (the same for the CLI and the web app)
# ---------------------------------------------------------------------------

_PRESENT_WORDS = CaseReader._PRESENT_WORDS


def forecasting_case(record: dict, today: str) -> tuple[dict | None, list[str]]:
    """Turn a saved client record (from the web form, the command line or the documents
    auto-fill) into the case every part of the assessment uses, dated today.

    Returns (case, []) when everything can be read, otherwise (None, what's missing).
    The command line then asks the officer for what's missing (io_manager.case_from_client_record);
    the web app asks the officer to complete the record. Both assess the same case.
    """
    return CaseReader(today).forecasting_case(record)


# ---------------------------------------------------------------------------
# 2. Links between the features
# ---------------------------------------------------------------------------

def crime_declaration(declaration: dict | None, policy: dict | None = None) -> tuple[dict | None, list[str]]:
    """The declaration the forecast read (Step 0), as the crime scan's warning-sign rows.

    The declaration is read by the AI ONCE; this only reshapes it. A salary, bonus or savings
    source tied to one of his jobs needs no amount: the forecast works out what the job paid.
    Returns ({"sources": [...]}, warnings) or (None, warnings) if there is no declaration.
    """
    return CrimeScan(policy or utilities.policy()).crime_declaration(declaration)


def economy_brief(markets: dict | None) -> dict | None:
    """What the benchmark AI may see of the forecast's economy (Call 1): each market's yearly %
    change and each country's risk listings. Nothing about the client's own figures."""
    return Forecast().economy_brief(markets)


# ---------------------------------------------------------------------------
# 2b. The documents layer: what the submitted documents themselves show
# ---------------------------------------------------------------------------
# The client record holds what the client DECLARED (the standard form). The documents layer
# holds what his documents SHOW, each fact with the file it came from. The two are compared,
# and every contradiction is evidence for the verdict, like a benchmark or crime-scan finding.

def document_evidence(extracted: dict | None, files: list[str] | None = None,
                      policy: dict | None = None) -> dict:
    """The AI's reading of every submitted document, cleaned into the documents layer:
    {"files", "documented_pay": [{year, amount, source_file}], "findings": [...], "notes": [...]}.
    Anything the reading left out is just empty, so older readings still work."""
    return DocumentEvidence(policy or utilities.policy())._read(extracted, files)


def calibrate_pay(case: dict, forecast: dict, documented_pay: list[dict], policy: dict) -> tuple[dict, list[dict]]:
    """Use the pay his documents show (tax notices, employment letter) instead of the AI's guess.

    For each job with documented years, every year of that job's forecast pay is scaled by
    documented / AI-typical over those years (the current job's future pay too), so the honest
    story is built on his real pay. The AI never sees these figures; only this arithmetic does.
    Returns (adjusted forecast copy, one row per adjusted job)."""
    return PayCalibrator(CareerSavings(), policy).calibrate(case, forecast, documented_pay)


# ---------------------------------------------------------------------------
# 3. The honest story's numbers (shared by the benchmark cross-checks and the forecast checks)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 4. The checks of each feature, in the shared shape (with the cross-checks)
# ---------------------------------------------------------------------------


def describe_piece(case: dict, piece: str | None) -> str:
    """A forecast piece's name in words: 'call2_earnings.asset.0' -> 'asset 1 (Property - Condo, Bishan)'."""
    return VerdictEngine([], Config(utilities.policy(), utilities.vocabulary())).describe_piece(case, piece)


# ---------------------------------------------------------------------------
# 5. One verdict
# ---------------------------------------------------------------------------


def combined_verdict(case: dict, parts: dict, policy: dict | None = None) -> dict:
    """ONE verdict from the crime scan, the benchmark and the forecast.

    parts: research, typologies (verified list), crime_result, declaration (forecast Step 0),
           benchmark_input, benchmark_ai, benchmark_findings, forecast, forecast_assessment,
           markets (Call 1, even if the forecast stopped later), evidence (the documents layer),
           pay_adjustments (calibrate_pay), failed_step, not_run, notes

    The ladder (config/policy.json "verdict" holds the numbers):
      SERIOUS RISK   the honest story can't explain his wealth AND a crime story can AND another
                     feature agrees (its warning signs fired, his documents support it, or a
                     benchmark failure the forecast can't explain); OR his documents contradict his
                     declaration in several ways AND another feature agrees. One feature alone can
                     never reach Serious Risk.
      RISKY          the honest story fails or only works at the optimistic edge, a purchase he
                     couldn't afford, a crime story that fits whose warning signs fired, money for
                     the bank he can't fund, a PEP with a public-office crime story that fits, or
                     several unexplained benchmark failures
      MANUAL REVIEW  loose ends: an unexplained benchmark failure, other forecast checks failed,
                     a borderline result, a PEP, a known pattern on its own, or a part that couldn't run
      PASSED         everything else
    """
    policy = policy or utilities.policy()
    config = Config(policy, utilities.vocabulary())
    features = [CrimeScan(policy), DocumentEvidence(policy), Benchmark(policy, config), Forecast(policy, config)]
    return VerdictEngine(features, config).decide(case, parts)


# Notes from the run that are routine bookkeeping, not something the officer must look at
_ROUTINE_NOTES = VerdictEngine._ROUTINE_NOTES


# ---------------------------------------------------------------------------
# 6. The report (the command line prints it, the web app shows it: the same text)
# ---------------------------------------------------------------------------

MARKS = VerdictEngine.MARKS
# How each mark is shown, by the command line and the web app alike
REPORT_LEGEND = VerdictEngine.REPORT_LEGEND


# The benchmark's 9 original checks: always shown in the report, passed or not, in this order
ORIGINAL_BENCHMARK = VerdictEngine.ORIGINAL_BENCHMARK


def verdict_report(verdict: dict) -> dict:
    """The report as plain data: a header, short sections of marked lines, and the full evidence.
    io_manager prints it and the web app's template shows it, so both give exactly the same content.

    The benchmark section always lists its 9 original checks, passed or not. The other sections show
    only what matters: failures, what another feature explained, loose ends and what couldn't run;
    their passed checks are listed under "What came back clean"."""
    return VerdictEngine([], Config(utilities.policy(), utilities.vocabulary())).report(verdict)
