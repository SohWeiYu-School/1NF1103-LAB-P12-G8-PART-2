"""web_browser.py - a Flask test client that behaves like the officer's browser.

The web app refuses any POST without the CSRF token its form was given. A real browser sends
it because the token is a hidden box in every form. This client does the same: it opens a
page once, reads the token from its form, and sends it with every POST it makes.

Tests that check the refusal itself use the plain test_client() instead.
"""

import re

from flask import Flask
from flask.testing import FlaskClient

TOKEN_BOX = re.compile(r'name="csrf_token" value="([^"]+)"')


class BrowserClient(FlaskClient):
    """A test client that sends the page's CSRF token with every POST, like a browser."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.token: str = ""

    def read_token(self, page: str = "/client/new") -> str:
        """Open a page with a form and keep the token in its hidden box."""
        found = TOKEN_BOX.search(self.get(page).get_data(as_text=True))
        if found is None:
            raise AssertionError(f"{page} has no csrf_token box in its form")
        self.token = found.group(1)
        return self.token

    def open(self, *args, **kwargs):
        if kwargs.get("method", "GET").upper() == "POST":
            kwargs["headers"] = {**dict(kwargs.get("headers") or {}), "X-CSRFToken": self.token}
        return super().open(*args, **kwargs)


def browser(flask: Flask) -> BrowserClient:
    """A browser-like test client for this Flask app, already holding a token."""
    flask.test_client_class = BrowserClient
    client = flask.test_client()
    client.read_token()
    return client
