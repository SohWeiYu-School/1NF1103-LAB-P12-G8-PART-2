"""Account: validation, the unset account and the saved layout."""

import pytest

from app.model.account import Account


def test_a_good_account_is_kept_with_email_lower_cased_and_trimmed():
    account = Account("  Shareen@Orbit.local ", " Shareen ", "officer")
    assert (account.email, account.name, account.role) == ("shareen@orbit.local", "Shareen", "officer")
    assert account.is_admin() is False


def test_the_admin_role_is_recognised():
    assert Account("admin@orbit.local", "Orbit Admin", "admin").is_admin() is True


def test_an_account_with_all_defaults_is_unset():
    account = Account()
    assert (account.email, account.name, account.role) == ("", "", "officer")


@pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "a b@c.com", "A@@c.com", "x@y.123"])
def test_a_bad_email_is_refused_with_a_message(email):
    with pytest.raises(ValueError, match="email"):
        Account(email, "Wei Yu", "officer")


@pytest.mark.parametrize("name", ["", "A", "x" * 41, "Bob3", "<b>Bob</b>", "  ", "-Bob"])
def test_a_bad_name_is_refused_with_a_message(name):
    with pytest.raises(ValueError, match="name"):
        Account("a@b.com", name, "officer")


def test_an_email_alone_or_a_name_alone_is_refused():
    with pytest.raises(ValueError):
        Account("a@b.com", "", "officer")
    with pytest.raises(ValueError):
        Account("", "Wei Yu", "officer")


def test_a_role_outside_the_allowed_ones_is_refused():
    with pytest.raises(ValueError, match="admin, officer"):
        Account("a@b.com", "Wei Yu", "boss")


def test_text_is_required():
    with pytest.raises(ValueError, match="text"):
        Account(None, "Wei Yu", "officer")          # type: ignore[arg-type]


def test_names_with_dots_apostrophes_and_dashes_are_allowed():
    assert Account("a@b.com", "Mary-Jane O'Neil Jr.", "officer").name == "Mary-Jane O'Neil Jr."


def test_to_dict_and_from_dict_round_trip():
    account = Account("adrian@orbit.local", "Adrian", "officer")
    again = Account.from_dict(account.to_dict())
    assert again.to_dict() == account.to_dict() == {"email": "adrian@orbit.local", "name": "Adrian", "role": "officer"}


@pytest.mark.parametrize("data", [None, [], "x", 5])
def test_from_dict_refuses_something_that_is_not_an_object(data):
    with pytest.raises(ValueError, match="object"):
        Account.from_dict(data)


def test_from_dict_refuses_a_bad_field():
    with pytest.raises(ValueError):
        Account.from_dict({"email": "bad", "name": "Wei Yu", "role": "officer"})
