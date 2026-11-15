"""Typology, MatchResult and ResearchReport: the crime scan's data objects."""

import pytest

from app.model.match_result import MatchResult
from app.model.typology import Typology

INDICATORS = [{"indicator": "gift_or_inheritance_unnamed", "weight": "core"},
              {"indicator": "counterparty_unnamed", "weight": "core"},
              {"indicator": "related_party_transaction", "weight": "supporting"}]


def _typology(indicators=INDICATORS):
    return Typology("TYP-1", "Trade-based laundering", indicators, ["R1", "R2"])


def test_typology_separates_core_from_supporting_signs():
    typology = _typology()
    assert typology.core_indicators() == ["gift_or_inheritance_unnamed", "counterparty_unnamed"]
    assert typology.supporting_indicators() == ["related_party_transaction"]
    assert typology.cited_report_ids() == ["R1", "R2"]


def test_typology_indicators_cannot_be_changed_from_outside():
    typology = _typology()
    typology.indicators[0]["weight"] = "supporting"
    assert len(typology.core_indicators()) == 2


def test_a_match_is_breached_only_when_every_core_sign_fired():
    typology = _typology()
    assert MatchResult(typology, ["gift_or_inheritance_unnamed", "counterparty_unnamed"]).breached
    assert not MatchResult(typology, ["gift_or_inheritance_unnamed"]).breached
    assert not MatchResult(typology).breached


def test_a_typology_with_no_core_signs_is_never_breached():
    assert not MatchResult(_typology([{"indicator": "x", "weight": "supporting"}]), []).breached


REPLY_TYPOLOGY = {
    "typology_id": "trade_based_laundering", "name": "Trade-based laundering", "crime_category": "TRADE_BASED_ML",
    "description": "Freight is over-invoiced.", "source_ids": ["R1", "R2"],
    "source_quotes": [{"report_id": "R1", "quote": "Over-invoicing is used."}],
    "indicators": INDICATORS, "typical_documents": ["Freight invoices", "Bills of lading"]}
REPLY_KEYS = ["typology_id", "name", "crime_category", "description", "source_ids", "source_quotes",
              "indicators", "typical_documents"]


def test_a_typology_reads_every_field_of_the_typology_reply():
    typology = Typology.from_dict(REPLY_TYPOLOGY)
    assert (typology.typology_id, typology.name, typology.crime_category, typology.description) == (
        "trade_based_laundering", "Trade-based laundering", "TRADE_BASED_ML", "Freight is over-invoiced.")
    assert typology.cited_report_ids() == ["R1", "R2"]
    assert typology.source_quotes == [{"report_id": "R1", "quote": "Over-invoicing is used."}]
    assert typology.typical_documents == ["Freight invoices", "Bills of lading"]
    assert typology.core_indicators() == ["gift_or_inheritance_unnamed", "counterparty_unnamed"]
    assert typology.verified is False


def test_to_dict_gives_back_the_reply_layout_in_the_same_order():
    saved = Typology.from_dict(REPLY_TYPOLOGY).to_dict()
    assert saved == REPLY_TYPOLOGY
    assert list(saved) == REPLY_KEYS                    # no field lost, none moved


def test_a_verified_copy_keeps_only_the_checked_sources_and_says_so():
    typology = Typology.from_dict(REPLY_TYPOLOGY)
    checked = typology.with_verified_sources(["R1"], [{"report_id": "R1", "quote": "Over-invoicing is used."}],
                                             False, ["R1"])
    assert checked.verified and not typology.verified       # the original is unchanged
    assert checked.cited_report_ids() == ["R1"] and typology.cited_report_ids() == ["R1", "R2"]
    assert (checked.corroborated, checked.outdated_source_ids) == (False, ["R1"])
    saved = checked.to_dict()
    assert list(saved) == REPLY_KEYS + ["corroborated", "outdated_source_ids"]
    assert saved == {**REPLY_TYPOLOGY, "source_ids": ["R1"], "corroborated": False, "outdated_source_ids": ["R1"]}
    assert Typology.from_dict(saved).to_dict() == saved       # a saved verified typology reads back the same


def test_an_outdated_source_must_be_one_of_its_sources():
    with pytest.raises(ValueError, match="not among the typology's sources"):
        Typology.from_dict(REPLY_TYPOLOGY).with_verified_sources(["R1"], [], True, ["R2"])


@pytest.mark.parametrize("bad", [{"typology_id": 7}, {"name": None}, {"indicators": "core"},
                                 {"indicators": [{"indicator": "x", "weight": "optional"}]},
                                 {"indicators": [{"weight": "core"}]}, {"source_ids": "R1"},
                                 {"source_quotes": ["R1: a quote"]}, {"typical_documents": [3]}])
def test_impossible_values_are_rejected_with_a_clear_message(bad):
    with pytest.raises(ValueError, match="typology"):
        Typology.from_dict({**REPLY_TYPOLOGY, **bad})


def test_a_typology_that_is_not_an_object_is_rejected():
    with pytest.raises(ValueError, match="JSON object"):
        Typology.from_dict("trade_based_laundering")


def test_the_typology_cannot_be_changed_from_outside():
    typology = Typology.from_dict(REPLY_TYPOLOGY)
    typology.source_quotes[0]["quote"] = "changed"
    typology.to_dict()["indicators"][0]["weight"] = "supporting"
    typology.typical_documents.append("Anything")
    assert typology.to_dict() == REPLY_TYPOLOGY
