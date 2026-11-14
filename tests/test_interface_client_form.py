"""ClientForm: the questions that create a client. The typed answers are a hard-coded list."""

from app.interface.client_form import ClientForm
from app.interface.console_ui import ConsoleUI
from app.interface.report_view import ReportView


def _form():
    ui = ConsoleUI()
    return ClientForm(ui, ReportView(ui))


def _type(monkeypatch, *answers):
    waiting = iter(answers)
    monkeypatch.setattr("builtins.input", lambda question="": next(waiting))


def test_a_new_client_reference_is_made_up_of_cl_and_eight_characters():
    first, second = _form().generate_client_id(), _form().generate_client_id()
    assert first.startswith("CL-") and len(first) == 11
    assert first != second


def test_the_pep_choices_and_payment_methods_are_fixed_lists():
    assert ClientForm.PEP_OPTIONS[0] == "None"
    assert ClientForm.PAYMENT_METHODS == ["cash", "loan", "asset_sale"]


def test_the_declaration_is_asked_until_it_is_long_enough(monkeypatch, capsys):
    _type(monkeypatch, "short", "My wealth came from thirty years of salary and one property sale.")
    text = _form().get_sow_declaration()
    assert text == "My wealth came from thirty years of salary and one property sale."
    assert "[ERROR]" in capsys.readouterr().out


def test_no_jobs_are_added_when_the_officer_says_no(monkeypatch):
    _type(monkeypatch, "n")
    assert _form().get_career_history() == []


def test_no_assets_are_added_when_the_officer_says_no(monkeypatch):
    _type(monkeypatch, "n")
    assert _form().get_investments() == []
