"""CrimeScan: the crime scan feature and the warning signs it owns."""

import pytest

from app.logic.crime_scan import CrimeScan
from app.logic.risk_analysis import RiskAnalysis
from app.model.check import Check
from app.model.declaration import Declaration
from app.model.match_result import MatchResult
from app.model.research_report import ResearchReport
from app.model.typology import Typology
from tests import fake_ai
from tests.logic_fixtures import POLICY

CASE = {"client_ref": "SOW-1", "occupation": "COO", "industry": "Shipping", "age": 51,
        "career_start_year": 1998, "country": "Singapore", "country_of_residence": "Singapore"}
UNNAMED = {"sources": [{"source_id": "S1", "source_type": "advisory_fees", "counterparty": None,
                        "amount_sgd": None, "occupation_mismatch": False, "jurisdiction": "Hong Kong"}]}
NAMED = {"sources": [{"source_id": "S1", "source_type": "salary", "counterparty": "Straits Harbour Logistics",
                      "amount_sgd": 300000, "occupation_mismatch": False, "jurisdiction": "Singapore"}]}


def test_crime_scan_is_a_feature():
    assert isinstance(CrimeScan(POLICY), RiskAnalysis)
    assert CrimeScan.NAME == "crime"


def test_flags_names_the_warning_signs_that_fire():
    scan = CrimeScan(POLICY)
    assert scan.flags(Declaration(UNNAMED["sources"])) == ["counterparty_unnamed", "unvalued_source_present"]
    assert scan.flags(Declaration(NAMED["sources"])) == []


def test_a_typology_is_breached_when_all_its_core_signs_fire():
    result = CrimeScan(POLICY).run(CASE, {"typology_response": fake_ai.typologies(), "declaration": UNNAMED})
    match = result["match_results"][0]
    assert isinstance(match, MatchResult)                  # an object, not a dict
    assert match.breached is True
    assert match.core_fired == ["counterparty_unnamed"]
    assert match.typology.typology_id == fake_ai.typologies()["sector_typologies"][0]["typology_id"]
    assert result["breach_count"] == 1


def test_a_clean_declaration_breaches_nothing():
    result = CrimeScan(POLICY).run(CASE, {"typology_response": fake_ai.typologies(), "declaration": NAMED})
    assert result["breach_count"] == 0
    assert result["match_results"][0].category == "no_match"


def test_research_from_a_site_that_is_not_trusted_is_dropped():
    research = fake_ai.research()
    research["reports"].append({**research["reports"][0], "report_id": "R2", "url": "https://random-blog.example/ml"})
    research["api_sources"].append({"url": "https://random-blog.example/ml", "title": "Blog"})
    scan = CrimeScan(POLICY)
    reports = scan.verify_research(research)
    assert [report.report_id for report in reports] == ["R1"]
    assert all(isinstance(report, ResearchReport) for report in reports)
    assert scan.warnings()


def test_a_typology_whose_quote_is_not_in_its_report_is_dropped():
    scan = CrimeScan(POLICY)
    clean = scan.verify_research(fake_ai.research())
    typologies = fake_ai.typologies()["sector_typologies"]
    kept = scan.verify_typology_sources(typologies, clean)
    assert len(kept) == 1
    assert isinstance(kept[0], Typology) and kept[0].verified
    invented = [{**typologies[0], "source_quotes": [{"report_id": "R1", "quote": "A sentence the report never said."}]}]
    kept = scan.verify_typology_sources(invented, clean)
    assert kept == []
    assert any("dropped" in warning for warning in scan.warnings())


def test_an_empty_or_blank_quote_is_not_verified():
    scan = CrimeScan(POLICY)
    clean = scan.verify_research(fake_ai.research())
    typologies = fake_ai.typologies()["sector_typologies"]
    for blank in ("", "   "):
        empty = [{**typologies[0], "source_quotes": [{"report_id": "R1", "quote": blank}]}]
        assert scan.verify_typology_sources(empty, clean) == []
    assert any("dropped" in warning for warning in scan.warnings())


def test_without_research_the_typologies_are_read_unchecked():
    scan = CrimeScan(POLICY)
    reply = fake_ai.typologies()["sector_typologies"]
    read = scan.read_typologies(reply)
    assert all(isinstance(typology, Typology) and not typology.verified for typology in read)
    assert [typology.to_dict() for typology in read] == reply      # nothing lost, nothing added
    assert scan.warnings() == []


def test_a_typology_reply_given_whole_is_read_like_the_typology_objects():
    scan = CrimeScan(POLICY)
    whole = scan.run(CASE, {"typology_response": fake_ai.typologies(), "declaration": UNNAMED})
    objects = scan.run(CASE, {"typologies": scan.read_typologies(fake_ai.typologies()["sector_typologies"]),
                              "declaration": UNNAMED})
    assert {**whole, "match_results": [match.to_dict() for match in whole["match_results"]]} == \
        {**objects, "match_results": [match.to_dict() for match in objects["match_results"]]}


def test_every_match_holds_the_very_typology_it_matched():
    scan = CrimeScan(POLICY)
    typologies = scan.verify_typology_sources(fake_ai.typologies()["sector_typologies"],
                                              scan.verify_research(fake_ai.research()))
    result = scan.run(CASE, {"typologies": typologies, "declaration": UNNAMED})
    assert [match.typology for match in result["match_results"]] == typologies
    assert result["match_results"][0].typology is typologies[0]


def test_the_saved_match_layout_keeps_every_field_in_order():
    result = CrimeScan(POLICY).run(CASE, {"typology_response": fake_ai.typologies(), "declaration": UNNAMED})
    reply = fake_ai.typologies()["sector_typologies"][0]
    assert list(result) == ["breach_count", "match_count", "match_results"]
    assert result["match_results"][0].to_dict() == {
        "typology_id": reply["typology_id"], "name": reply["name"], "source_ids": ["R1"], "breached": True,
        "category": "high", "core_indicators": ["counterparty_unnamed"], "core_fired": ["counterparty_unnamed"],
        "supporting_indicators": ["unvalued_source_present"], "supporting_fired": ["unvalued_source_present"],
        "typical_documents": ["Freight invoices", "Bills of lading"]}
    assert list(result["match_results"][0].to_dict()) == [
        "typology_id", "name", "source_ids", "breached", "category", "core_indicators", "core_fired",
        "supporting_indicators", "supporting_fired", "typical_documents"]


def test_checks_are_check_objects_that_keep_the_signs_that_fired():
    scan = CrimeScan(POLICY)
    clean = scan.verify_research(fake_ai.research())
    typologies = scan.verify_typology_sources(fake_ai.typologies()["sector_typologies"], clean)
    result = scan.run(CASE, {"typologies": typologies, "declaration": UNNAMED})
    checks = scan.checks({"crime_result": result, "reports": clean, "typologies": typologies, "types": []})
    assert all(isinstance(check, Check) and check.feature == "crime" for check in checks)
    typology = next(check for check in checks if check.check == "TYPOLOGY")
    assert typology.extra("signs") == ["counterparty_unnamed", "unvalued_source_present"]
    assert typology.extra("match") == result["match_results"][0].category
    assert typology.extra("typology_id") == typologies[0].typology_id
    assert typology.explanation.endswith(f'"{typologies[0].source_quotes[0]["quote"]}" [R1]')
    assert (typology.group, typology.theme) == ("Patterns", "pattern")
    saved = typology.to_dict()                      # the saved layout keeps them after the shared fields
    assert list(saved)[-3:] == ["signs", "match", "typology_id"]


def test_a_crime_scan_that_could_not_run_gives_one_skipped_check():
    checks = CrimeScan(POLICY).checks({"crime_result": None})
    assert [check.status for check in checks] == ["skipped"]


def test_a_person_type_without_research_is_an_information_check():
    scan = CrimeScan(POLICY)
    types = [{"type_id": "T3", "name": "Cash courier", "typology_id": None, "fits": False}]
    checks = scan.checks({"crime_result": {"match_results": []}, "reports": [], "types": types})
    assert [(check.check, check.status, check.label) for check in checks] == [
        ("UNBACKED_TYPE", "info", "T3 Cash courier"), ("NO_PATTERNS", "info", "Known patterns")]
    assert all(isinstance(check, Check) and check.extra("signs") is None for check in checks)


# ----- the declaration the forecast read, as the crime scan reads it --------------------------

READING = Declaration.from_dict({"claimed_sources": [
    {"source_id": "S1", "source_type": "employment", "description": "Salary as COO", "start_year": 1998,
     "end_year": None, "amount": None, "country": "Singapore", "linked_position_index": 2,
     "linked_asset_index": None, "quote": "salary", "counterparty": "Straits Harbour Logistics",
     "occupation_mismatch": False},
    {"source_id": "S2", "source_type": "inheritance_gift", "description": "Inherited from his late father",
     "start_year": 2015, "end_year": 2015, "amount": 500000, "country": "sg", "linked_position_index": None,
     "linked_asset_index": None, "quote": "inherited", "counterparty": None, "occupation_mismatch": True},
    {"source_id": "S3", "source_type": "inheritance_gift", "description": "From his uncle", "start_year": None,
     "end_year": None, "amount": None, "country": "Mordor", "linked_position_index": None,
     "linked_asset_index": 0, "quote": "a gift", "counterparty": "Uncle", "occupation_mismatch": False},
]})


def test_crime_declaration_gives_a_new_declaration_in_the_saved_row_layout():
    rows, warnings = CrimeScan(POLICY).crime_declaration(READING)
    assert isinstance(rows, Declaration) and warnings == []
    assert rows.to_scan_dict() == {"sources": [
        {"source_id": "S1", "source_type": "employment", "description": "Salary as COO", "amount_sgd": None,
         "start_year": 1998, "end_year": None, "jurisdiction": "Singapore",
         "counterparty": "Straits Harbour Logistics", "evidence_sentence": "salary", "occupation_mismatch": False,
         "amount_explained_by_forecast": True},
        {"source_id": "S2", "source_type": "inheritance", "description": "Inherited from his late father",
         "amount_sgd": 500000, "start_year": 2015, "end_year": 2015, "jurisdiction": "sg", "counterparty": None,
         "evidence_sentence": "inherited", "occupation_mismatch": True, "amount_explained_by_forecast": False},
        {"source_id": "S3", "source_type": "gift", "description": "From his uncle", "amount_sgd": None,
         "start_year": None, "end_year": None, "jurisdiction": "Mordor", "counterparty": "Uncle",
         "evidence_sentence": "a gift", "occupation_mismatch": False, "amount_explained_by_forecast": False}]}
    assert READING.sources()[1].source_type == "inheritance_gift"      # the forecast's reading is unchanged


def test_crime_declaration_of_no_reading_is_none():
    assert CrimeScan(POLICY).crime_declaration(None) == (None, [])


def test_the_crime_scans_signs_read_the_reshaped_sources():
    rows, _ = CrimeScan(POLICY).crime_declaration(READING)
    flags = CrimeScan(POLICY).flags(rows)
    assert "gift_or_inheritance_unnamed" in flags           # S2 became an unnamed inheritance
    assert "source_contradicts_occupation" in flags
    assert "unvalued_source_present" in flags                 # S3 has no amount and no job behind it


def test_normalise_jurisdictions_gives_a_new_declaration_and_leaves_the_old_one():
    rows, _ = CrimeScan(POLICY).crime_declaration(READING)
    cleaned, warnings = CrimeScan(POLICY).normalise_jurisdictions(rows)
    assert [source.country for source in cleaned.sources()] == ["SG", "SG", None]
    assert [source.country for source in rows.sources()] == ["Singapore", "sg", "Mordor"]
    assert len(warnings) == 3
    kept = cleaned.to_scan_dict()["sources"][1]
    assert kept == {**rows.to_scan_dict()["sources"][1], "jurisdiction": "SG"}


def test_normalise_jurisdictions_keeps_a_valid_code_and_a_missing_one_without_warnings():
    rows = Declaration([{**UNNAMED["sources"][0], "source_id": "S1", "jurisdiction": "SG"},
                        {**UNNAMED["sources"][0], "source_id": "S2", "jurisdiction": None}])
    cleaned, warnings = CrimeScan(POLICY).normalise_jurisdictions(rows)
    assert [source.country for source in cleaned.sources()] == ["SG", None]
    assert warnings == []


def test_run_takes_the_declaration_object_or_its_saved_rows():
    typologies = CrimeScan(POLICY).read_typologies(fake_ai.typologies()["sector_typologies"])
    as_object = CrimeScan(POLICY).run(CASE, {"typologies": typologies, "declaration": Declaration(UNNAMED["sources"])})
    as_rows = CrimeScan(POLICY).run(CASE, {"typologies": typologies, "declaration": UNNAMED})
    assert [m.to_dict() for m in as_object["match_results"]] == [m.to_dict() for m in as_rows["match_results"]]
    assert as_object["breach_count"] == 1


def test_the_crime_scan_rejects_a_policy_that_is_not_a_dict():
    with pytest.raises(ValueError, match="policy must be a dict"):
        CrimeScan(["policy"])


# ===========================================================================
# match_typologies: the warning signs and how they add up to a match
# ===========================================================================

def match_typologies(typologies, declaration, clean_case, policy):
    """The crime scan's matching, as these tests have always called it: the typology dicts become
    Typology objects and the declaration a Declaration, as the crime scan hands them over."""
    return CrimeScan(policy).match_typologies(Declaration(declaration["sources"]),
                                              [Typology.from_dict(typology) for typology in typologies])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decl(*sources):
    return {"sources": list(sources)}


def _src(source_type="employment", counterparty=None, amount_sgd=0, occupation_mismatch=False):
    return {
        "source_type": source_type,
        "description": "test",
        "amount_sgd": amount_sgd,
        "start_year": 2000,
        "end_year": None,
        "jurisdiction": "SG",
        "counterparty": counterparty,
        "evidence_sentence": "test.",
        "occupation_mismatch": occupation_mismatch,
    }


def _clean_case():
    return {}


def _policy(limit=1):
    return {
        "thresholds": {"unknown_counterparty_limit": limit},
        "typology_full_match_counts_as_breach": True,
    }


def _typology(typ_id, indicators):
    return {
        "typology_id": typ_id,
        "name": typ_id,
        "description": "test",
        "source_ids": [],
        "source_quotes": [],
        "indicators": indicators,
        "typical_documents": ["test doc"],
    }


# ---------------------------------------------------------------------------
# Each warning sign, on its own: does it fire for this declared source?
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("indicator, source, limit, fires", [
    ("gift_or_inheritance_unnamed", _src(source_type="inheritance", counterparty=None), 1, True),
    ("gift_or_inheritance_unnamed", _src(source_type="gift", counterparty=None), 1, True),
    ("gift_or_inheritance_unnamed", _src(source_type="inheritance", counterparty="Estate of John Doe"), 1, False),
    ("gift_or_inheritance_unnamed", _src(source_type="employment", counterparty=None), 1, False),
    ("counterparty_unnamed", _src(counterparty=None), 1, True),
    ("counterparty_unnamed", _src(counterparty="Maersk"), 1, False),
    ("source_contradicts_occupation", _src(occupation_mismatch=True), 1, True),
    ("source_contradicts_occupation", _src(occupation_mismatch=False), 1, False),
    ("unvalued_source_present", _src(amount_sgd=None), 1, True),
    ("unvalued_source_present", _src(amount_sgd=100000), 1, False),
    ("related_party_transaction", _src(counterparty="a friend"), 1, True),
    ("related_party_transaction", _src(counterparty="Maersk Line"), 1, False),
], ids=["unnamed inheritance", "unnamed gift", "named inheritance", "employment is not a gift",
        "unnamed counterparty at the limit", "named counterparty", "occupation mismatch", "no occupation mismatch",
        "no amount", "amount given", "a friend is a related party", "a named company is not"])
def test_each_warning_sign_fires_only_when_it_should(indicator, source, limit, fires):
    results = match_typologies([_typology("t1", [{"indicator": indicator, "weight": "core"}])],
                               _decl(source), _clean_case(), _policy(limit=limit))
    assert results[0].breached is fires


# ---------------------------------------------------------------------------
# match_typologies — structural tests
# ---------------------------------------------------------------------------

def test_empty_typologies_returns_empty():
    results = match_typologies([], _decl(), _clean_case(), _policy())
    assert results == []


def test_all_core_fire_gives_breach():
    decl = _decl(_src(source_type="gift", counterparty=None, occupation_mismatch=True))
    typ = _typology("t1", [
        {"indicator": "gift_or_inheritance_unnamed", "weight": "core"},
        {"indicator": "source_contradicts_occupation", "weight": "core"},
    ])
    results = match_typologies([typ], decl, _clean_case(), _policy())
    assert results[0].breached is True
    assert set(results[0].core_fired) == {"gift_or_inheritance_unnamed", "source_contradicts_occupation"}


def test_partial_core_fire_no_breach():
    # gift fires, source_contradicts_occupation doesn't
    decl = _decl(_src(source_type="gift", counterparty=None, occupation_mismatch=False))
    typ = _typology("t1", [
        {"indicator": "gift_or_inheritance_unnamed", "weight": "core"},
        {"indicator": "source_contradicts_occupation", "weight": "core"},
    ])
    results = match_typologies([typ], decl, _clean_case(), _policy())
    assert results[0].breached is False


def test_supporting_indicators_do_not_affect_breach():
    # Core fires, supporting doesn't — still BREACH
    decl = _decl(_src(source_type="gift", counterparty=None))
    typ = _typology("t1", [
        {"indicator": "gift_or_inheritance_unnamed", "weight": "core"},
        {"indicator": "counterparty_unnamed", "weight": "supporting"},
    ])
    results = match_typologies([typ], decl, _clean_case(), _policy(limit=99))
    assert results[0].breached is True
    assert results[0].supporting_fired == []


def test_multiple_typologies_mixed_results():
    decl = _decl(_src(source_type="gift", counterparty=None, amount_sgd=None))
    typ1 = _typology("t1", [{"indicator": "gift_or_inheritance_unnamed", "weight": "core"}])
    typ2 = _typology("t2", [{"indicator": "counterparty_unnamed", "weight": "core"}])
    results = match_typologies([typ1, typ2], decl, _clean_case(), _policy())
    # gift with no counterparty → both fire
    assert results[0].breached is True
    assert results[1].breached is True


def test_each_result_is_a_match_result_holding_its_typology():
    decl = _decl(_src(source_type="gift", counterparty=None, amount_sgd=None))
    typ = _typology("t1", [{"indicator": "gift_or_inheritance_unnamed", "weight": "core"},
                           {"indicator": "unvalued_source_present", "weight": "supporting"},
                           {"indicator": "related_party_transaction", "weight": "supporting"}])
    result = match_typologies([typ], decl, _clean_case(), _policy())[0]
    assert isinstance(result, MatchResult)
    assert isinstance(result.typology, Typology) and result.typology.typology_id == "t1"
    assert result.typology.to_dict() == {**typ, "crime_category": ""}       # the whole typology, not just its id
    assert (result.category, result.core_fired, result.supporting_fired) == (
        "high", ["gift_or_inheritance_unnamed"], ["unvalued_source_present"])
    assert result.to_dict() == {
        "typology_id": "t1", "name": "t1", "source_ids": [], "breached": True, "category": "high",
        "core_indicators": ["gift_or_inheritance_unnamed"], "core_fired": ["gift_or_inheritance_unnamed"],
        "supporting_indicators": ["unvalued_source_present", "related_party_transaction"],
        "supporting_fired": ["unvalued_source_present"], "typical_documents": ["test doc"]}


# ===========================================================================
# verify_research: the trusted research reports
# ===========================================================================

def verify_research(research, policy):
    """(the kept ResearchReports, the warnings), as these tests have always used it."""
    scan = CrimeScan(policy)
    reports = scan.verify_research(research)
    return reports, scan.warnings()


def _research_policy(trusted=None):
    return {
        "trusted_sources": trusted or ["fatf-gafi.org", "mas.gov.sg"],
    }


def _research_report(report_id, url, org="FATF", year=2020):
    return {
        "report_id": report_id,
        "url": url,
        "organisation": org,
        "year": year,
        "title": "Test Report",
        "summary": "Summary",
        "excerpts": ["Excerpt one.", "Excerpt two."],
    }


def _sample_research(reports, api_sources=None):
    if api_sources is None:
        api_sources = [{"url": r["url"]} for r in reports]
    return {
        "reports": reports,
        "api_sources": api_sources,
        "retrieved_at": "2025-01-01T00:00:00Z",
        "model": "test-model",
    }


# ---------------------------------------------------------------------------
# Test 1: URL not in api_sources → removed + warning
# ---------------------------------------------------------------------------

def test_url_not_in_api_sources_removed():
    report = _research_report("R1", "https://fatf-gafi.org/report.pdf")
    research = _sample_research([report], api_sources=[])  # empty api_sources
    policy = _research_policy()

    reports, warnings = verify_research(research, policy)

    assert reports == []
    assert any("R1" in w and "web search" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 2: Domain not trusted → removed + warning
# ---------------------------------------------------------------------------

def test_untrusted_domain_removed():
    report = _research_report("R1", "https://untrusted-site.com/report.pdf")
    research = _sample_research([report])
    policy = _research_policy()

    reports, warnings = verify_research(research, policy)

    assert reports == []
    assert any("R1" in w and "trusted" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 3: Duplicate URL → second removed
# ---------------------------------------------------------------------------

def test_duplicate_url_second_removed():
    url = "https://fatf-gafi.org/report.pdf"
    r1 = _research_report("R1", url)
    r2 = _research_report("R2", url)
    research = _sample_research([r1, r2], api_sources=[{"url": url}])
    policy = _research_policy()

    reports, warnings = verify_research(research, policy)

    assert len(reports) == 1
    assert any("R2" in w and "duplicate" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 4: Original IDs are preserved after filtering (gaps are fine)
# ---------------------------------------------------------------------------

def test_original_ids_preserved_after_filtering():
    r1 = _research_report("R1", "https://fatf-gafi.org/r1.pdf")
    r2 = _research_report("R2", "https://untrusted.com/r2.pdf")  # will be removed (untrusted)
    r3 = _research_report("R3", "https://mas.gov.sg/r3.pdf")
    research = _sample_research(
        [r1, r2, r3],
        api_sources=[
            {"url": "https://fatf-gafi.org/r1.pdf"},
            {"url": "https://untrusted.com/r2.pdf"},
            {"url": "https://mas.gov.sg/r3.pdf"},
        ],
    )
    policy = _research_policy()

    reports, warnings = verify_research(research, policy)

    ids = [r.report_id for r in reports]
    # R2 removed (untrusted), R1 and R3 survive with their original IDs (gap is intentional)
    assert ids == ["R1", "R3"]


# ---------------------------------------------------------------------------
# Test 5: All valid → nothing removed, no warnings
# ---------------------------------------------------------------------------

def test_all_valid_nothing_removed():
    r1 = _research_report("R1", "https://fatf-gafi.org/r1.pdf")
    r2 = _research_report("R2", "https://mas.gov.sg/r2.pdf")
    research = _sample_research([r1, r2])
    policy = _research_policy()

    reports, warnings = verify_research(research, policy)

    assert len(reports) == 2
    assert warnings == []


# ---------------------------------------------------------------------------
# Test 6: Empty reports → empty result, no warnings
# ---------------------------------------------------------------------------

def test_empty_reports():
    research = _sample_research([], api_sources=[])
    policy = _research_policy()

    reports, warnings = verify_research(research, policy)

    assert reports == []
    assert warnings == []


# ---------------------------------------------------------------------------
# Test 7: Subdomain www.fatf-gafi.org matches trusted fatf-gafi.org
# ---------------------------------------------------------------------------

def test_subdomain_matches_trusted():
    report = _research_report("R1", "https://www.fatf-gafi.org/report.pdf")
    research = _sample_research([report])
    policy = _research_policy()

    reports, warnings = verify_research(research, policy)

    assert len(reports) == 1
    assert warnings == []


# ---------------------------------------------------------------------------
# Test 8: The kept reports are ResearchReport objects with every field
# ---------------------------------------------------------------------------

def test_kept_reports_are_research_report_objects():
    report = _research_report("R1", "https://www.fatf-gafi.org/report.pdf")
    reports, _ = verify_research(_sample_research([report]), _research_policy())
    assert all(isinstance(kept, ResearchReport) for kept in reports)
    kept = reports[0]
    assert (kept.report_id, kept.url, kept.organisation, kept.year, kept.title) == (
        "R1", "https://www.fatf-gafi.org/report.pdf", "FATF", 2020, "Test Report")
    assert kept.excerpts == ["Excerpt one.", "Excerpt two."]
    assert kept.retrieved_at == "2025-01-01T00:00:00Z"        # the age check measures from it


# ---------------------------------------------------------------------------
# Test 9: A report that cannot be read is removed with a warning, not a crash
# ---------------------------------------------------------------------------

def test_unreadable_report_removed_not_crashed():
    good = _research_report("R1", "https://fatf-gafi.org/r1.pdf")
    broken = {**_research_report("R2", "https://mas.gov.sg/r2.pdf"), "excerpts": "one long excerpt"}
    research = _sample_research([good, broken, "not a report"], api_sources=[{"url": good["url"]}, {"url": broken["url"]}])
    reports, warnings = verify_research(research, _research_policy())
    assert [r.report_id for r in reports] == ["R1"]
    assert any("R2" in w and "could not be read" in w for w in warnings)
    assert any("?" in w and "could not be read" in w for w in warnings)
    assert "Removed R2: the report could not be read." in warnings     # plain words, no raw error text


# ---------------------------------------------------------------------------
# Test 10: warnings() only describes the last call
# ---------------------------------------------------------------------------

def test_warnings_are_those_of_the_last_call():
    scan = CrimeScan(_research_policy())
    scan.verify_research(_sample_research([_research_report("R1", "https://untrusted.com/x")]))
    assert scan.warnings()
    scan.verify_research(_sample_research([]))
    assert scan.warnings() == []


# ===========================================================================
# verify_typology_sources
# Tests for CrimeScan.verify_typology_sources.
#
# verify_typology_sources returns the verified Typology objects; CrimeScan.warnings() then
# holds what was removed:
#   - the typologies: bad source_ids/quotes removed;
#     typologies with zero verified quotes are dropped entirely.
#     Each kept typology is verified and carries corroborated (bool) and
#     outdated_source_ids (list[str]).
#   - warnings: ONLY for removals / invalid data:
#       - source_id not found in research
#       - quote report_id not found
#       - quote not found verbatim in excerpts
#       - typology dropped (no verified quotes remain)
#       - source has no valid year
#     Corroboration status and outdated age are NOT warnings — they are
#     stored on the returned typology for display.
# ===========================================================================

def verify_typology_sources(typologies, clean_research, policy):
    """The research dict's reports become ResearchReports, as verify_research hands them over."""
    reports = [ResearchReport.from_dict(report, clean_research["retrieved_at"]) for report in clean_research["reports"]]
    scan = CrimeScan(policy)
    kept = scan.verify_typology_sources(typologies, reports)
    return kept, scan.warnings()


def _sources_policy(max_age=10):
    return {"source_max_age_years": max_age}


def _sources_report(report_id, org="FATF", year=2020, excerpts=None):
    return {
        "report_id": report_id,
        "organisation": org,
        "year": year,
        "excerpts": excerpts or ["Known excerpt text.", "Another excerpt."],
    }


def _sample_clean_research(reports, retrieved_at="2026-01-01T00:00:00Z"):
    return {
        "reports": reports,
        "api_sources": [],
        "retrieved_at": retrieved_at,
        "model": "test-model",
    }


def _sample_typology(typology_id, source_ids, source_quotes):
    return {
        "typology_id": typology_id,
        "name": "Test Typology",
        "crime_category": "TRADE_BASED_ML",
        "description": "Sentence one. Sentence two.",
        "source_ids": source_ids,
        "source_quotes": source_quotes,
        "indicators": [{"indicator": "source_contradicts_occupation", "weight": "core"}],
        "typical_documents": ["Bank statements"],
    }


# ---------------------------------------------------------------------------
# Test 1: Valid source_id → retained in cleaned typology
# ---------------------------------------------------------------------------

def test_valid_source_id_retained():
    report = _sources_report("R1")
    clean = _sample_clean_research([report])
    typ = _sample_typology("T1", ["R1"], [{"report_id": "R1", "quote": "Known excerpt text."}])

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy())

    assert len(cleaned) == 1
    assert "R1" in cleaned[0].cited_report_ids()
    assert not any("not found in research" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 2: Invalid source_id → removed from cleaned typology + warning
# ---------------------------------------------------------------------------

def test_invalid_source_id_removed():
    report = _sources_report("R1")
    clean = _sample_clean_research([report])
    # R99 doesn't exist; R1 does and has a valid quote
    typ = _sample_typology(
        "T1",
        ["R1", "R99"],
        [{"report_id": "R1", "quote": "Known excerpt text."}],
    )

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy())

    assert len(cleaned) == 1
    assert "R99" not in cleaned[0].cited_report_ids()
    assert "R1" in cleaned[0].cited_report_ids()
    assert any("R99" in w and "not found in research" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 3: Valid quote (substring of excerpt) → retained in cleaned typology
# ---------------------------------------------------------------------------

def test_valid_quote_retained():
    report = _sources_report("R1", excerpts=["The full excerpt with important text."])
    clean = _sample_clean_research([report])
    typ = _sample_typology("T1", ["R1"], [{"report_id": "R1", "quote": "important text"}])

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy())

    assert len(cleaned) == 1
    assert cleaned[0].source_quotes[0]["quote"] == "important text"
    assert not any("not found verbatim" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 4: Invalid quote → removed from cleaned output + warning
# ---------------------------------------------------------------------------

def test_invalid_quote_removed_from_output():
    report = _sources_report("R1", excerpts=["Valid excerpt text."])
    clean = _sample_clean_research([report])
    # Two quotes: one valid, one invalid
    typ = _sample_typology("T1", ["R1"], [
        {"report_id": "R1", "quote": "Valid excerpt text."},
        {"report_id": "R1", "quote": "This quote does not exist in excerpts"},
    ])

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy())

    assert len(cleaned) == 1
    quotes = [q["quote"] for q in cleaned[0].source_quotes]
    assert "Valid excerpt text." in quotes
    assert "This quote does not exist in excerpts" not in quotes
    assert any("not found verbatim" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 5: Typology with no valid quotes → dropped entirely + warning
# ---------------------------------------------------------------------------

def test_no_valid_quotes_drops_typology():
    report = _sources_report("R1", excerpts=["Real excerpt."])
    clean = _sample_clean_research([report])
    typ = _sample_typology(
        "T1", ["R1"], [{"report_id": "R1", "quote": "Quote not present in excerpts"}]
    )

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy())

    assert cleaned == []
    assert any("dropped" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 6: Corroborated — 2 reports from different orgs → corroborated=True
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("second_org, corroborated", [("MAS", True), ("FATF", False)],
                         ids=["different orgs", "same org"])
def test_a_quote_is_corroborated_only_by_a_different_org(second_org, corroborated):
    r1 = _sources_report("R1", org="FATF", excerpts=["shared quote"])
    r2 = _sources_report("R2", org=second_org, excerpts=["shared quote"])
    clean = _sample_clean_research([r1, r2])
    typ = _sample_typology(
        "T1",
        ["R1", "R2"],
        [
            {"report_id": "R1", "quote": "shared quote"},
            {"report_id": "R2", "quote": "shared quote"},
        ],
    )

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy())

    assert len(cleaned) == 1
    assert cleaned[0].corroborated is corroborated
    assert not any("corroborat" in w for w in warnings)  # either way, not a warning


# ---------------------------------------------------------------------------
# Test 7: Not corroborated — 2 reports from same org → corroborated=False
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Test 8: Org splitting — "FATF and Egmont Group" vs "FATF" → same;
#          "FATF and Egmont Group" vs "MAS" → corroborated
# ---------------------------------------------------------------------------

def test_org_splitting():
    r1 = _sources_report("R1", org="FATF and Egmont Group", excerpts=["quote"])
    r2_same = _sources_report("R2", org="FATF", excerpts=["quote"])
    r3_diff = _sources_report("R3", org="MAS", excerpts=["quote"])

    # R1 + R2 share "fatf" → not corroborated
    clean_same = _sample_clean_research([r1, r2_same])
    typ_same = _sample_typology(
        "T1",
        ["R1", "R2"],
        [{"report_id": "R1", "quote": "quote"}, {"report_id": "R2", "quote": "quote"}],
    )
    cleaned_same, _ = verify_typology_sources([typ_same], clean_same, _sources_policy())
    assert cleaned_same[0].corroborated is False

    # R1 + R3: "fatf"/"egmont group" vs "mas" → disjoint → corroborated
    clean_diff = _sample_clean_research([r1, r3_diff])
    typ_diff = _sample_typology(
        "T2",
        ["R1", "R3"],
        [{"report_id": "R1", "quote": "quote"}, {"report_id": "R3", "quote": "quote"}],
    )
    cleaned_diff, _ = verify_typology_sources([typ_diff], clean_diff, _sources_policy())
    assert cleaned_diff[0].corroborated is True


# ---------------------------------------------------------------------------
# Test 9: Outdated — year 2006, retrieved_at 2026 → in outdated_source_ids,
#          NOT a warning
# ---------------------------------------------------------------------------

def test_outdated_source_tracked_not_warned():
    report = _sources_report("R1", year=2006, excerpts=["quote"])
    clean = _sample_clean_research([report], retrieved_at="2026-01-01T00:00:00Z")
    typ = _sample_typology("T1", ["R1"], [{"report_id": "R1", "quote": "quote"}])

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy(max_age=10))

    assert len(cleaned) == 1
    assert "R1" in cleaned[0].outdated_source_ids
    assert not any("years old" in w for w in warnings)  # outdated is not a warning


# ---------------------------------------------------------------------------
# Test 10: Not outdated — year 2020, retrieved_at 2026 → outdated_source_ids=[]
# ---------------------------------------------------------------------------

def test_not_outdated():
    report = _sources_report("R1", year=2020, excerpts=["quote"])
    clean = _sample_clean_research([report], retrieved_at="2026-01-01T00:00:00Z")
    typ = _sample_typology("T1", ["R1"], [{"report_id": "R1", "quote": "quote"}])

    cleaned, _ = verify_typology_sources([typ], clean, _sources_policy(max_age=10))

    assert len(cleaned) == 1
    assert cleaned[0].outdated_source_ids == []


# ---------------------------------------------------------------------------
# Test 11: Normalisation — excerpt has curly quotes, quote uses straight → match
# ---------------------------------------------------------------------------

def test_normalisation_curly_quotes_match():
    report = _sources_report(
        "R1", excerpts=["\u201cImportant finding\u201d noted here."]
    )
    clean = _sample_clean_research([report])
    typ = _sample_typology(
        "T1", ["R1"], [{"report_id": "R1", "quote": '"Important finding" noted here.'}]
    )

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy())

    assert len(cleaned) == 1
    assert not any("not found verbatim" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 12: Unknown age — year=0 → outdated_source_ids=[], "no valid year" warning
# ---------------------------------------------------------------------------

def test_unknown_age_not_counted_as_outdated():
    report = _sources_report("R1", year=0, excerpts=["quote"])
    clean = _sample_clean_research([report], retrieved_at="2026-01-01T00:00:00Z")
    typ = _sample_typology("T1", ["R1"], [{"report_id": "R1", "quote": "quote"}])

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy(max_age=10))

    assert len(cleaned) == 1
    assert cleaned[0].outdated_source_ids == []
    assert any("no valid year" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 13: Missing year (None) → also treated as unknown age
# ---------------------------------------------------------------------------

def test_missing_year_treated_as_unknown():
    report = {"report_id": "R1", "organisation": "FATF", "excerpts": ["quote"]}  # no "year"
    clean = _sample_clean_research([report], retrieved_at="2026-01-01T00:00:00Z")
    typ = _sample_typology("T1", ["R1"], [{"report_id": "R1", "quote": "quote"}])

    cleaned, warnings = verify_typology_sources([typ], clean, _sources_policy(max_age=10))

    assert len(cleaned) == 1
    assert cleaned[0].outdated_source_ids == []
    assert any("no valid year" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 14: The kept typologies are verified Typology objects, every field kept
# ---------------------------------------------------------------------------

def test_kept_typologies_are_verified_typology_objects():
    report = _sources_report("R1", year=2006, excerpts=["quote"])
    clean = _sample_clean_research([report], retrieved_at="2026-01-01T00:00:00Z")
    typ = _sample_typology("T1", ["R1", "R9"], [{"report_id": "R1", "quote": "quote"}])

    cleaned, _ = verify_typology_sources([typ], clean, _sources_policy(max_age=10))

    assert isinstance(cleaned[0], Typology) and cleaned[0].verified
    saved = cleaned[0].to_dict()
    # the layout the code always had: the reply's fields, then the two the check adds
    assert list(saved) == ["typology_id", "name", "crime_category", "description", "source_ids",
                           "source_quotes", "indicators", "typical_documents", "corroborated",
                           "outdated_source_ids"]
    assert saved == {**typ, "source_ids": ["R1"], "corroborated": False, "outdated_source_ids": ["R1"]}


# ---------------------------------------------------------------------------
# Test 15: A typology that cannot be read is dropped with a warning, not a crash
# ---------------------------------------------------------------------------

def test_unreadable_typology_dropped_not_crashed():
    clean = _sample_clean_research([_sources_report("R1", excerpts=["quote"])])
    good = _sample_typology("T1", ["R1"], [{"report_id": "R1", "quote": "quote"}])
    broken = {**good, "typology_id": "T2", "indicators": [{"indicator": "x", "weight": "optional"}]}

    cleaned, warnings = verify_typology_sources([good, broken, "T3"], clean, _sources_policy())

    assert [t.typology_id for t in cleaned] == ["T1"]
    assert any("'T2'" in w and "could not be read" in w for w in warnings)
    assert any("'unknown'" in w and "could not be read" in w for w in warnings)
    assert "Typology 'T2': dropped — it could not be read." in warnings   # plain words, no raw error text
