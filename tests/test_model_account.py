"""Account: validation, the unset account and the saved layout."""

import pytest
from werkzeug.security import generate_password_hash

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


@pytest.mark.parametrize("name", ["", "A", "x" * 41, "Bob3", "<b>Bob</b>", "-Bob"])
def test_a_bad_name_is_refused_with_a_message(name):
    with pytest.raises(ValueError, match="name"):
        Account("a@b.com", name, "officer")


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
    assert again.to_dict() == account.to_dict() == {"email": "adrian@orbit.local", "name": "Adrian", "role": "officer", "password_hash": ""}


@pytest.mark.parametrize("data", [None, [], "x", 5])
def test_from_dict_refuses_something_that_is_not_an_object(data):
    with pytest.raises(ValueError, match="object"):
        Account.from_dict(data)


def test_from_dict_refuses_a_bad_field():
    with pytest.raises(ValueError):
        Account.from_dict({"email": "bad", "name": "Wei Yu", "role": "officer"})


@pytest.mark.parametrize("data", [{}, {"email": "", "name": "Wei Yu"}, {"email": "a@b.com", "name": ""},
                                  {"email": "  ", "name": "  "}, {"email": None, "name": "Wei Yu"},
                                  {"email": "a@b.com", "name": 5}])
def test_from_dict_refuses_an_entry_with_no_email_or_no_name(data):
    with pytest.raises(ValueError, match="needs an email and a name"):
        Account.from_dict(data)


def test_the_unset_account_stays_legal_but_is_never_an_admin():
    assert Account().is_admin() is False
    assert Account(role="admin").is_admin() is False          # an admin role with no email is still unset


@pytest.mark.parametrize("name", [" TERMINAL ", "unknown"])
def test_the_name_terminal_is_reserved_in_any_case(name):
    with pytest.raises(ValueError, match="reserved"):
        Account("a@b.com", name, "officer")


def test_a_name_that_only_contains_terminal_is_fine():
    assert Account("a@b.com", "Terminal Tan", "officer").name == "Terminal Tan"


def _with_password(password="officer123"):
    return Account("a@b.com", "Wei Yu", "officer", generate_password_hash(password))


def test_check_password_accepts_only_the_right_password():
    account = _with_password()
    assert account.check_password("officer123") is True
    assert account.check_password("officer124") is False
    assert account.check_password("") is False
    assert account.check_password(None) is False       # type: ignore[arg-type]


def test_an_account_with_no_password_set_never_passes_check_password():
    assert Account("a@b.com", "Wei Yu").check_password("") is False
    assert Account("a@b.com", "Wei Yu").check_password("anything") is False
    assert Account().check_password("x") is False
    assert Account("a@b.com", "Wei Yu").has_password is False and _with_password().has_password is True


@pytest.mark.parametrize("value", ["officer123", "md5:abc", "plain text"])
def test_a_password_hash_that_is_not_a_werkzeug_hash_is_refused(value):
    with pytest.raises(ValueError, match="plain password"):
        Account("a@b.com", "Wei Yu", "officer", value)


def test_pbkdf2_hashes_are_accepted_and_the_hash_round_trips():
    account = Account("a@b.com", "Wei Yu", "officer", generate_password_hash("x", method="pbkdf2:sha256"))
    assert account.check_password("x") is True
    assert Account.from_dict(account.to_dict()).check_password("x") is True


def test_the_hash_must_be_text_and_an_unset_account_cannot_have_one():
    with pytest.raises(ValueError, match="text"):
        Account("a@b.com", "Wei Yu", "officer", 5)         # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unset"):
        Account(password_hash=generate_password_hash("x"))
