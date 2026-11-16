"""MatchResult: how one typology matched one client."""

import pytest

from app.model.match_result import MatchResult
from app.model.typology import Typology

INDICATORS = [{"indicator": "gift_or_inheritance_unnamed", "weight": "core"},
              {"indicator": "counterparty_unnamed", "weight": "core"},
              {"indicator": "related_party_transaction", "weight": "supporting"},
              {"indicator": "unvalued_source_present", "weight": "supporting"}]
MATCH_KEYS = ["typology_id", "name", "source_ids", "breached", "category", "core_indicators", "core_fired",
              "supporting_indicators", "supporting_fired", "typical_documents"]


def _typology(indicators=INDICATORS):
    return Typology("TYP-1", "Trade-based laundering", indicators, ["R1", "R2"],
                    typical_documents=["Freight invoices"])


def test_a_match_is_breached_only_when_every_core_sign_fired():
    typology = _typology()
    assert MatchResult(typology, ["gift_or_inheritance_unnamed", "counterparty_unnamed"]).breached
    assert not MatchResult(typology, ["gift_or_inheritance_unnamed"]).breached
    assert not MatchResult(typology).breached


def test_a_typology_with_no_core_signs_is_never_breached():
    assert not MatchResult(_typology([{"indicator": "x", "weight": "supporting"}]), []).breached


def test_a_match_keeps_the_typology_it_matched():
    typology = _typology()
    match = MatchResult(typology, ["counterparty_unnamed"], ["unvalued_source_present"], "weak_signal")
    assert match.typology is typology
    assert match.category == "weak_signal"
    assert match.fired() == ["counterparty_unnamed", "unvalued_source_present"]


def test_to_dict_is_the_saved_match_layout_in_order():
    match = MatchResult(_typology(), ["gift_or_inheritance_unnamed", "counterparty_unnamed"],
                        ["related_party_transaction"], "high")
    saved = match.to_dict()
    assert list(saved) == MATCH_KEYS                     # no field lost, none moved
    assert saved == {
        "typology_id": "TYP-1", "name": "Trade-based laundering", "source_ids": ["R1", "R2"], "breached": True,
        "category": "high", "core_indicators": ["gift_or_inheritance_unnamed", "counterparty_unnamed"],
        "core_fired": ["gift_or_inheritance_unnamed", "counterparty_unnamed"],
        "supporting_indicators": ["related_party_transaction", "unvalued_source_present"],
        "supporting_fired": ["related_party_transaction"], "typical_documents": ["Freight invoices"]}


def test_a_sign_that_is_not_in_the_typology_cannot_have_fired():
    with pytest.raises(ValueError, match="core signs"):
        MatchResult(_typology(), ["related_party_transaction"])
    with pytest.raises(ValueError, match="supporting signs"):
        MatchResult(_typology(), [], ["counterparty_unnamed"])


def test_an_unknown_category_is_rejected():
    with pytest.raises(ValueError, match="match category"):
        MatchResult(_typology(), [], [], "very high")


def test_a_match_needs_a_typology_object():
    with pytest.raises(ValueError, match="needs a Typology"):
        MatchResult({"typology_id": "TYP-1"})


def test_the_match_cannot_be_changed_from_outside():
    match = MatchResult(_typology(), ["counterparty_unnamed"], [], "no_match")
    match.core_fired.append("gift_or_inheritance_unnamed")
    match.fired().append("x")
    assert match.core_fired == ["counterparty_unnamed"] and not match.breached
