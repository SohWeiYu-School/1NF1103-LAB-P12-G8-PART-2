"""Typology, MatchResult and ResearchReport: the crime scan's data objects."""

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
