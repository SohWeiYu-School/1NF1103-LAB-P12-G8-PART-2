"""Claims: the client's declared figures."""

import pytest

from app.model.claims import Claims

SPLIT = {"property": 0.28, "listed_equities": 0.11, "private_business": 0.41, "cash": 0.2}


def _claims(**changes):
    details = {"declared_net_worth": 16500000, "expected_aum": 5000000, "pep_status": "None",
               "asset_composition": SPLIT, "wealth_countries": ["Singapore"],
               "declared_counterparties": []}
    details.update(changes)
    return Claims(**details)


@pytest.mark.parametrize("status", ["None", "no", " N/A ", "Not a PEP"])
def test_ways_of_writing_no_are_not_a_pep(status):
    assert not _claims(pep_status=status).is_pep()


@pytest.mark.parametrize("status", ["", "   ", None])
def test_a_blank_pep_answer_is_unknown_so_it_is_not_taken_as_no(status):
    claims = _claims(pep_status=status)
    assert claims.is_pep()                                  # unknown counts as a PEP: the cautious side
    assert any("PEP question is not answered" in problem for problem in claims.problems())


def test_a_blank_pep_answer_is_still_accepted_by_the_setter():
    claims = _claims()
    claims.pep_status = ""                                  # auto-fill leaves it blank; problems() lists it
    assert claims.pep_status == ""


def test_an_answered_pep_question_has_no_pep_problem():
    for status in ("None", "no", "Domestic PEP"):
        assert not any("PEP" in problem for problem in _claims(pep_status=status).problems())


@pytest.mark.parametrize("status", ["Domestic PEP", "Foreign PEP", "Family member / close associate of a PEP"])
def test_any_other_status_is_a_pep(status):
    assert _claims(pep_status=status).is_pep()


def test_liquid_share_is_cash_plus_listed_equities():
    assert _claims().liquid_share() == pytest.approx(0.31)
    assert _claims(asset_composition=None).liquid_share() == 0


def test_claims_reject_zero_net_worth_but_allow_not_given():
    with pytest.raises(ValueError, match="greater than 0"):
        _claims(declared_net_worth=0)
    claims = _claims()
    with pytest.raises(ValueError, match="greater than 0"):
        claims.declared_net_worth = 0
    claims.declared_net_worth = None
    assert claims.declared_net_worth is None
    claims.declared_net_worth = 1
    assert claims.declared_net_worth == 1


def test_claims_reject_negative_or_non_number_figures():
    with pytest.raises(ValueError):
        _claims(declared_net_worth=-1)
    with pytest.raises(ValueError):
        _claims(expected_aum="5m")
    claims = _claims()
    with pytest.raises(ValueError):
        claims.biggest_wealth_jump = -5


def test_a_share_must_be_between_0_and_1():
    with pytest.raises(ValueError):
        _claims(asset_composition={"cash": 20})
    claims = _claims()
    with pytest.raises(ValueError):
        claims.asset_composition = {"cash": -0.1}


def test_a_split_that_does_not_add_up_is_a_problem():
    assert _claims().problems() == []
    assert _claims(asset_composition={"cash": 0.5, "property": 0.3}).problems() == [
        "The asset split adds up to 80%, not 100%."]


def test_missing_net_worth_is_a_problem():
    assert "Declared net worth is missing: enter an amount greater than 0." in _claims(declared_net_worth=None).problems()


def test_expecting_to_place_more_than_he_has_is_a_warning():
    assert _claims().warnings() == []
    assert _claims(expected_aum=20000000).warnings() == [
        "Expected assets with the bank are more than the declared net worth."]


def test_to_dict_keeps_the_saved_layout():
    data = _claims(biggest_wealth_jump=2000000, wealth_jump_years=3).to_dict()
    assert data["declared_net_worth"] == 16500000
    assert data["asset_composition"] == SPLIT
    assert data["wealth_jump_years"] == 3
    assert _claims(asset_composition=None).to_dict()["asset_composition"] is None


def test_the_problems_say_what_to_enter_and_do_not_assume_the_clients_gender():
    problems = _claims(declared_net_worth=None, pep_status="").problems()
    assert "Declared net worth is missing: enter an amount greater than 0." in problems
    assert any("which kind of PEP the client is" in problem for problem in problems)
    assert not any(" he " in problem for problem in problems)
