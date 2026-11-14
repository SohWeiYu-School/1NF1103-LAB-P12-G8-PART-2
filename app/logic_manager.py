"""
logic_manager.py - the logic layer: every calculation and every decision.

The sections run in this order for a new client:

    1. Benchmark          run_benchmark: declared figures vs the AI's single expected
                          values (total wealth, liquidity, composition) -> PASS / FAIL
    2. Sector Crime Scan  decide_outcome, build_document_requests, assess_typology_case
    3. Forecasting        (runs after the benchmark)
       Onboarding (assess_onboarding):
         Types: T1 is the honest person; T2+ are standard crime categories (trade-based money
         laundering, sanctions evasion, ...) each tied to the job/asset/source that enables it.
         1. Back-test every type: build each type's wealth, year by year, from the forecasts
         2. Fit score per type: does his declared wealth, asset values and purchases fit it?
         3. Affordability per type: could he have paid for each purchase that year?
         4. Checks that don't depend on the type: asset values, asset income, countries,
            declared sources with no amount
         5. Stability test: re-run the decision with every forecast 10% lower and higher
         6. Forward paths, event impacts, divergence dates, monitoring ranges,
            ranked documents, next review date

The forecasting section calls no AI: it only does arithmetic on the forecasts and decides
with fixed rules from config/policy.json, so the same forecast and the same client always
give the same answer.

Outcomes: PASSED, MANUAL_REVIEW, RISKY, SERIOUS_RISK.
"""

import copy
import datetime
import logging
import re

from app import utilities
from app.logic.formatter import Formatter
from app.logic.market_model import MarketModel
from app.logic.career_savings import CareerSavings
from app.logic.asset_path import AssetPath
from app.logic.future_paths import FuturePaths
from app.logic.onboarding_assessor import OnboardingAssessor
from app.logic.pay_calibrator import PayCalibrator
from app.logic.forecast import Forecast
from app.logic.crime_scan import CrimeScan
from app.logic.case_reader import CaseReader
from app.model.band import Band
from app.model.check import Check
from app.model.config import Config
from app.model.verdict import Verdict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared — limits used across all features
# ---------------------------------------------------------------------------

LIMITS = {
    "total_wealth": 3,
    "liquidity": 2,
    "composition": 40,
    "velocity": 2,
    "counterparties": 1,
    "jurisdiction": 1
}

# ---------------------------------------------------------------------------
# Benchmark Section
# ---------------------------------------------------------------------------


def calculate_total_wealth(client_data, ai_data):

    declared = client_data["declared_net_worth"]
    expected = ai_data["expected_wealth"]

    result1 = declared / expected

    return result1


def calculate_liquidity(client_data, ai_data):

    declared = client_data["listed_equities"] + client_data["cash"]
    expected = ai_data["expected_liquidity"]

    result2 = declared / expected

    return result2


_COMPOSITION_PARTS = [
    ("COMPOSITION_PROPERTY",  "property",        "expected_property",        "Property"),
    ("COMPOSITION_EQUITIES",  "listed_equities",  "expected_listed_equities", "Listed equities"),
    ("COMPOSITION_BUSINESS",  "private_business", "expected_private_business","Private business"),
    ("COMPOSITION_CASH",      "cash",             "expected_cash",            "Cash"),
]


def calculate_composition(client_data, ai_data):
    results = []
    for rule_id, client_key, ai_key, label in _COMPOSITION_PARTS:
        declared = client_data[client_key]
        expected = ai_data[ai_key]
        diff = abs(declared - expected)
        results.append({"rule_id": rule_id, "failed": diff > LIMITS["composition"],
                        "detail": f"{label}: declared {declared}%, expected {expected}%, diff {diff}%"})
    return results


def calculate_velocity(client_data, ai_data):
    jump = client_data.get("biggest_wealth_jump")
    years = client_data.get("wealth_jump_years")
    expected = ai_data.get("expected_velocity")
    if jump is None or years is None or years <= 0 or expected is None or expected <= 0:
        return None, None          # (ratio, per_year) — None means skipped
    per_year = jump / years
    return per_year / expected, per_year

def calculate_counterparties(declared, expected):
    unknown = []

    for item in declared:
        if item not in expected:
            unknown.append(item)

    return unknown

#=============================================================================#
def clean_country(country):
    if country == "SG":
        return "Singapore"
    elif country == "MY":
        return "Malaysia"
    elif country == "ID":
        return "Indonesia"
    elif country == "HK":
        return "Hong Kong"
    elif country == "AE":
        return "United Arab Emirates"

    return country

def calculate_jurisdiction(declared, expected):
    unknown = []

    for country in declared:
        country = clean_country(country)

        if country not in expected:
            unknown.append(country)

    return unknown


def crime_scan_input(record: dict) -> dict:
    """The crime scan input from a saved client record (used by both the CLI and the web app).
    Raises KeyError if the record has no career or no source of wealth declaration."""
    career = record["career"]
    sow = record["sow_declaration"]
    return {
        "client_ref":           record["client_ref"],
        "occupation":           career["occupation"],
        "industry":             career["industry"],
        "age":                  utilities.whole_number(career["age"]),
        "career_start_year":    utilities.whole_number(career["career_start_year"]),
        "country":              career["country_of_residence"],
        "country_of_residence": career["country_of_residence"],
        "declaration_text":     sow if isinstance(sow, str) else (sow or {}).get("declaration_text", ""),
    }


def _whole_percent(value) -> int | None:
    """A share of wealth as a whole-number percent: 0.45 (stored fraction) or 45 -> 45."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value * 100) if value <= 1.0 else round(value)


def benchmark_input(record: dict, case_input: dict) -> tuple[dict, list[str]]:
    """The benchmark's input built from a saved client record - the CLI and the web app both use this,
    so the same client always gets the same benchmark. Composition is in whole percents (45 = 45%),
    the unit run_benchmark and the benchmark prompt expect.
    Returns (input, names of the required values that are missing)."""
    claims = record.get("claims") or {}
    split = claims.get("asset_composition") or {}
    worth = claims.get("declared_net_worth")
    jump = claims.get("biggest_wealth_jump")
    data = {
        **case_input,
        "declared_net_worth":      utilities.whole_number(worth),
        "listed_equities":         _whole_percent(split.get("listed_equities")),
        "cash":                    _whole_percent(split.get("cash")),
        "property":                _whole_percent(split.get("property")),
        "private_business":        _whole_percent(split.get("private_business")),
        "biggest_wealth_jump":     float(jump) if isinstance(jump, (int, float)) else None,
        "wealth_jump_years":       float(claims.get("wealth_jump_years") or 0.0),
        "declared_counterparties": list(claims.get("declared_counterparties") or []),
        "declared_countries":      list(claims.get("wealth_countries") or []),
    }
    missing = [key for key in ("declared_net_worth", "listed_equities", "cash", "property", "private_business")
               if data[key] is None]
    return data, missing


def run_benchmark(client_data: dict, ai_data: dict, policy: dict | None = None):
    """Run all benchmark checks for a client."""

    if ai_data is None:
        return None

    findings = []

    # 1. TOTAL WEALTH CHECK
    result1 = calculate_total_wealth(client_data, ai_data)
    findings.append({"rule_id": "TOTAL_WEALTH", "failed": result1 > LIMITS["total_wealth"],
                     "detail": f"Declared {client_data['declared_net_worth']:,}, expected {ai_data['expected_wealth']:,}, ratio {round(result1, 2)}"})

    # 2. LIQUIDITY CHECK
    result2 = calculate_liquidity(client_data, ai_data)
    findings.append({"rule_id": "LIQUIDITY", "failed": result2 > LIMITS["liquidity"],
                     "detail": f"Declared {client_data['listed_equities'] + client_data['cash']}%, expected {ai_data['expected_liquidity']}%, ratio {round(result2, 2)}"})

    # 3. ASSET COMPOSITION CHECK
    findings += calculate_composition(client_data, ai_data)

    # 4. VELOCITY CHECK
    ratio, per_year = calculate_velocity(client_data, ai_data)
    if ratio is None:
        findings.append({"rule_id": "VELOCITY", "failed": False,
                         "detail": "Skipped — missing or invalid wealth timeline data"})
    else:
        findings.append({"rule_id": "VELOCITY", "failed": ratio > LIMITS["velocity"],
                         "detail": f"Actual velocity {round(per_year, 2)}, expected {ai_data.get('expected_velocity')}, ratio {round(ratio, 2)}"})

    # 5. COUNTERPARTIES CHECK — service providers (banks, law firms, etc.) are excluded
    declared_counterparties = client_data.get("declared_counterparties", [])
    if policy:
        words = policy.get("verdict", {}).get("service_provider_words", [])
        declared_counterparties = [c for c in declared_counterparties
                                   if not any(re.search(rf"\b{re.escape(w)}\b", c.lower()) for w in words)]
    expected_counterparties = ai_data.get("expected_counterparties", [])
    unknown_counterparties = calculate_counterparties(declared_counterparties, expected_counterparties)
    findings.append({"rule_id": "COUNTERPARTIES", "failed": len(unknown_counterparties) > LIMITS["counterparties"],
                     "detail": f"Unknown counterparties: {unknown_counterparties or 'none'}"})

    # 6. JURISDICTION CHECK
    declared_countries = client_data.get("declared_countries", [])
    expected_countries = ai_data.get("expected_jurisdiction", [])
    unknown_countries = calculate_jurisdiction(declared_countries, expected_countries)
    findings.append({"rule_id": "JURISDICTION", "failed": len(unknown_countries) > LIMITS["jurisdiction"],
                     "detail": f"Unknown countries: {unknown_countries or 'none'}"})

    return {"findings": findings}

    
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

def band(cautious: float, typical: float, optimistic: float) -> dict:
    return Band(cautious, typical, optimistic).to_dict()


def zero_band() -> dict:
    return Band().to_dict()


def add_bands(first: dict, second: dict) -> dict:
    return (Band.from_dict(first) + Band.from_dict(second)).to_dict()


def scale_band(values: dict, factor: float) -> dict:
    return (Band.from_dict(values) * factor).to_dict()


def sorted_band(three_values: list[float]) -> dict:
    """Three results worked out from the low, typical and high inputs, lowest first."""
    return Band.from_values(three_values).to_dict()


def range_to_band(ai_range: dict) -> dict:
    """An AI {low, typical, high} range as a cautious/typical/optimistic band."""
    return Band.from_range(ai_range).to_dict()


def add_months(date_text: str, months: int) -> str:
    """'2026-09-24' + 3 months = '2026-12-24' (the day is clipped to the month's length)."""
    return Formatter.add_months(date_text, months)


def same_country(name: str, policy: dict) -> str:
    """Lower-case a country name and map short forms (UAE, Dubai) to one spelling."""
    return Config(policy, {}).same_country(name)


def category_name(code: str) -> str:
    """'TRADE_BASED_ML' -> its readable name from the vocabulary file."""
    return Config({}, utilities.vocabulary()).category_name(code)




def asset_category(asset_type: str, policy: dict) -> str:
    """property / listed_equities / private_business, by keyword lookup."""
    text = (asset_type or "").lower()
    for category, keywords in policy["asset_categories"].items():
        if any(word in text for word in keywords):
            return category
    return "other"


# ============================================================================
# 1. Markets (from Call 1)
# ============================================================================

def market_history(forecast: dict) -> dict:
    """{market_id: {year: % change or None}}"""
    return MarketModel(forecast).history()


def market_outlook(forecast: dict) -> dict:
    """{market_id: {year: {scenario: {low, typical, high}}}}"""
    return MarketModel(forecast).outlook()


def scenario_chances(forecast: dict) -> dict:
    """{year: {scenario: share}} with the shares adding up to exactly 1."""
    return MarketModel(forecast).scenario_chances()




# ============================================================================
# 2. Savings from his jobs (from Call 2)
# ============================================================================

def pay_total(pay: dict, level: str) -> float:
    return CareerSavings().pay_total(pay, level)


def career_savings(forecast: dict, start: int, end: int) -> list[dict]:
    """Year by year: total pay, after tax, living costs, saved, growth and savings so far."""
    return CareerSavings(forecast["earnings"]).rows(start, end)


# ============================================================================
# 3. Assets (Call 2 behaviour + Call 1 markets)
# ============================================================================



def all_asset_paths(record: dict, forecast: dict, last_year: int, scenario: str,
                    shocks: dict | None = None) -> list[dict]:
    assets = AssetPath(MarketModel(forecast), forecast["earnings"]["assets"])
    return assets.build(record, last_year, scenario, shocks)


def income_up_to(path: dict, year: int) -> dict:
    """Total income an asset produced up to and including a year."""
    return AssetPath(MarketModel()).income_up_to(path, year)


# ============================================================================
# 4. Wealth of every type, past years (back-test)
# ============================================================================

def extra_money_up_to(behaviour: dict, year: int) -> dict:
    """A type's extra money (Call 3) added up to and including a year."""
    return FuturePaths(MarketModel()).extra_money_up_to(behaviour, year)


def honest_wealth(record: dict, savings_rows: list[dict], paths: list[dict], year: int) -> dict:
    """Wealth of the as-declared version: savings + gain on each asset + its income so far."""
    return FuturePaths(MarketModel()).honest_wealth(record, savings_rows, paths, year)


def type_wealth_now(record: dict, forecast: dict, savings_rows: list[dict], paths: list[dict]) -> dict:
    """{type_id: wealth band today} = honest wealth + that type's extra money so far."""
    return FuturePaths(MarketModel(forecast), forecast).type_wealth_now(record, savings_rows, paths)


# ============================================================================
# 5. Onboarding checks
# ============================================================================

def check_asset_values(record: dict, forecast: dict, paths: list[dict], end: int,
                       policy: dict, scale: float = 1.0) -> list[dict]:
    """Is each declared asset value within what its markets explain?"""
    return OnboardingAssessor(FuturePaths(MarketModel(forecast), forecast, policy), policy, Config(policy, {}))._check_asset_values(record, forecast, paths, end, scale)


def check_asset_income(record: dict, paths: list[dict], end: int, policy: dict,
                       scale: float = 1.0) -> list[dict]:
    """Is each asset's declared income within what an asset of that value normally pays?"""
    return OnboardingAssessor(FuturePaths(MarketModel()), policy, Config(policy, {}))._check_asset_income(record, paths, end, scale)


def check_affordability(record: dict, savings_rows: list[dict], paths: list[dict], behaviour: dict,
                        policy: dict, scale: float = 1.0) -> list[dict]:
    """For one type: could he pay the cash part of each purchase from what he had that year?"""
    return OnboardingAssessor(FuturePaths(MarketModel()), policy, Config(policy, {}))._check_affordability(record, savings_rows, paths, behaviour, scale)


def check_jurisdictions(record: dict, forecast: dict, policy: dict) -> dict:
    """Countries he named with nothing behind them, and linked countries on a risk list."""
    return OnboardingAssessor(FuturePaths(MarketModel(forecast), forecast, policy), policy, Config(policy, {}))._check_jurisdictions(record, forecast)


def check_declared_sources(forecast: dict, policy: dict) -> list[dict]:
    """Declared sources with no amount and no job or asset behind them (e.g. 'some advisory work').
    Salary, bonuses and savings are explained by the career forecast, so they don't count."""
    return OnboardingAssessor(FuturePaths(MarketModel(forecast), forecast, policy), policy, Config(policy, {}))._check_declared_sources(forecast)


def fit_for_type(type_id: str, wealth_now: dict, affordability: list[dict], asset_checks: list[dict],
                 declared: float, policy: dict, scale: float = 1.0) -> dict:
    """How well his declared figures fit one type. Fit score 0-1."""
    return OnboardingAssessor(FuturePaths(MarketModel()), policy, Config(policy, {}))._fit_for_type(type_id, wealth_now, affordability, asset_checks, declared, scale)


def decide_onboarding(fits: dict, t1_affordability_breach: bool, other_failures: list[str]) -> str:
    """The onboarding rule. fits = {type_id: fit result}."""
    return OnboardingAssessor(FuturePaths(MarketModel()), {}, Config({}, {}))._decide_onboarding(fits, t1_affordability_breach, other_failures)


def stable_outcome(outcome: str, outcomes_when_shifted: dict) -> tuple[str, bool]:
    """If moving the forecasts 10% changes the answer, the case is borderline and a person
    must look at it, so it goes to at least Manual Review."""
    return OnboardingAssessor(FuturePaths(MarketModel()), {}, Config({}, {})).stable_outcome(outcome, outcomes_when_shifted)


def evaluate(record: dict, forecast: dict, savings_rows: list[dict], paths: list[dict],
             policy: dict, scale: float = 1.0) -> dict:
    """Run every onboarding check with all money forecasts multiplied by `scale`."""
    return OnboardingAssessor(FuturePaths(MarketModel(forecast), forecast, policy), policy, Config(policy, {})).evaluate(record, forecast, savings_rows, paths, scale)


# ============================================================================
# 6. The future: forward paths, events, divergence
# ============================================================================

def forward_paths(record: dict, forecast: dict, savings_rows: list[dict], scenario: str,
                  shocks: dict | None = None, event_changes: dict | None = None) -> dict:
    """
    Wealth of every type for the current year and each forecast year in one scenario.
    event_changes = {type_id: (year, extra money change)} adds an event reaction.
    """
    return FuturePaths(MarketModel(forecast), forecast).forward_paths(record, savings_rows, scenario, shocks, event_changes)


def expected_paths(record: dict, forecast: dict, savings_rows: list[dict]) -> dict:
    """Each type's wealth path weighted by the AI's chance of each scenario."""
    return FuturePaths(MarketModel(forecast), forecast).expected_paths(record, savings_rows)


def event_impacts(record: dict, forecast: dict, savings_rows: list[dict]) -> list[dict]:
    """For each event and type: change in 2030 wealth if it happens, and weighted by its chance."""
    return FuturePaths(MarketModel(forecast), forecast).event_impacts(record, savings_rows)


def divergence_years(paths: dict) -> list[dict]:
    """First forecast year each type's range stops overlapping the as-declared type's range."""
    return FuturePaths(MarketModel()).divergence_years(paths)


def monitoring_ranges(forecast: dict, year: int, policy: dict) -> dict:
    """What normal account activity looks like next year, from the as-declared type's signals."""
    return FuturePaths(MarketModel(forecast), forecast, policy).monitoring_ranges(year)








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
def _age_from_birth(date_of_birth, today: str) -> int | None:
    """Whole years between date_of_birth and today, or None if either can't be read."""
    try:
        born = datetime.date.fromisoformat(str(date_of_birth))
        day = datetime.date.fromisoformat(today)
    except (TypeError, ValueError):
        return None
    age = day.year - born.year - ((day.month, day.day) < (born.month, born.day))
    return age if 0 < age < 130 else None


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or value == []


def record_from_documents(extracted: dict, client_ref: str, today: str) -> tuple[dict, list[str]]:
    """Build a client record (the same layout the New Client form saves) from the AI's
    reading of the documents. Returns (record, paths of the fields that came from the documents).

    Every job, including the current one (end_year None), goes into career_history;
    finish_document_record then copies the current job into "career".
    """
    client = extracted.get("client") or {}
    claims = extracted.get("claims") or {}
    composition = extracted.get("composition") or {}

    jobs = [{key: job.get(key) for key in ("start_year", "end_year", "occupation", "seniority", "industry",
                                           "employer_name", "employer_size", "country")}
            for job in extracted.get("jobs") or []]
    # oldest first, current job (no end year) last - the order the forecasting checks
    jobs.sort(key=lambda job: (job["start_year"] if isinstance(job["start_year"], int) else 9999,
                               job["end_year"] if isinstance(job["end_year"], int) else 9999))
    if not jobs:   # always at least one (current) job, so its details get asked for
        jobs = [{"start_year": None, "end_year": None, "occupation": None, "seniority": None,
                 "industry": None, "employer_name": None, "employer_size": None,
                 "country": client.get("country_of_residence")}]

    investments = []
    for asset in extracted.get("assets") or []:
        investments.append({
            "asset_type": asset.get("asset_type"),
            "country": asset.get("country"), "year_acquired": asset.get("year_acquired"),
            "price_paid": asset.get("price_paid_sgd"),
            "current_declared_value": asset.get("current_declared_value_sgd"),
            "payment_method": asset.get("payment_method"),
            "income_produced": asset.get("income_produced_sgd"),   # the AI gives every amount in SGD
        })

    split = {key: composition.get(key) for key in COMPOSITION_KEYS}
    if all(isinstance(v, (int, float)) for v in split.values()):
        split = {key: value / 100 for key, value in split.items()}    # AI gives percentages

    age = client.get("age") or _age_from_birth(client.get("date_of_birth"), today)
    record = {
        "client_ref": client_ref,
        "name": client.get("name"),
        "nationality": client.get("nationality"),
        "current_date": today,
        "career": {"country_of_residence": client.get("country_of_residence"), "age": age},
        "career_history": jobs,
        "investments": investments,
        "claims": {
            "declared_net_worth": claims.get("declared_net_worth_sgd"),
            "expected_aum": claims.get("expected_aum_sgd"),
            "pep_status": claims.get("pep_status"),
            "wealth_countries": list(claims.get("wealth_countries") or []),
            "asset_composition": split,
            "biggest_wealth_jump": claims.get("biggest_wealth_jump_sgd"),
            "wealth_jump_years": claims.get("wealth_jump_years"),
            "declared_counterparties": list(claims.get("declared_counterparties") or []),
        },
        "sow_declaration": extracted.get("sow_declaration"),
        "supporting_documents": [],
    }
    found = [".".join(str(part) for part in item["path"])
             for item in _required_fields(record) if not _missing(record, item)]
    return record, found


def get_path(record: dict, path: list):
    """The value at path (e.g. ["career_history", 0, "start_year"]), or None if it isn't there."""
    value = record
    for part in path:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and isinstance(part, int) and 0 <= part < len(value):
            value = value[part]
        else:
            return None
    return value


def set_path(record: dict, path: list, value) -> dict:
    """Return a copy of record with the value at path replaced."""
    new = copy.deepcopy(record)
    target = new
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    return new


def _field(path: list, short: str, kind: str, group: str = "", label: str = "") -> dict:
    """One form field. label is the full question (when asking); short + group are for the summary."""
    return {"path": path, "short": short, "kind": kind, "group": group,
            "label": label or (f"{group}: {short}" if group else short)}


def _job_group(i: int, job: dict) -> str:
    years = f"{job.get('start_year') or '?'}-{job.get('end_year') or 'present'}"
    return f"Job {i + 1}: {job.get('occupation') or 'job'} at {job.get('employer_name') or 'unknown employer'} ({years})"


def _asset_group(i: int, asset: dict) -> str:
    return f"Asset {i + 1}: {asset.get('asset_type') or 'asset'}"


def _required_fields(record: dict) -> list[dict]:
    """Every field the New Client form insists on, with how it should be asked for."""
    fields = [
        _field(["name"], "Full name", "words"),
        _field(["nationality"], "Nationality", "words"),
        _field(["career", "country_of_residence"], "Country of residence", "words"),
        _field(["career", "age"], "Age", "age"),
    ]
    for i, job in enumerate(record.get("career_history", [])):
        group = _job_group(i, job)
        fields += [
            _field(["career_history", i, "start_year"], "start year", "year", group),
            _field(["career_history", i, "occupation"], "job title", "label", group),
            _field(["career_history", i, "seniority"], "seniority", "label", group),
            _field(["career_history", i, "industry"], "industry", "label", group),
            _field(["career_history", i, "employer_name"], "employer", "label", group),
            _field(["career_history", i, "employer_size"], "employer size", "text", group,
                   f"{group}: employer size (e.g. 1,000-5,000 employees)"),
            _field(["career_history", i, "country"], "country", "words", group),
        ]
    for i, asset in enumerate(record.get("investments", [])):
        group = _asset_group(i, asset)
        fields += [
            _field(["investments", i, "country"], "country", "words", group),
            _field(["investments", i, "year_acquired"], "year acquired", "year", group),
            _field(["investments", i, "price_paid"], "price paid (SGD)", "money_positive", group),
            _field(["investments", i, "payment_method"], "how it was paid for", "payment", group),
            _field(["investments", i, "current_declared_value"], "current value (SGD)", "money", group),
            _field(["investments", i, "income_produced"], "yearly income (SGD)", "money", group,
                   f"{group}: yearly income (SGD, 0 if none)"),
        ]
    fields += [
        _field(["claims", "declared_net_worth"], "Declared net worth (SGD)", "money_positive"),
        _field(["claims", "expected_aum"], "Expected assets to be managed by the bank (SGD)", "money_positive"),
        _field(["claims", "pep_status"], "PEP status", "pep"),
        _field(["claims", "wealth_countries"], "Countries where wealth was generated", "countries",
               label="Countries where wealth was generated (comma-separated)"),
        _field(["claims", "asset_composition"], "Asset composition", "composition",
               label="Asset composition (must add up to 100%)"),
        _field(["sow_declaration"], "Source of wealth declaration", "sow"),
    ]
    return fields


def _missing(record: dict, field: dict) -> bool:
    value = get_path(record, field["path"])
    kind = field["kind"]
    if kind == "composition":
        split = value or {}
        values = [split.get(key) for key in COMPOSITION_KEYS]
        return any(not isinstance(v, (int, float)) for v in values) or abs(sum(values) - 1.0) > 0.005
    if kind == "sow":
        return _blank(value) or len(str(value).strip()) < 50
    if kind == "payment":
        return value not in ("cash", "loan", "asset_sale")
    if kind == "pep":
        return _blank(value)
    return _blank(value)


def missing_client_fields(record: dict) -> list[dict]:
    """The required fields still empty (or unusable) after reading the documents, in form order."""
    return [field for field in _required_fields(record) if _missing(record, field)]


def finish_document_record(record: dict) -> dict:
    """Copy the current job (the one with no end year) into "career", and the first job's start year
    into career_start_year - the same layout the New Client form saves."""
    record = copy.deepcopy(record)
    jobs = record.get("career_history", [])     # kept in document order so the summary lines up
    current = next((job for job in reversed(jobs) if job.get("end_year") in (None, "")), jobs[-1] if jobs else {})
    career = record.setdefault("career", {})
    for key in ("occupation", "seniority", "industry", "employer_name", "employer_size"):
        career[key] = current.get(key)
    starts = [job.get("start_year") for job in jobs if isinstance(job.get("start_year"), int)]
    career["career_start_year"] = min(starts) if starts else None
    return record


def check_document_record(record: dict, today: str, policy: dict | None = None) -> list[str]:
    """Things worth a second look in a record filled from documents. Empty list = nothing spotted."""
    warnings = []
    this_year = int(today[:4])
    age = record.get("career", {}).get("age")
    start = record.get("career", {}).get("career_start_year")
    if isinstance(age, int) and isinstance(start, int) and start < this_year - age + 14:
        warnings.append(f"Career start year {start} means the client started work before age 14.")
    for i, job in enumerate(record.get("career_history", []), start=1):
        s, e = job.get("start_year"), job.get("end_year")
        if isinstance(s, int) and isinstance(e, int) and e < s:
            warnings.append(f"Job {i} ends ({e}) before it starts ({s}).")
        if isinstance(s, int) and s > this_year:
            warnings.append(f"Job {i} starts in the future ({s}).")
    open_jobs = [job for job in record.get("career_history", []) if job.get("end_year") in (None, "")]
    if len(open_jobs) > 1:
        warnings.append(f"{len(open_jobs)} jobs have no end year; only one should be the current job.")
    for i, asset in enumerate(record.get("investments", []), start=1):
        year = asset.get("year_acquired")
        if isinstance(year, int) and isinstance(start, int) and year < start:
            warnings.append(f"Asset {i} was bought in {year}, before the client's career started ({start}).")
    claims = record.get("claims", {})
    worth, aum = claims.get("declared_net_worth"), claims.get("expected_aum")
    if isinstance(worth, (int, float)) and isinstance(aum, (int, float)) and aum > worth:
        warnings.append("Expected assets with the bank are more than the declared net worth.")
    held = sum(a.get("current_declared_value") or 0 for a in record.get("investments", [])
               if isinstance(a.get("current_declared_value"), (int, float)))
    if isinstance(worth, (int, float)) and held > worth * 1.2:
        warnings.append(f"The listed assets are worth {held:,.0f}, well above the declared net worth {worth:,.0f}.")
    warnings += _split_against_assets(record, policy or {})
    return warnings


def _split_against_assets(record: dict, policy: dict) -> list[str]:
    """Does the declared wealth split agree with the assets listed? Catches a value or a percentage
    read wrongly from the documents (or typed wrongly). Only checks kinds of asset that are listed."""
    claims = record.get("claims", {})
    worth = claims.get("declared_net_worth")
    split = claims.get("asset_composition") or {}
    if not isinstance(worth, (int, float)) or worth <= 0:
        return []
    totals = {}
    for asset in record.get("investments", []):
        kind = str(asset.get("asset_type") or "")
        value = asset.get("current_declared_value")
        key = asset_category(kind, policy) if policy.get("asset_categories") else None
        if key and key != "other" and isinstance(value, (int, float)):
            totals[key] = totals.get(key, 0) + value
    warnings = []
    for key, listed in totals.items():
        share = split.get(key)
        if not isinstance(share, (int, float)):
            continue
        declared = share * worth
        if abs(listed - declared) > 0.15 * max(declared, listed):
            label = key.replace("_", " ")
            warnings.append(f"The {label} assets listed are worth {listed:,.0f}, but the declared split puts "
                            f"{share:.0%} ({declared:,.0f}) of the net worth in {label}.")
    return warnings


def _optional_fields(record: dict) -> list[dict]:
    """Fields shown in the summary that the form doesn't insist on."""
    fields = [_field(["career_history", i, "end_year"], "end year (blank = current job)", "year", _job_group(i, job))
              for i, job in enumerate(record.get("career_history", []))]
    return fields + [
        _field(["claims", "biggest_wealth_jump"], "Biggest single-period wealth increase (SGD)", "money"),
        _field(["claims", "wealth_jump_years"], "Over how many years", "money"),
        _field(["claims", "declared_counterparties"], "Known counterparties", "countries"),
    ]


SUMMARY_SECTIONS = {"name": "Client", "nationality": "Client", "career": "Client",
                    "career_history": "Career history", "investments": "Assets",
                    "claims": "Financial claims", "sow_declaration": "Source of wealth declaration"}


def summarise_document_record(record: dict, doc_record: dict) -> list[dict]:
    """One row per field for the officer to check: its value and where it came from.

    source: "documents" (read from the documents, unchanged), "edited" (read from the documents,
    then changed by the officer), "entered" (typed by the officer) or "blank".
    """
    rows = []
    fields = _required_fields(record) + _optional_fields(record)
    order = {name: i for i, name in enumerate(SUMMARY_SECTIONS.values())}
    for field in fields:
        value = get_path(record, field["path"])
        from_docs = get_path(doc_record, field["path"])
        if _blank(value) or (field["kind"] == "composition" and _missing(record, field)):
            source = "blank"
        elif _blank(from_docs) or (field["kind"] == "composition" and _missing(doc_record, field)):
            source = "entered"
        elif from_docs == value:
            source = "documents"
        else:
            source = "edited"
        rows.append({"section": SUMMARY_SECTIONS.get(field["path"][0], "Other"), "group": field["group"],
                     "label": field["short"], "kind": field["kind"], "value": value, "source": source,
                     "path": field["path"]})
    rows.sort(key=lambda row: (order.get(row["section"], 99),
                              row["path"][1] if len(row["path"]) > 2 and isinstance(row["path"][1], int) else -1))
    return rows


CAREER_JOB_KEYS = ["occupation", "seniority", "industry", "employer_name", "employer_size"]


def sync_after_edit(before: dict, after: dict) -> dict:
    """After the officer edits the record, keep "career" and the current job in career_history the same.
    If the profile screen changed "career", copy that into the current job; otherwise copy the
    (possibly edited) current job into "career"."""
    after = copy.deepcopy(after)
    jobs = after.get("career_history", [])
    open_jobs = [i for i, job in enumerate(jobs) if job.get("end_year") in (None, "")]
    changed = any((before.get("career") or {}).get(k) != (after.get("career") or {}).get(k)
                  for k in CAREER_JOB_KEYS)
    if changed and open_jobs:
        for key in CAREER_JOB_KEYS:
            jobs[open_jobs[-1]][key] = after["career"].get(key)
    return finish_document_record(after)

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

VERDICT_LABELS = {PASSED: "PASSED", MANUAL_REVIEW: "MANUAL REVIEW", RISKY: "RISKY", SERIOUS_RISK: "SERIOUS RISK"}

# Crime-scan match levels where every core warning sign fired
FULL_MATCH = CrimeScan.FULL_MATCH
WEAK_MATCH = CrimeScan.WEAK_MATCH
MATCH_LABELS = CrimeScan.MATCH_LABELS

# The six themes a finding can belong to (used to show where the checks agree)
THEMES = {
    "wealth":    "Wealth too high for his career",
    "purchases": "Purchases he couldn't afford",
    "people":    "Unknown or unnamed people giving money",
    "countries": "Money from risky or unexpected countries",
    "sources":   "Sources that don't match his job",
    "pattern":   "Matches a known crime pattern",
}

# The crime scan's warning signs, which theme each belongs to, and how to say it
SIGN_THEMES = CrimeScan.SIGN_THEMES
SIGN_LABELS = CrimeScan.SIGN_LABELS

BENCHMARK_LABELS = {
    "TOTAL_WEALTH": "Total wealth", "UNEXPLAINED_GAP": "Unexplained wealth",
    "VELOCITY": "Wealth growth speed", "JUMP_VS_ECONOMY": "Wealth jump vs economy",
    "LIQUIDITY": "Liquidity", "AUM_FUNDING": "Money brought to the bank",
    "COMPOSITION_PROPERTY": "Asset mix: property", "COMPOSITION_EQUITIES": "Asset mix: listed shares",
    "COMPOSITION_BUSINESS": "Asset mix: private business", "COMPOSITION_CASH": "Asset mix: cash",
    "COUNTERPARTIES": "Counterparties", "JURISDICTION": "Countries", "PEP_STATUS": "PEP status",
}
# Benchmark checks worked out from the forecast's honest story, so they can't "agree" with it
FORECAST_DERIVED = ("UNEXPLAINED_GAP", "PEP_STATUS", "PEER_BENCHMARK")
COMPOSITION_RULES = {"COMPOSITION_PROPERTY": "property", "COMPOSITION_EQUITIES": "listed_equities",
                     "COMPOSITION_BUSINESS": "private_business", "COMPOSITION_CASH": "cash"}

# Status of one check: failed (counts), weak (a loose end), explained (failed on its own, but
# another feature explains it, so it doesn't count), passed, skipped (couldn't run), info.

def _sgd(value) -> str:
    """12345.6 -> 'S$12,346'. Anything that isn't a number -> 'n/a'."""
    return Formatter.sgd(value)


def _check(feature: str, check: str, label: str, theme: str, status: str, detail: str,
           explanation: str = "", group: str = "") -> dict:
    """One finding in the shared shape all three features use."""
    return Check(feature, check, label, theme, status, detail, explanation, group).to_dict()


# ---------------------------------------------------------------------------
# 1. The client record -> the forecasting case (the same for the CLI and the web app)
# ---------------------------------------------------------------------------

_PRESENT_WORDS = CaseReader._PRESENT_WORDS


def _read_amount(text) -> float | None:
    """'1,650,000', 'S$1.65m', '410k', 30 -> a number; None if it can't be read."""
    return CaseReader.read_amount(text)


def _read_year(text) -> int | None:
    return CaseReader().read_year(text)


def _read_payment(text) -> str | None:
    """'Cash', 'mortgage', 'bank loan', 'sold my flat' -> cash / loan / asset_sale."""
    return CaseReader()._read_payment(text)


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
    policy = policy or utilities.policy()
    kinds = policy["verdict"]["document_evidence"]
    evidence = (extracted or {}).get("evidence") or {}
    pay = []
    for row in evidence.get("documented_pay") or []:
        year, amount = _read_year(row.get("year")), _read_amount(row.get("employment_income_sgd"))
        if year and amount and amount > 0 and year not in [p["year"] for p in pay]:
            pay.append({"year": year, "amount": amount, "source_file": row.get("source_file")})
    findings = []
    for row in evidence.get("findings") or []:
        kind = row.get("kind") if row.get("kind") in kinds else "other"
        summary = str(row.get("summary") or "").strip()
        if not summary:
            continue
        findings.append({"kind": kind, "summary": summary, "amount_sgd": _read_amount(row.get("amount_sgd")),
                         "per": row.get("per"), "counterparty": row.get("counterparty"),
                         "country": row.get("country"), "source_files": list(row.get("source_files") or [])})
    order = list(kinds)
    findings.sort(key=lambda f: (not kinds[f["kind"]]["serious"], order.index(f["kind"])))
    return {"files": list(files or []), "read": extracted is not None,
            "documented_pay": sorted(pay, key=lambda p: p["year"]), "findings": findings,
            "notes": [str(n) for n in (extracted or {}).get("notes") or []]}


def calibrate_pay(case: dict, forecast: dict, documented_pay: list[dict], policy: dict) -> tuple[dict, list[dict]]:
    """Use the pay his documents show (tax notices, employment letter) instead of the AI's guess.

    For each job with documented years, every year of that job's forecast pay is scaled by
    documented / AI-typical over those years (the current job's future pay too), so the honest
    story is built on his real pay. The AI never sees these figures; only this arithmetic does.
    Returns (adjusted forecast copy, one row per adjusted job)."""
    return PayCalibrator(CareerSavings(), policy).calibrate(case, forecast, documented_pay)


def document_checks(evidence: dict | None, types: list[dict], policy: dict) -> list[dict]:
    """The documents layer as findings in the shared shape: each fact the declaration leaves out
    or contradicts, and which crime stories it supports."""
    if not evidence or not evidence.get("files"):
        return [_check("documents", "NO_DOCUMENTS", "Supporting documents", "pattern", "info",
                       "No supporting documents were submitted, so nothing was checked against them.")]
    if not evidence.get("read"):
        return [_check("documents", "DOCUMENTS_UNREAD", "Supporting documents", "pattern", "skipped",
                       f"{len(evidence['files'])} document(s) couldn't be read.")]
    kinds = policy["verdict"]["document_evidence"]
    checks = []
    for finding in evidence["findings"]:
        setting = kinds[finding["kind"]]
        stories = [t for t in types if t["category"] in setting["supports"]]
        check = _check("documents", finding["kind"].upper(), setting["label"], setting["theme"],
                       "failed" if setting["serious"] else "weak", finding["summary"],
                       ("Supports " + "; ".join(f"{t['type_id']} {t['name']}" for t in stories) + ".") if stories else "",
                       group="Documents")
        check["sources"] = finding["source_files"]
        check["supports"] = setting["supports"]
        checks.append(check)
    if not checks:
        checks.append(_check("documents", "DOCUMENTS_AGREE", "Supporting documents", "pattern", "passed",
                             f"The {len(evidence['files'])} document(s) agree with his declaration.",
                             group="Documents"))
    return checks


def type_patterns(forecast: dict | None, assessment: dict | None, crime_result: dict | None,
                  typologies: list[dict] | None) -> list[dict]:
    """One row per crime person type: does its money fit (forecast), which researched pattern it
    was built from, and how many of that pattern's warning signs fired (crime scan)."""
    if not forecast or not assessment:
        return []
    matches = {m["typology_id"]: m for m in (crime_result or {}).get("match_results", [])}
    by_id = {t.get("typology_id"): t for t in typologies or []}
    fits = {row["type_id"]: row for row in assessment.get("types", [])}
    rows = []
    for person_type in forecast["types"]["person_types"]:
        type_id = person_type["type_id"]
        if type_id == utilities.BASELINE_TYPE:
            continue
        fit = fits.get(type_id, {})
        typology_id = person_type.get("typology_id")
        if typology_id not in by_id:   # older replies: link by category, as ai_manager.link_typologies does
            typology_id = next((t.get("typology_id") for t in typologies or []
                                if t.get("crime_category") == person_type.get("category")), None)
        match = matches.get(typology_id, {})
        typology = by_id.get(typology_id, {})
        rows.append({
            "type_id": type_id, "name": person_type["name"], "category": person_type["category"],
            "category_name": category_name(person_type["category"]),
            "fits": bool(fit.get("fits")), "fit_score": fit.get("fit_score"),
            "route_years": fit.get("route_years", ""), "enabled_by": fit.get("enabled_by", ""),
            "typology_id": typology_id, "typology_name": typology.get("name"),
            "match": match.get("category") if match else None,
            "fired": list(match.get("core_fired", [])) + list(match.get("supporting_fired", [])) if match else [],
            "quote": (typology.get("source_quotes") or [{}])[0] if typology else {},
            "source_ids": typology.get("source_ids", []),
        })
    return rows


# ---------------------------------------------------------------------------
# 3. The honest story's numbers (shared by the benchmark cross-checks and the forecast checks)
# ---------------------------------------------------------------------------

def honest_numbers(case: dict, forecast: dict, assessment: dict, policy: dict) -> dict:
    """T1's fit, wealth today, liquid wealth, wealth by year and peak pay."""
    return Forecast(policy, Config(policy, utilities.vocabulary())).honest_numbers(case, forecast, assessment)


def _market_growth(history: dict, market_id: str, first: int, last: int) -> float:
    """% a market grew from the end of `first` to the end of `last` (unknown years count as 0)."""
    level = 1.0
    for year in range(first + 1, last + 1):
        level *= 1 + float(history.get(market_id, {}).get(year) or 0.0) / 100
    return (level - 1) * 100


def _best_market_stretch(markets: dict | None, years: int, start: int, end: int) -> tuple[float, int, int] | None:
    """The best `years`-long stretch of his markets during his career: (average % a year, first, last)."""
    if not markets or not markets.get("series"):
        return None
    changes = {}
    for series in markets["series"].values():
        for row in series.get("history", []):
            if row.get("change_pct") is not None:
                changes.setdefault(row["year"], []).append(row["change_pct"])
    yearly = {y: sum(v) / len(v) for y, v in changes.items() if start <= y <= end}
    if not yearly:
        return None
    years = max(1, min(years, end - start + 1))
    best = None
    for last in range(start + years - 1, end + 1):
        window = [yearly.get(y, 0.0) for y in range(last - years + 1, last + 1)]
        average = sum(window) / years
        if best is None or average > best[0]:
            best = (round(average, 1), last - years + 1, last)
    return best


def _best_honest_jump(honest: dict, years: int) -> tuple[float, int, int]:
    """The most the honest story's wealth rose over any `years`-long stretch: (gain, first, last)."""
    by_year = honest["by_year"]
    first_year, last_year = honest["start"], honest["end"]
    years = max(1, min(years, last_year - first_year + 1))
    best = None
    for last in range(first_year + years - 1, last_year + 1):
        gain = by_year[last]["optimistic"] - by_year[last - years]["optimistic"]
        if best is None or gain > best[0]:
            best = (gain, last - years + 1, last)
    return best


def _jump_years(case: dict) -> tuple[float | None, int | None]:
    claims = case.get("claims", {})
    jump, years = claims.get("biggest_wealth_jump"), claims.get("wealth_jump_years")
    if not isinstance(jump, (int, float)) or jump <= 0 or not isinstance(years, (int, float)) or years <= 0:
        return None, None
    return float(jump), max(1, round(years))


def is_pep(case: dict, policy: dict) -> bool:
    status = str(case.get("claims", {}).get("pep_status") or "").strip().lower()
    return status not in policy["verdict"]["no_pep_values"]


# ---------------------------------------------------------------------------
# 4. The checks of each feature, in the shared shape (with the cross-checks)
# ---------------------------------------------------------------------------

def benchmark_checks(case: dict, bench_input: dict | None, ai_data: dict | None, findings: list[dict] | None,
                     honest: dict | None, assessment: dict | None, declaration: dict | None,
                     markets: dict | None, types: list[dict], policy: dict) -> list[dict]:
    """The peer benchmark's checks, each cross-checked against the forecast: a failure the
    honest forecast explains is marked "explained" and doesn't count towards the verdict."""
    settings = policy["verdict"]
    claims = case.get("claims", {})
    worth = claims.get("declared_net_worth") or 0
    split = claims.get("asset_composition") or {}
    liquid_share = (split.get("listed_equities") or 0) + (split.get("cash") or 0)
    declared_liquid = liquid_share * worth
    t1 = honest["t1"] if honest else None
    checks = []
    by_rule = {f["rule_id"]: f for f in findings or []}
    not_checked = "Couldn't be cross-checked: the forecast didn't finish."

    def failed_or_explained(failed: bool, explained: bool | None, yes: str, no: str) -> tuple[str, str]:
        if not failed:
            return "passed", ""
        if explained is None:
            return "failed", not_checked
        return ("explained", yes) if explained else ("failed", no)

    if findings is None:
        checks.append(_check("benchmark", "PEER_BENCHMARK", "Peer benchmark", "wealth", "skipped",
                             "The peer benchmark couldn't run, so declared figures weren't compared with peers."))

    # Total wealth vs peers
    if "TOTAL_WEALTH" in by_rule:
        expected = ai_data["expected_wealth"]
        ratio = worth / expected if expected else 0
        status, why = failed_or_explained(
            by_rule["TOTAL_WEALTH"]["failed"], t1["net_worth_fits"] if t1 else None,
            f"Explained: the honest forecast reaches {_sgd(t1['wealth_now']['cautious'])} to "
            f"{_sgd(t1['wealth_now']['optimistic'])}, which "
            + ("covers it." if worth <= t1["wealth_now"]["optimistic"] else
               f"is within the {policy['tolerance']['net_worth']:.0%} tolerance.") if t1 else "",
            f"Not explained: the honest forecast reaches at most {_sgd(t1['wealth_now']['optimistic'])}." if t1 else "")
        checks.append(_check("benchmark", "TOTAL_WEALTH", BENCHMARK_LABELS["TOTAL_WEALTH"], "wealth", status,
                             f"Declared {_sgd(worth)} vs about {_sgd(expected)} for peers in this economy "
                             f"({ratio:.1f}x; flagged above {LIMITS['total_wealth']}x)", why))

    # NEW: how much the honest story can't explain, in money and in years of his pay
    if honest:
        reach = t1["wealth_now"]["optimistic"]
        gap = worth - reach
        over = worth > reach * (1 + policy["tolerance"]["net_worth"])
        years = gap / honest["peak_pay"] if honest["peak_pay"] > 0 else None
        if over:
            detail = (f"{_sgd(gap)} of the declared {_sgd(worth)} is beyond the most the honest story reaches "
                      f"({_sgd(reach)})" + (f": about {years:.0f} years of his peak pay "
                                            f"({_sgd(honest['peak_pay'])} a year)" if years else ""))
        elif worth > reach:
            detail = (f"The honest story reaches up to {_sgd(reach)}, within the "
                      f"{policy['tolerance']['net_worth']:.0%} tolerance of the declared {_sgd(worth)}.")
        else:
            detail = f"The honest story reaches up to {_sgd(reach)}, which covers the declared {_sgd(worth)}."
        checks.append(_check("benchmark", "UNEXPLAINED_GAP", BENCHMARK_LABELS["UNEXPLAINED_GAP"], "wealth",
                             "failed" if over else "passed", detail))
    else:
        checks.append(_check("benchmark", "UNEXPLAINED_GAP", BENCHMARK_LABELS["UNEXPLAINED_GAP"], "wealth",
                             "skipped", "Needs the honest forecast, which didn't finish."))

    # Wealth growth speed vs peers, cross-checked with the honest path
    jump, jump_years = _jump_years(case)
    velocity_failed = velocity_status = None
    if "VELOCITY" in by_rule:
        finding = by_rule["VELOCITY"]
        if finding["detail"].startswith("Skipped") or jump is None:
            checks.append(_check("benchmark", "VELOCITY", BENCHMARK_LABELS["VELOCITY"], "wealth", "skipped",
                                 "No biggest wealth jump was recorded, so growth speed wasn't checked."))
        else:
            velocity_failed = finding["failed"]
            expected = ai_data["expected_velocity"]
            per_year = jump / jump_years
            explained = None
            if honest:
                best = _best_honest_jump(honest, jump_years)
                explained = jump <= best[0] * (1 + policy["tolerance"]["net_worth"])
            status, why = failed_or_explained(
                velocity_failed, explained,
                f"Explained: the honest story could gain up to {_sgd(best[0])} in {best[1]}-{best[2]}."
                if honest else "",
                f"Not explained: the honest story gains at most {_sgd(best[0])} in any {jump_years}-year "
                f"stretch (best {best[1]}-{best[2]})." if honest else "")
            velocity_status = status
            checks.append(_check("benchmark", "VELOCITY", BENCHMARK_LABELS["VELOCITY"], "wealth", status,
                                 f"Biggest jump {_sgd(jump)} over {jump_years} year(s) = {_sgd(per_year)} a year vs "
                                 f"about {_sgd(expected)} a year for peers ({per_year / expected if expected else 0:.1f}x; "
                                 f"flagged above {LIMITS['velocity']}x)", why))

    # NEW: was the economy strong enough for such a jump?
    if jump is None:
        checks.append(_check("benchmark", "JUMP_VS_ECONOMY", BENCHMARK_LABELS["JUMP_VS_ECONOMY"], "wealth",
                             "skipped", "No biggest wealth jump was recorded."))
    else:
        start, end = utilities.career_years(case)
        best = _best_market_stretch(markets, jump_years, start, end)
        if best is None or velocity_failed is None:
            checks.append(_check("benchmark", "JUMP_VS_ECONOMY", BENCHMARK_LABELS["JUMP_VS_ECONOMY"], "wealth",
                                 "skipped", "Needs the economy forecast and the peer growth speed."))
        else:
            average, first, last = best
            boom = settings["booming_market_pct"]
            note = "The jump's own years aren't recorded, so his markets' best stretch is used."
            if not velocity_failed:
                status, detail = "passed", (f"Within the peer range. His markets' best {jump_years}-year stretch "
                                            f"was {first}-{last} ({average:+.1f}% a year).")
            elif average >= boom:
                status, detail = "explained", (f"Faster than peers, but his markets boomed in {first}-{last} "
                                               f"({average:+.1f}% a year), which can explain it. {note}")
            elif velocity_status == "explained":
                status, detail = "explained", (f"Faster than peers and his markets never boomed (best {jump_years}-"
                                               f"year stretch {first}-{last}, {average:+.1f}% a year), but the "
                                               f"honest story's own growth explains the jump (see growth speed).")
            else:
                status, detail = "failed", (f"Faster than peers, and his markets never boomed: their best "
                                            f"{jump_years}-year stretch was {first}-{last} at {average:+.1f}% a year "
                                            f"(a boom is {boom:g}% or more). {note}")
            checks.append(_check("benchmark", "JUMP_VS_ECONOMY", BENCHMARK_LABELS["JUMP_VS_ECONOMY"], "wealth",
                                 status, detail))

    # Liquidity vs peers, cross-checked with the honest story's cash and shares
    if "LIQUIDITY" in by_rule:
        declared_pct = bench_input["listed_equities"] + bench_input["cash"]
        explained = (declared_liquid <= honest["liquid"]["optimistic"] * (1 + settings["aum_tolerance"])
                     if honest else None)
        status, why = failed_or_explained(
            by_rule["LIQUIDITY"]["failed"], explained,
            f"Explained: the honest story leaves him up to {_sgd(honest['liquid']['optimistic'])} in cash and "
            f"shares, enough for the {_sgd(declared_liquid)} he declares." if honest else "",
            f"Not explained: he declares {_sgd(declared_liquid)} in cash and shares; the honest story leaves "
            f"at most {_sgd(honest['liquid']['optimistic'])}." if honest else "")
        checks.append(_check("benchmark", "LIQUIDITY", BENCHMARK_LABELS["LIQUIDITY"], "wealth", status,
                             f"{declared_pct}% of his wealth in cash and listed shares vs about "
                             f"{ai_data['expected_liquidity']:g}% for peers ("
                             + (f"{declared_pct / ai_data['expected_liquidity']:.1f}x; " if ai_data['expected_liquidity'] else "")
                             + f"flagged above {LIMITS['liquidity']}x)", why))

    # NEW: can he fund the money he says he'll bring to the bank?
    aum = claims.get("expected_aum")
    if isinstance(aum, (int, float)) and aum > 0:
        tolerance = 1 + settings["aum_tolerance"]
        short_own = aum > declared_liquid * tolerance
        short_honest = honest is not None and aum > honest["liquid"]["optimistic"] * tolerance
        detail = f"Plans to bring {_sgd(aum)}; by his own split he holds {_sgd(declared_liquid)} in cash and shares"
        if honest:
            detail += f", and the honest story leaves him up to {_sgd(honest['liquid']['optimistic'])}"
        checks.append(_check("benchmark", "AUM_FUNDING", BENCHMARK_LABELS["AUM_FUNDING"], "wealth",
                             "failed" if short_own or short_honest else "passed", detail + "."))
        checks[-1]["independent"] = short_own        # short by his OWN figures, not only by the forecast

    # Asset mix vs peers, cross-checked with his listed assets and their markets
    history = market_history({"markets": markets}) if markets and markets.get("series") else {}
    asset_checks = {c["asset_index"]: c for c in (assessment or {}).get("asset_checks", [])
                    if c["rule_id"] == "ASSET_VALUE"}
    models = {m["asset_index"]: m for m in (honest or {}).get("models", [])}
    for rule, key in COMPOSITION_RULES.items():
        if rule not in by_rule:
            continue
        declared_pct = bench_input[key]
        expected_pct = ai_data[f"expected_{key}"]
        declared_amount = (split.get(key) or 0) * worth
        explained, yes, no = None, "", ""
        if honest:
            if key == "cash":
                reach = honest["cash"]["optimistic"]
                explained = 0 < declared_amount <= reach * (1 + settings["composition_tolerance"])
                yes = f"Explained: the honest story leaves him up to {_sgd(reach)} in cash."
                no = f"Not explained: the honest story leaves him at most {_sgd(reach)} in cash."
            else:
                indexes = [i for i, a in enumerate(case.get("investments", []))
                           if asset_category(a["asset_type"], policy) == key]
                listed = sum(case["investments"][i]["current_declared_value"] for i in indexes)
                values_ok = all(not asset_checks.get(i, {}).get("failed") for i in indexes)
                close = listed > 0 and abs(listed - declared_amount) <= settings["composition_tolerance"] * max(
                    listed, declared_amount)
                explained = bool(indexes) and close and values_ok
                market_note = ""
                if indexes and history:
                    first = case["investments"][indexes[0]]
                    model = models.get(indexes[0])
                    if model and model["exposures"]:
                        top = max(model["exposures"], key=lambda e: e["sensitivity"]["typical"])
                        growth = _market_growth(history, top["market_id"], int(first["year_acquired"]), honest["end"])
                        market_note = f" ({top['market_id']} {growth:+.0f}% since {first['year_acquired']})"
                yes = (f"Explained: his {key.replace('_', ' ')} assets ({_sgd(listed)}) match that share and their "
                       f"markets explain their values{market_note}.")
                no = ("Not explained: " + (f"his {key.replace('_', ' ')} assets add up to {_sgd(listed)}, not "
                                           f"{_sgd(declared_amount)}" if indexes else
                                           f"no {key.replace('_', ' ')} assets are listed")
                      + ("" if values_ok else ", and their declared values are above what their markets explain")
                      + ".")
        status, why = failed_or_explained(by_rule[rule]["failed"], explained, yes, no)
        checks.append(_check("benchmark", rule, BENCHMARK_LABELS[rule], "wealth", status,
                             f"Declared {declared_pct}% vs about {expected_pct:g}% for peers "
                             f"(off by {abs(declared_pct - expected_pct):g} points; flagged above "
                             f"{LIMITS['composition']})", why, group="Asset mix"))

    # Counterparties not expected for his career, cross-checked with his declaration
    if "COUNTERPARTIES" in by_rule:
        words = settings["service_provider_words"]
        providers = [c for c in bench_input.get("declared_counterparties", [])
                     if any(re.search(rf"\b{re.escape(w)}\b", c.lower()) for w in words)]
        # Service providers were already excluded by run_benchmark — unknown comes from its finding
        unknown = calculate_counterparties([c for c in bench_input.get("declared_counterparties", [])
                                            if c not in providers], ai_data.get("expected_counterparties", []))
        sources = (declaration or {}).get("claimed_sources", [])

        def backed(name: str) -> bool:
            low = name.lower()
            return any((source.get("linked_position_index") is not None
                        or source.get("linked_asset_index") is not None)
                       and source.get("counterparty")
                       and (low in source["counterparty"].lower() or source["counterparty"].lower() in low)
                       for source in sources)
        explained = all(backed(name) for name in unknown) if declaration else None
        status, why = failed_or_explained(
            by_rule["COUNTERPARTIES"]["failed"], explained,
            "Explained: each one is named in his declaration as linked to one of his jobs or assets.",
            "Not explained: not every one is linked to a job or asset in his declaration.")
        checks.append(_check("benchmark", "COUNTERPARTIES", BENCHMARK_LABELS["COUNTERPARTIES"], "people", status,
                             ((f"{len(unknown)} not usual for his career: {', '.join(unknown)} "
                               f"(flagged when more than {LIMITS['counterparties']})") if unknown
                              else "All usual for his career.")
                             + (f" Banks, brokers and law firms are left out: {', '.join(providers)}." if providers else ""),
                             why))

    # Countries not expected for his career, cross-checked with the forecast's countries
    if "JURISDICTION" in by_rule:
        unknown = calculate_jurisdiction(bench_input.get("declared_countries", []),
                                         ai_data.get("expected_jurisdiction", []))
        explained = None
        if assessment:
            juris = assessment["jurisdiction"]
            flagged = {same_country(c, policy) for c in juris["unexplained_countries"] + juris["listed_countries"]}
            explained = not any(same_country(c, policy) in flagged for c in unknown)
        status, why = failed_or_explained(
            by_rule["JURISDICTION"]["failed"], explained,
            "Explained: each has a job, asset or declared source behind it, and none is on a risk list.",
            "Not explained: at least one has nothing behind it or is on a risk list.")
        checks.append(_check("benchmark", "JURISDICTION", BENCHMARK_LABELS["JURISDICTION"], "countries", status,
                             (f"{len(unknown)} not usual for his career: {', '.join(unknown)} "
                              f"(flagged when more than {LIMITS['jurisdiction']})") if unknown
                             else "All usual for his career.", why))

    # NEW: PEP status (a PEP always needs a person to look, and a public-office crime story matters more)
    status_text = str(claims.get("pep_status") or "None")
    pep = is_pep(case, policy)
    pep_types = [t for t in types if t["fits"] and t["category"] in settings["pep_crime_categories"]]
    checks.append(_check(
        "benchmark", "PEP_STATUS", BENCHMARK_LABELS["PEP_STATUS"], "pattern", "failed" if pep else "passed",
        f"{status_text}" + (" - a politically exposed person needs enhanced due diligence" if pep else " - not a PEP"),
        ("A public-office crime story also fits his money: "
         + "; ".join(f"{t['type_id']} {t['name']}" for t in pep_types) + ".") if pep and pep_types else ""))
    # Which failures are evidence of their own (from peers or his own figures), rather than the
    # forecast's honest story seen again: only these can be the "second feature" that agrees.
    for item in checks:
        item.setdefault("independent", item["check"] not in FORECAST_DERIVED)
        item["optional"] = item["status"] == "skipped" and item["detail"].startswith("No biggest wealth jump")
    return checks


def describe_piece(case: dict, piece: str | None) -> str:
    """A forecast piece's name in words: 'call2_earnings.asset.0' -> 'asset 1 (Property - Condo, Bishan)'."""
    piece = piece or ""
    parts = piece.split(".")
    assets, jobs = case.get("investments", []), utilities.career_positions(case)
    if len(parts) == 3 and parts[1] == "asset" and parts[2].isdigit() and int(parts[2]) < len(assets):
        return f"asset {int(parts[2]) + 1} ({assets[int(parts[2])].get('asset_type', 'asset')})"
    if len(parts) == 3 and parts[1] == "position" and parts[2].isdigit() and int(parts[2]) < len(jobs):
        job = jobs[int(parts[2])]
        return f"the pay for job {int(parts[2]) + 1} ({job.get('occupation')} at {job.get('employer_name')})"
    names = {"step0_declaration": "reading the declaration", "call1_markets.list": "choosing the markets",
             "call2_earnings.future_pay": "his future pay", "call3_types.list": "the list of person types",
             "call4_events.list": "the future events"}
    if piece in names:
        return names[piece]
    if len(parts) == 3 and parts[0] == "call1_markets":
        return f"the {parts[2]} market figures"
    if len(parts) == 3 and parts[0].startswith("call3_types"):
        return f"how person type {parts[2]} behaves"
    if len(parts) == 3 and parts[0].startswith("call4_events"):
        return f"how person type {parts[2]} reacts to events"
    return piece or "an early step"


def forecast_checks(case: dict, assessment: dict | None, honest: dict | None, types: list[dict],
                    failed_step: str | None, policy: dict, unmodelled: list[dict] | None = None) -> list[dict]:
    """The forecast's checks in the shared shape, plus the two new ones (wealth jump, liquid wealth).
    failed_step: why the forecast stopped, in words (if it did)."""
    return Forecast(policy)._forecast_checks(case, assessment, honest, types, failed_step, unmodelled)


def crime_checks(crime_result: dict | None, research: dict | None, typologies: list[dict] | None,
                 types: list[dict], forecast_ran: bool) -> list[dict]:
    """The crime scan's patterns in the shared shape: how well each one matches, and which
    person type was built from it."""
    return CrimeScan()._crime_checks(crime_result, research, typologies, types, forecast_ran)


# ---------------------------------------------------------------------------
# 5. One verdict
# ---------------------------------------------------------------------------

def _agreement(checks: list[dict]) -> list[dict]:
    """Group the findings that count (failed, or a crime warning sign) by theme, most agreement first."""
    themes: dict = {}
    for check in checks:
        if check["status"] not in ("failed", "weak"):
            continue
        if check["feature"] == "crime" and check.get("signs"):
            keys = {SIGN_THEMES.get(sign, "pattern") for sign in check["signs"]}
            if check["status"] == "failed":
                keys.add("pattern")
        elif check["status"] == "failed":
            keys = {check["theme"]}
        else:
            continue
        for key in keys:
            entry = themes.setdefault(key, {"theme": key, "title": THEMES[key], "features": [], "lines": []})
            if check["feature"] not in entry["features"]:
                entry["features"].append(check["feature"])
            detail = check["detail"]
            if check["feature"] == "crime" and key != "pattern":   # only the warning signs of this theme
                detail = "warning signs fired: " + ", ".join(
                    SIGN_LABELS.get(sign, sign) for sign in check["signs"] if SIGN_THEMES.get(sign) == key)
            entry["lines"].append(f"{check['feature'].capitalize()}: {check['label']} - {detail}")
            entry.setdefault("short", []).append(f"{check['feature'].capitalize()}: {check['label']}")
    order = list(THEMES)
    return sorted(themes.values(), key=lambda t: (-len(t["features"]), order.index(t["theme"])))


def _documents(assessment: dict | None, bench: list[dict], crime: list[dict], typologies: list[dict] | None,
               case: dict, policy: dict, docs: list[dict] | None = None) -> list[dict]:
    """Documents to ask for: first for what his own documents contradict, then the forecast's (failed
    checks, then the ones that rule out the most stories), the benchmark's failed checks, and the
    matched patterns' typical documents."""
    names = utilities.vocabulary().get("document_codes", {})
    settings = policy["verdict"]
    wanted, seen = [], set()

    def add(document: str, reason: str) -> None:
        key = document.strip().lower()
        if key and key not in seen:
            seen.add(key)
            wanted.append({"document": document, "reason": reason})

    kinds = settings["document_evidence"]
    for check in docs or []:
        if check["status"] in ("failed", "weak") and check["check"].lower() in kinds:
            for code in kinds[check["check"].lower()]["documents"]:
                if code in names:
                    add(names[code], f"His documents show: {check['label'].lower()}")
    for document in (assessment or {}).get("documents", []):
        add(document["document"], document["reason"])
    for check in bench:
        if check["status"] != "failed":
            continue
        rule = "COMPOSITION" if check["check"].startswith("COMPOSITION") else check["check"]
        for code in settings["benchmark_documents"].get(rule, []):
            if code in names:
                add(names[code], f"Benchmark check failed: {check['label'].lower()}")
    by_id = {t.get("typology_id"): t for t in typologies or []}
    for check in crime:
        if check["check"] == "TYPOLOGY" and check["status"] in ("failed", "weak"):
            name = check["label"].split(" [")[0]
            for document in by_id.get(check["typology_id"], {}).get("typical_documents", []):
                add(document, f"Matches the known pattern: {name}")
    return wanted[:settings["max_documents"]]


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
    settings = policy["verdict"]
    forecast, assessment = parts.get("forecast"), parts.get("forecast_assessment")
    honest = None
    if forecast and assessment:
        honest = honest_numbers(case, forecast, assessment, policy)
    types = type_patterns(forecast, assessment, parts.get("crime_result"), parts.get("typologies"))
    evidence = parts.get("evidence")
    docs = document_checks(evidence, types, policy)
    for t in types:                                 # which of his documents support each crime story
        t["documents"] = [c["label"] for c in docs if c["status"] == "failed" and t["category"] in c.get("supports", [])]
    bench = benchmark_checks(case, parts.get("benchmark_input"), parts.get("benchmark_ai"),
                             parts.get("benchmark_findings"), honest, assessment, parts.get("declaration"),
                             parts.get("markets"), types, policy)
    fore = forecast_checks(case, assessment, honest, types, parts.get("failed_step"), policy,
                           (forecast or {}).get("earnings", {}).get("fallback_assets"))
    for adjusted in reversed(parts.get("pay_adjustments") or []):
        fore.insert(1, _check("forecast", "PAY_FROM_DOCUMENTS", "Pay taken from his documents", "wealth", "info",
                              f"The AI estimated {_sgd(adjusted['ai_pay'])} for {adjusted['year']}; "
                              f"{adjusted['source_file'] or 'his documents'} shows {_sgd(adjusted['documented_pay'])}, "
                              f"so his pay as {adjusted['job']} was scaled x{adjusted['ratio']:g} for every year of that job."))
    crime = crime_checks(parts.get("crime_result"), parts.get("research"), parts.get("typologies"), types,
                         forecast is not None)
    checks = bench + fore + crime + docs

    triggers: list[tuple[str, str]] = []           # (level, reason)

    def flag(level: str, reason: str) -> None:
        triggers.append((level, reason))

    unexplained = [c for c in bench if c["status"] == "failed" and c.get("independent")]
    fitting = [t for t in types if t["fits"]]
    backed = [t for t in fitting if t["match"] in FULL_MATCH]
    contradicted = [c for c in docs if c["status"] == "failed"]

    if honest:
        t1 = honest["t1"]
        if not t1["fits"]:
            agrees = ([f"{t['type_id']}'s warning signs fired ({MATCH_LABELS[t['match']]} match)" for t in backed]
                      + [f"his documents support {t['type_id']} ({', '.join(t['documents']).lower()})"
                         for t in fitting if t["documents"]]
                      + [f"the benchmark's {c['label'].lower()} check failed and the forecast can't explain it"
                         for c in unexplained])
            if fitting and agrees:
                flag(SERIOUS_RISK, "The honest story can't explain his wealth, a crime story can ("
                     + "; ".join(f"{t['type_id']} {t['name']}" for t in fitting) + "), and another check agrees: "
                     + "; ".join(agrees[:3]) + ".")
            elif fitting:
                flag(RISKY, "The honest story can't explain his wealth and a crime story can ("
                     + "; ".join(f"{t['type_id']} {t['name']}" for t in fitting)
                     + "), but no other check agrees yet.")
            else:
                flag(RISKY, "No story explains his wealth: neither the honest story nor any crime story reaches "
                     f"{_sgd(case['claims']['declared_net_worth'])}.")
        elif not t1["fits_at_typical"]:
            flag(RISKY, "The honest story only reaches his declared wealth at its optimistic edge.")
        for check in fore:
            if check["check"] == "AFFORDABILITY" and check["status"] == "failed":
                flag(RISKY, f"He couldn't have afforded the {check['label'].split(':')[0]}: {check['detail']}.")
        for t in backed:
            flag(RISKY, f"{t['type_id']} {t['name']} fits his money AND its researched pattern's warning signs "
                        f"fired ({MATCH_LABELS[t['match']]} match).")
        if assessment["borderline"]:
            flag(MANUAL_REVIEW, "The result is borderline: it changes when every forecast moves 10%.")
        other = [c for c in fore if c["status"] == "failed"
                 and c["check"] in ("ASSET_VALUE", "ASSET_INCOME", "JURISDICTION", "UNQUANTIFIED_SOURCE", "WEALTH_JUMP")]
        if other:
            flag(MANUAL_REVIEW, f"{len(other)} forecast check(s) failed: "
                 + "; ".join(c["label"] for c in other[:4])
                 + (f"; and {len(other) - 4} more." if len(other) > 4 else "."))

    # What his own documents show against what he declared
    if contradicted:
        found = "; ".join(c["label"].lower() for c in contradicted)
        others = []
        if honest and not honest["t1"]["fits"]:
            others.append("the honest story can't explain his wealth")
        elif honest and not honest["t1"]["fits_at_typical"]:
            others.append("the honest story only reaches his wealth at its optimistic edge")
        others += [f"{t['type_id']} {t['name']} fits his money" for t in fitting]
        others += [f"the crime scan matched \"{c['label'].split(' [')[0]}\"" for c in crime
                   if c["check"] == "TYPOLOGY" and c["status"] == "failed"]
        others += [f"the benchmark's {c['label'].lower()} check failed" for c in unexplained]
        others += [f"he couldn't have afforded the {c['label'].split(':')[0]}" for c in fore
                   if c["check"] == "AFFORDABILITY" and c["status"] == "failed"]
        if len(contradicted) >= settings["min_serious_document_findings"] and others:
            flag(SERIOUS_RISK, f"His documents contradict his declaration ({len(contradicted)} findings: {found}), "
                               "and another check agrees: " + "; ".join(others[:3]) + ".")
        else:
            flag(RISKY, f"His documents contradict his declaration: {found}.")
    loose = [c for c in docs if c["status"] == "weak"]
    if loose:
        flag(MANUAL_REVIEW, "His documents show things to check: " + "; ".join(c["label"].lower() for c in loose) + ".")

    if any(c["check"] == "AUM_FUNDING" and c["status"] == "failed" for c in bench):
        flag(RISKY, "He plans to bring more money to the bank than his cash and shares can fund.")
    if is_pep(case, policy):
        pep_types = [t for t in fitting if t["category"] in settings["pep_crime_categories"]]
        if pep_types:
            flag(RISKY, "He is a PEP and a public-office crime story fits his money ("
                 + "; ".join(f"{t['type_id']} {t['name']}" for t in pep_types) + ").")
        else:
            flag(MANUAL_REVIEW, f"He is a PEP ({case['claims']['pep_status']}): a KYC officer must review him.")
    counted = [c for c in unexplained if c["check"] != "AUM_FUNDING"]      # AUM has its own rule above
    if len(counted) >= settings["unexplained_benchmark_for_risky"]:
        flag(RISKY, f"{len(counted)} benchmark checks failed that the forecast can't explain: "
             + ", ".join(c["label"].lower() for c in counted) + ".")
    elif counted:
        flag(MANUAL_REVIEW, "Benchmark check(s) failed that the forecast can't explain: "
             + ", ".join(c["label"].lower() for c in counted) + ".")
    built = {t["typology_id"] for t in fitting if t["typology_id"]}
    for check in crime:
        if check["check"] == "TYPOLOGY" and check.get("match") not in (None, "no_match"):
            level = settings["pattern_alone"].get(check["match"], PASSED)
            if level != PASSED and check["typology_id"] not in built:
                flag(level, f"Known pattern \"{check['label'].split(' [')[0]}\": {check['detail']}.")
    for part in parts.get("not_run", []):
        flag(MANUAL_REVIEW, f"{part} couldn't run, so a person must check what it would have covered.")

    level = max((t[0] for t in triggers), key=lambda lv: SEVERITY[lv], default=PASSED)
    reasons = []
    for trigger_level, reason in sorted(triggers, key=lambda t: -SEVERITY[t[0]]):
        if reason not in [r["text"] for r in reasons]:
            reasons.append({"level": trigger_level, "text": reason})
    summary = reasons[0]["text"] if reasons else "Every check came back clean or was explained by another feature."

    # Next review: by the verdict, sooner if the forecast says two stories can be told apart earlier
    current = case["current_date"]
    review = add_months(current, policy["review_interval_months"][level])
    for watch in (assessment or {}).get("watch_dates", []):
        if "told apart" in watch["what"] and current < watch["date"] < review:
            review = watch["date"]

    groups: dict = {}
    for check in bench + fore + docs:
        groups.setdefault((check["feature"], check["group"]), []).append(check["status"])
    clean = [group for (feature, group), statuses in groups.items()
             if statuses and all(s == "passed" for s in statuses)]

    return {
        "client_ref": case["client_ref"],
        "name": case.get("name", ""),
        "assessed_on": current,
        "policy_version": policy["policy_version"],
        "verdict": level,
        "verdict_label": VERDICT_LABELS[level],
        "next_step": policy["routing"][level],
        "next_review_date": review,
        "summary": summary,
        "reasons": reasons,
        "agreement": _agreement(checks),
        "benchmark": bench,
        "forecast": fore,
        "crime": crime,
        "document_findings": docs,
        "types": types,
        "documents": (_documents(assessment, bench, crime, parts.get("typologies"), case, policy, docs)
                      if level != PASSED else []),
        "clean": clean,
        "not_run": list(parts.get("not_run", [])),
        "notes": list(parts.get("notes", [])),
        "evidence": _evidence(case, parts, assessment, honest),
    }


# Notes from the run that are routine bookkeeping, not something the officer must look at
_ROUTINE_NOTES = ("converted to", "renumbered", "kept first")


def _evidence(case: dict, parts: dict, assessment: dict | None, honest: dict | None) -> list[dict]:
    """The detail behind the verdict, shown under "Full evidence"."""
    sections = []
    evidence = parts.get("evidence") or {}
    if evidence.get("files"):
        lines = [f"Read: {', '.join(evidence['files'])}"]
        lines += [f"Pay shown for {p['year']}: {_sgd(p['amount'])} ({p['source_file'] or 'documents'})"
                  for p in evidence.get("documented_pay", [])]
        lines += [f"{f['summary']} ({', '.join(f['source_files'])})" for f in evidence.get("findings", [])]
        if not evidence.get("findings"):            # the findings already say what the notes say
            lines += [f"Reader's note: {note}" for note in evidence.get("notes", [])]
        sections.append({"title": "What his documents show", "lines": lines})
    reports = (parts.get("research") or {}).get("reports", [])
    sections.append({"title": "Research reports", "lines": [
        f"[{r.get('report_id', '?')}] {r.get('organisation', '')}{' (' + str(r['year']) + ')' if r.get('year') else ''}"
        f" - {r.get('title', '')}" for r in reports] or ["No research reports were found."]})
    typology_lines = []
    for t in parts.get("typologies") or []:
        typology_lines.append(f"{t.get('name')} ({category_name(t.get('crime_category', ''))})")
        if t.get("description"):
            typology_lines.append(f"    {t['description']}")
    sections.append({"title": "Sector typologies", "lines": typology_lines or ["No verified typologies."]})
    if assessment and honest:
        sections.append({"title": "Person types", "lines": [
            f"{row['type_id']} {row['name']} - {'fits' if row['fits'] else 'does not fit'} "
            f"(fit {row['fit_score']:.2f}); wealth today "
            f"{_sgd(row['wealth_now']['cautious'])} to {_sgd(row['wealth_now']['optimistic'])}; route {row['route']}"
            for row in assessment["types"]]})
        documented = {p["year"]: p for p in evidence.get("documented_pay", [])}
        rows = honest["savings_rows"]
        shown = [row for i, row in enumerate(rows) if i % 5 == 0 or i == len(rows) - 1 or row["year"] in documented]
        sections.append({"title": "Career savings (typical, every 5 years)", "lines": [
            f"{row['year']}: pay {_sgd(row['total_pay']['typical'])}"
            + (f" (documents show {_sgd(documented[row['year']]['amount'])})" if row["year"] in documented else "")
            + f", saved {_sgd(row['saved']['typical'])}, savings so far {_sgd(row['savings']['typical'])}"
            for row in shown]})
        events = {}
        for row in assessment["event_impacts"]:
            events.setdefault((row["year"], row["event_id"], row["event"], row["chance"]), []).append(
                f"{row['type_id']} {'+' if row['impact'] >= 0 else ''}{_sgd(row['impact'])}")
        sections.append({"title": "Future events and how each story's 2030 wealth would change", "lines": [
            f"{year} {name} ({chance:.0%} chance): " + ", ".join(impacts)
            for (year, event_id, name, chance), impacts in sorted(events.items())] or ["No events."]})
        sections.append({"title": "When the stories can be told apart", "lines": [
            f"T1 and {d['type_id']}: " + (f"from {d['distinguishable_from']}" if d["distinguishable_from"]
                                         else "not within the forecast years (his wealth alone won't tell them apart)")
            for d in assessment["divergence"]] or ["No crime stories to tell apart."]})
        names = utilities.vocabulary().get("signal_codes", {})
        sections.append({"title": "Normal account activity next year (honest story)", "lines": [
            f"{names.get(code, code)}: up to {_sgd(r['amount_max'])} a year"
            + (f" in up to {r['count_max']:g} payments" if r["count_max"] >= 2 else "")
            for code, r in assessment["monitoring_ranges"].items()] or ["None forecast."]})
        quality = assessment["data_quality"]
        sections.append({"title": "Data quality", "lines": [
            f"{quality['market_figures']} market figures, {quality['unverified_share']:.0%} from AI memory "
            "(not checked online) or missing."] + [f"Gap: {gap}" for gap in quality["data_gaps"]]})
        sections.append({"title": "Stability test (the forecast's own result)", "lines": [
            f"Forecasts {shift}: {VERDICT_LABELS.get(outcome, outcome)}"
            for shift, outcome in assessment["stability"].items()]})
    warnings = list(dict.fromkeys(n for n in parts.get("notes", [])
                                  if not any(word in n.lower() for word in _ROUTINE_NOTES)))
    if warnings:
        sections.append({"title": "Warnings from the run", "lines": warnings})
    return sections


# ---------------------------------------------------------------------------
# 6. The report (the command line prints it, the web app shows it: the same text)
# ---------------------------------------------------------------------------

MARKS = {"failed": "fail", "weak": "weak", "explained": "explained", "passed": "pass", "skipped": "skip", "info": "info"}
# How each mark is shown, by the command line and the web app alike
REPORT_LEGEND = [
    {"mark": "fail", "symbol": "\u2717", "meaning": "counts towards the verdict"},
    {"mark": "explained", "symbol": "~", "meaning": "failed, but another feature explains it"},
    {"mark": "weak", "symbol": "!", "meaning": "loose end"},
    {"mark": "pass", "symbol": "\u2713", "meaning": "clean"},
    {"mark": "skip", "symbol": "-", "meaning": "couldn't run"},
    {"mark": "info", "symbol": "\u2022", "meaning": "information"},
]


def _items(checks: list[dict], statuses: tuple) -> list[dict]:
    return [{"mark": MARKS[c["status"]], "text": f"{c['label']}: {c['detail']}",
             "sub": [c["explanation"]] if c["explanation"] else []}
            for c in checks if c["status"] in statuses and not c.get("optional")]


# The benchmark's 9 original checks: always shown in the report, passed or not, in this order
ORIGINAL_BENCHMARK = ["TOTAL_WEALTH", "LIQUIDITY", "COMPOSITION_PROPERTY", "COMPOSITION_EQUITIES",
                      "COMPOSITION_BUSINESS", "COMPOSITION_CASH", "VELOCITY", "COUNTERPARTIES", "JURISDICTION"]


def _benchmark_items(checks: list[dict]) -> list[dict]:
    """The benchmark section: the 9 original checks every time (passed, failed, explained or not
    run, each with its numbers), then any of the newer checks that failed or need a look."""
    by_rule = {c["check"]: c for c in checks}
    items = []
    for rule in ORIGINAL_BENCHMARK:
        check = by_rule.get(rule)
        if check is None:
            items.append({"mark": "skip", "text": f"{BENCHMARK_LABELS[rule]}: couldn't run - the peer benchmark "
                                                  "didn't finish, so this wasn't compared with peers.", "sub": []})
            continue
        items.append({"mark": MARKS[check["status"]], "text": f"{check['label']}: {check['detail']}",
                      "sub": [check["explanation"]] if check["explanation"] else []})
    newer = [c for c in checks if c["check"] not in ORIGINAL_BENCHMARK and c["check"] != "PEER_BENCHMARK"]
    return items + _items(newer, ("failed", "explained", "weak", "skipped"))


def verdict_report(verdict: dict) -> dict:
    """The report as plain data: a header, short sections of marked lines, and the full evidence.
    io_manager prints it and the web app's template shows it, so both give exactly the same content.

    The benchmark section always lists its 9 original checks, passed or not. The other sections show
    only what matters: failures, what another feature explained, loose ends and what couldn't run;
    their passed checks are listed under "What came back clean"."""
    level_marks = {SERIOUS_RISK: "fail", RISKY: "fail", MANUAL_REVIEW: "weak", PASSED: "pass"}
    why = [{"mark": level_marks[r["level"]], "text": f"[{VERDICT_LABELS[r['level']]}] {r['text']}", "sub": []}
           for r in verdict["reasons"]] or [{"mark": "pass", "text": verdict["summary"], "sub": []}]
    why += [{"mark": "fail", "text": f"Checks agree - {a['title']} ({len(a['features'])} features: "
                                     f"{', '.join(a['features'])})",
             "sub": ["; ".join(dict.fromkeys(a.get("short", a["lines"])))]}
            for a in verdict["agreement"] if len(a["features"]) > 1]

    forecast = _items(verdict["forecast"], ("failed", "weak", "explained", "skipped"))
    forecast += [{"mark": "info", "text": f"{c['label']}: {c['detail']}", "sub": []} for c in verdict["forecast"]
                 if c["check"] == "PAY_FROM_DOCUMENTS"
                 or (c["check"] == "CRIME_STORY" and c["detail"].startswith("Fits"))]
    forecast += [{"mark": "pass", "text": f"{c['label']}: {c['detail']}", "sub": []} for c in verdict["forecast"]
                 if c["check"] == "STABILITY" and c["status"] == "passed"]
    crime = _items(verdict["crime"], ("failed", "weak", "skipped"))
    documents = _items(verdict["document_findings"], ("failed", "weak", "skipped", "info", "passed"))
    for item, check in zip(documents, [c for c in verdict["document_findings"]
                                       if c["status"] in ("failed", "weak", "skipped", "info", "passed")]):
        if check.get("sources"):
            item["sub"] = item["sub"] + [f"From: {', '.join(check['sources'])}"]

    sections = [
        {"title": "Why", "items": why},
        {"title": "Benchmark - compared with peers in the same economy",
         "items": _benchmark_items(verdict["benchmark"])},
        {"title": "Forecast - what it predicted",
         "items": forecast or [{"mark": "pass", "text": "Every forecast check passed.", "sub": []}]},
        {"title": "Crime - known patterns for his industry",
         "items": crime or [{"mark": "pass", "text": "No known pattern matched his declaration.", "sub": []}]},
        {"title": "Documents - what his papers show", "items": documents},
        {"title": "Documents to request", "items": [
            {"mark": "info", "text": f"{n}. {d['document']}", "sub": [d["reason"]]}
            for n, d in enumerate(verdict["documents"], 1)]
         or [{"mark": "pass", "text": "None.", "sub": []}]},
        {"title": "What came back clean", "items": [{"mark": "pass", "text": group, "sub": []}
                                                    for group in verdict["clean"]]
         or [{"mark": "info", "text": "Nothing came back fully clean.", "sub": []}]},
    ]
    if verdict["not_run"]:
        sections.append({"title": "Could not run", "items": [{"mark": "skip", "text": part, "sub": []}
                                                             for part in verdict["not_run"]]})
    return {
        "header": {"client_ref": verdict["client_ref"], "name": verdict["name"],
                   "assessed_on": verdict["assessed_on"], "verdict": verdict["verdict"],
                   "verdict_label": verdict["verdict_label"], "next_step": verdict["next_step"],
                   "next_review_date": verdict["next_review_date"], "summary": verdict["summary"],
                   "policy_version": verdict["policy_version"]},
        "sections": sections,
        "evidence": verdict["evidence"],
        "evidence_titles": [part["title"] for part in verdict["evidence"]],
        "legend": REPORT_LEGEND,
    }