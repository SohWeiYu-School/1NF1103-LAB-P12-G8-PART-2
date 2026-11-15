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


def test_run_takes_the_declaration_object_or_its_saved_rows():
    typologies = CrimeScan(POLICY).read_typologies(fake_ai.typologies()["sector_typologies"])
    as_object = CrimeScan(POLICY).run(CASE, {"typologies": typologies, "declaration": Declaration(UNNAMED["sources"])})
    as_rows = CrimeScan(POLICY).run(CASE, {"typologies": typologies, "declaration": UNNAMED})
    assert [m.to_dict() for m in as_object["match_results"]] == [m.to_dict() for m in as_rows["match_results"]]
    assert as_object["breach_count"] == 1


def test_the_crime_scan_rejects_a_policy_that_is_not_a_dict():
    with pytest.raises(ValueError, match="policy must be a dict"):
        CrimeScan(["policy"])
