"""The JSON schemas every AI reply is checked against. A reply that breaks its schema is
rejected and asked again, so these tests pin down what a valid reply looks like."""

import json
import os

import jsonschema
import pytest

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "schemas")


def _load_schema(name: str) -> dict:
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


TYPOLOGY_SCHEMA = _load_schema("typology_response.schema.json")
RESEARCH_SCHEMA = _load_schema("research_response.schema.json")


def _valid_typology(typology_id: str = "test_typology") -> dict:
    return {
        "typology_id": typology_id,
        "name": "Test typology name",
        "crime_category": "TRADE_BASED_ML",
        "description": "First sentence about the pattern. Second sentence.",
        "source_ids": ["R1"],
        "source_quotes": [
            {
                "report_id": "R1",
                "quote": "Trade-based money laundering is one of the main methods.",
            }
        ],
        "indicators": [
            {"indicator": "source_contradicts_occupation", "weight": "core"},
            {"indicator": "counterparty_unnamed", "weight": "supporting"},
        ],
        "typical_documents": ["Bank statements", "Invoices"],
    }


def _valid_typology_response(typologies=None) -> dict:
    return {
        "reasoning": "Reports matched this industry. Typologies were generated based on known patterns.",
        "sector_typologies": typologies if typologies is not None else [_valid_typology()],
        "expected_jurisdictions": ["SG", "MY"],
        "max_accumulation_per_year_sgd": 500000,
    }


def _valid_report(title: str = "Test Report") -> dict:
    return {
        "organisation": "FATF",
        "title": title,
        "year": 2020,
        "url": "https://www.fatf-gafi.org/test-report",
        "excerpts": ["Excerpt from the report."],
        "summary": ["Over-invoicing of goods to move funds.", "Use of shell companies."],
    }


def _valid_research_response(reports=None) -> dict:
    return {"reports": reports if reports is not None else [_valid_report()]}


# ---- typology replies ----

def test_valid_typology_fixture_passes_schema():
    jsonschema.validate(instance=_valid_typology_response(), schema=TYPOLOGY_SCHEMA)


def test_empty_typologies_passes_schema():
    jsonschema.validate(instance=_valid_typology_response(typologies=[]), schema=TYPOLOGY_SCHEMA)


def test_missing_source_ids_fails_schema():
    t = _valid_typology()
    del t["source_ids"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_valid_typology_response(typologies=[t]), schema=TYPOLOGY_SCHEMA)


def test_empty_quote_fails_schema():
    t = _valid_typology()
    t["source_quotes"] = [{"report_id": "R1", "quote": ""}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_valid_typology_response(typologies=[t]), schema=TYPOLOGY_SCHEMA)


def test_extra_risk_level_field_fails_schema():
    t = {**_valid_typology(), "risk_level": "high"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_valid_typology_response(typologies=[t]), schema=TYPOLOGY_SCHEMA)


def test_no_core_indicator_fails_schema():
    t = _valid_typology()
    t["indicators"] = [
        {"indicator": "source_contradicts_occupation", "weight": "supporting"},
        {"indicator": "counterparty_unnamed", "weight": "supporting"},
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_valid_typology_response(typologies=[t]), schema=TYPOLOGY_SCHEMA)


def test_source_id_wrong_format_fails_schema():
    """source_ids entries must match ^R[0-9]+$."""
    t = _valid_typology()
    t["source_ids"] = ["X1"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_valid_typology_response(typologies=[t]), schema=TYPOLOGY_SCHEMA)


def test_missing_source_quotes_fails_schema():
    t = _valid_typology()
    del t["source_quotes"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_valid_typology_response(typologies=[t]), schema=TYPOLOGY_SCHEMA)


# ---- research replies ----

def test_valid_research_fixture_passes_schema():
    jsonschema.validate(instance=_valid_research_response(), schema=RESEARCH_SCHEMA)


def test_empty_research_reports_passes_schema():
    jsonschema.validate(instance=_valid_research_response(reports=[]), schema=RESEARCH_SCHEMA)


def test_report_missing_url_fails_schema():
    r = _valid_report()
    del r["url"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_valid_research_response(reports=[r]), schema=RESEARCH_SCHEMA)


def test_report_extra_risk_level_fails_schema():
    r = {**_valid_report(), "risk_level": "high"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_valid_research_response(reports=[r]), schema=RESEARCH_SCHEMA)
