"""CrimeScan: the crime scan feature and the warning signs it owns."""

from app.logic.crime_scan import CrimeScan
from app.logic.risk_analysis import RiskAnalysis
from app.model.check import Check
from app.model.declaration import Declaration
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
    assert match["breached"] is True
    assert match["core_fired"] == ["counterparty_unnamed"]
    assert result["breach_count"] == 1


def test_a_clean_declaration_breaches_nothing():
    result = CrimeScan(POLICY).run(CASE, {"typology_response": fake_ai.typologies(), "declaration": NAMED})
    assert result["breach_count"] == 0
    assert result["match_results"][0]["category"] == "no_match"


def test_research_from_a_site_that_is_not_trusted_is_dropped():
    research = fake_ai.research()
    research["reports"].append({**research["reports"][0], "report_id": "R2", "url": "https://random-blog.example/ml"})
    research["api_sources"].append({"url": "https://random-blog.example/ml", "title": "Blog"})
    clean, warnings = CrimeScan(POLICY).verify_research(research)
    assert [report["report_id"] for report in clean["reports"]] == ["R1"]
    assert warnings


def test_a_typology_whose_quote_is_not_in_its_report_is_dropped():
    scan = CrimeScan(POLICY)
    clean, _ = scan.verify_research(fake_ai.research())
    typologies = fake_ai.typologies()["sector_typologies"]
    kept, _ = scan.verify_typology_sources(typologies, clean)
    assert len(kept) == 1
    invented = [{**typologies[0], "source_quotes": [{"report_id": "R1", "quote": "A sentence the report never said."}]}]
    kept, warnings = scan.verify_typology_sources(invented, clean)
    assert kept == []
    assert any("dropped" in warning for warning in warnings)


def test_checks_are_check_objects_that_keep_the_signs_that_fired():
    scan = CrimeScan(POLICY)
    clean, _ = scan.verify_research(fake_ai.research())
    typologies, _ = scan.verify_typology_sources(fake_ai.typologies()["sector_typologies"], clean)
    result = scan.run(CASE, {"typology_response": {"sector_typologies": typologies}, "declaration": UNNAMED})
    checks = scan.checks({"crime_result": result, "research": clean, "typologies": typologies, "types": []})
    assert all(isinstance(check, Check) and check.feature == "crime" for check in checks)
    typology = next(check for check in checks if check.check == "TYPOLOGY")
    assert typology.extra("signs") == ["counterparty_unnamed", "unvalued_source_present"]
    assert typology.extra("match") == result["match_results"][0]["category"]
    assert typology.extra("typology_id") == typologies[0]["typology_id"]
    assert (typology.group, typology.theme) == ("Patterns", "pattern")
    saved = typology.to_dict()                      # the saved layout keeps them after the shared fields
    assert list(saved)[-3:] == ["signs", "match", "typology_id"]


def test_a_crime_scan_that_could_not_run_gives_one_skipped_check():
    checks = CrimeScan(POLICY).checks({"crime_result": None})
    assert [check.status for check in checks] == ["skipped"]


def test_a_person_type_without_research_is_an_information_check():
    scan = CrimeScan(POLICY)
    types = [{"type_id": "T3", "name": "Cash courier", "typology_id": None, "fits": False}]
    checks = scan.checks({"crime_result": {"match_results": []}, "research": {"reports": []}, "types": types})
    assert [(check.check, check.status, check.label) for check in checks] == [
        ("UNBACKED_TYPE", "info", "T3 Cash courier"), ("NO_PATTERNS", "info", "Known patterns")]
    assert all(isinstance(check, Check) and check.extra("signs") is None for check in checks)
