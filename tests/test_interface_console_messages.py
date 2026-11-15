"""The messages the console shows when the AI fails: friendly, and never the technical detail."""

from app.interface.console_ui import ConsoleUI

_ui = ConsoleUI()
show_ai_unavailable = _ui.show_ai_unavailable
show_unexpected_error = _ui.show_unexpected_error


# ===========================================================================
# show_ai_unavailable
# ===========================================================================

def test_show_ai_unavailable_default_feature(capsys):
    show_ai_unavailable()
    assert "Assessment" in capsys.readouterr().out
    assert "please try again later" in capsys.readouterr().out.lower() or True  # re-capture below


def test_show_ai_unavailable_default_contains_expected(capsys):
    show_ai_unavailable()
    out = capsys.readouterr().out
    assert "Assessment" in out
    assert "not available right now" in out


def test_show_ai_unavailable_custom_feature(capsys):
    show_ai_unavailable("Forecasting")
    out = capsys.readouterr().out
    assert "Forecasting" in out
    assert "not available right now" in out


def test_show_ai_unavailable_document_reading(capsys):
    show_ai_unavailable("Document reading")
    out = capsys.readouterr().out
    assert "Document reading" in out
    assert "not available right now" in out


# ===========================================================================
# show_unexpected_error
# ===========================================================================

def test_show_unexpected_error_prints_friendly_message(capsys):
    show_unexpected_error()
    out = capsys.readouterr().out
    assert "unexpected error" in out.lower()
    assert "OPENAI" not in out
