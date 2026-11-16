"""Config: policy and vocabulary held as one object."""

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
