"""Config: policy and vocabulary held as one object."""

import pytest

from app.model.account import Account
from app.model.config import Config

POLICY = {"country_aliases": {"uae": "united arab emirates", "hk": "hong kong"}}
VOCABULARY = {"crime_categories": {"TRADE_BASED_ML": "Trade-based money laundering"}}


def test_config_gives_back_what_it_was_given():
    config = Config(POLICY, VOCABULARY)
    assert config.policy is POLICY
    assert config.vocabulary is VOCABULARY


def test_category_name_reads_the_vocabulary():
    assert Config(POLICY, VOCABULARY).category_name("TRADE_BASED_ML") == "Trade-based money laundering"


def test_category_name_returns_an_unknown_code_unchanged():
    assert Config(POLICY, VOCABULARY).category_name("NOT_A_CODE") == "NOT_A_CODE"


def test_same_country_maps_short_forms_to_one_spelling():
    config = Config(POLICY, VOCABULARY)
    assert config.same_country(" UAE ") == "united arab emirates"
    assert config.same_country("HK") == "hong kong"


def test_same_country_lower_cases_names_with_no_short_form():
    assert Config(POLICY, VOCABULARY).same_country("Singapore") == "singapore"


def test_same_country_copes_with_an_empty_name():
    assert Config({}, {}).same_country(None) == ""


def test_config_made_with_two_arguments_has_no_accounts():
    config = Config(POLICY, VOCABULARY)
    assert config.accounts == [] and config.account("a@b.com") is None


def test_config_holds_the_accounts_and_finds_one_by_email_ignoring_case():
    shareen = Account("shareen@orbit.local", "Shareen", "officer")
    admin = Account("admin@orbit.local", "Orbit Admin", "admin")
    config = Config(POLICY, VOCABULARY, [admin, shareen])
    assert config.accounts == [admin, shareen]
    assert config.account(" SHAREEN@orbit.local ") is shareen
    assert config.account("nobody@orbit.local") is None
    assert config.account(None) is None


def test_accounts_must_be_a_list_of_accounts():
    for bad in ("shareen", [{"email": "a@b.com"}], [Account("a@b.com", "Wei Yu"), None], {"a": 1}):
        with pytest.raises(ValueError, match="list of Account"):
            Config(POLICY, VOCABULARY, bad)


def test_the_accounts_property_gives_a_copy():
    config = Config(POLICY, VOCABULARY, [Account("a@b.com", "Wei Yu")])
    config.accounts.clear()
    assert len(config.accounts) == 1


def test_the_list_given_in_is_copied_too():
    given = [Account("a@b.com", "Wei Yu")]
    config = Config(POLICY, VOCABULARY, given)
    given.clear()
    assert len(config.accounts) == 1


def test_account_with_an_empty_or_missing_email_finds_nothing_even_next_to_an_unset_account():
    config = Config(POLICY, VOCABULARY, [Account(), Account("a@b.com", "Wei Yu")])
    assert config.account("") is None and config.account(None) is None and config.account("   ") is None
