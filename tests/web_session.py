"""Sign a Flask test client in, the way the sign-in page does, without going through the page."""

from app.application.app import App
from app.model.account import Account


def account_with_role(application: App, role: str = Account.OFFICER) -> Account:
    """The first configured account with this role."""
    return next(account for account in application.accounts() if account.role == role)


def sign_in(client, application: App, role: str = Account.OFFICER) -> Account:
    """Put an account of this role into the client's session and return it. No audit line is written."""
    account = account_with_role(application, role)
    with client.session_transaction() as session:
        session["account"] = account.email
    return account
