"""The five warning signs, each tested on its own declaration."""

import pytest

from app.logic.indicator import (CounterpartyUnnamed, GiftOrInheritanceUnnamed, Indicator,
                                 RelatedPartyTransaction, SourceContradictsOccupation, UnvaluedSource)
from app.model.declaration import Declaration


def _declaration(*sources):
    return Declaration([{"source_type": "salary", "counterparty": "Employer Ltd", "amount_sgd": 100000,
                         "occupation_mismatch": False, **source} for source in sources])


CLEAN = _declaration({})


def test_the_abstract_indicator_cannot_be_created():
    with pytest.raises(TypeError):
        Indicator()


def test_every_sign_is_an_indicator_with_its_own_name():
    signs = [GiftOrInheritanceUnnamed(), CounterpartyUnnamed(), SourceContradictsOccupation(),
             UnvaluedSource(), RelatedPartyTransaction()]
    assert all(isinstance(sign, Indicator) for sign in signs)
    assert [sign.NAME for sign in signs] == [
        "gift_or_inheritance_unnamed", "counterparty_unnamed", "source_contradicts_occupation",
        "unvalued_source_present", "related_party_transaction"]


def test_no_sign_fires_on_a_clean_declaration():
    for sign in (GiftOrInheritanceUnnamed(), CounterpartyUnnamed(), SourceContradictsOccupation(),
                 UnvaluedSource(), RelatedPartyTransaction()):
        assert sign.fires(CLEAN) is False


def test_a_gift_from_someone_unnamed_fires():
    assert GiftOrInheritanceUnnamed().fires(_declaration({"source_type": "gift", "counterparty": None}))
    assert GiftOrInheritanceUnnamed().fires(_declaration({"source_type": "inheritance", "counterparty": None}))


def test_a_gift_from_a_named_person_does_not_fire():
    assert not GiftOrInheritanceUnnamed().fires(_declaration({"source_type": "gift", "counterparty": "Uncle Lim"}))


def test_an_unnamed_salary_is_not_an_unnamed_gift():
    assert not GiftOrInheritanceUnnamed().fires(_declaration({"counterparty": None}))


def test_unnamed_counterparties_fire_at_the_policy_limit():
    one_unnamed = _declaration({"counterparty": None}, {})
    assert CounterpartyUnnamed({"thresholds": {"unknown_counterparty_limit": 1}}).fires(one_unnamed)
    assert not CounterpartyUnnamed({"thresholds": {"unknown_counterparty_limit": 2}}).fires(one_unnamed)


def test_with_no_policy_one_unnamed_counterparty_is_enough():
    assert CounterpartyUnnamed().fires(_declaration({"counterparty": None}))


def test_a_source_that_does_not_fit_the_occupation_fires():
    assert SourceContradictsOccupation().fires(_declaration({"occupation_mismatch": True}))


def test_a_source_with_no_amount_fires():
    assert UnvaluedSource().fires(_declaration({"amount_sgd": None}))


def test_a_job_source_the_forecast_explains_does_not_fire():
    assert not UnvaluedSource().fires(_declaration({"amount_sgd": None, "amount_explained_by_forecast": True}))


@pytest.mark.parametrize("counterparty", ["His brother-in-law", "A business ASSOCIATE", "Family trust"])
def test_a_related_party_fires(counterparty):
    assert RelatedPartyTransaction().fires(_declaration({"counterparty": counterparty}))


def test_an_unrelated_company_does_not_fire():
    assert not RelatedPartyTransaction().fires(_declaration({"counterparty": "Meridian Harbour Bank"}))


def test_every_sign_rejects_a_policy_that_is_not_a_dict():
    for sign in (GiftOrInheritanceUnnamed, CounterpartyUnnamed, SourceContradictsOccupation,
                 UnvaluedSource, RelatedPartyTransaction):
        with pytest.raises(ValueError, match="policy must be a dict"):
            sign(["not", "a", "dict"])
        assert sign(None) is not None and sign({}) is not None
