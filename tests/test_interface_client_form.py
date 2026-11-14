"""ClientForm: the questions that create a client. The typed answers are a hard-coded list."""

from app.interface.client_form import ClientForm
from app.interface.console_ui import ConsoleUI
from app.interface.report_view import ReportView
from app.model.client_record import ClientRecord
from tests.logic_fixtures import sample_case


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


def test_editing_with_no_changes_returns_the_same_record(monkeypatch):
    """edit_existing_client returns the edited record as a ClientRecord."""
    _type(monkeypatch, "8")
    record = ClientRecord.from_dict(sample_case())
    edited = _form().edit_existing_client(record)
    assert isinstance(edited, ClientRecord)
    assert edited.to_dict() == record.to_dict()


def test_a_new_current_job_title_in_the_profile_is_kept_on_the_current_job(monkeypatch):
    """The current job is listed in career_history too: a profile edit changes both, so it is
    not lost when the record is saved."""
    _type(monkeypatch, "1", "", "", "Chief Executive Officer", "", "", "", "", "", "", "", "n")
    record = ClientRecord.from_dict(sample_case())
    edited = _form().edit_existing_client(record)
    assert edited.current_job().occupation == "Chief Executive Officer"
    assert edited.to_dict()["career"]["occupation"] == "Chief Executive Officer"
    assert record.current_job().occupation == sample_case()["career"]["occupation"]   # the original is untouched


def test_a_client_whose_saved_record_cannot_be_read_is_reported(monkeypatch, capsys):
    def find(client_ref):
        raise ValueError(f"Client {client_ref} could not be loaded because age must be between 18 and 120.")

    _type(monkeypatch, "CL-BROKEN1", "")
    assert _form().find_existing_client(find_fn=find) is None
    out = capsys.readouterr().out
    assert "could not be loaded" in out and "No client found" not in out


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


NEW_CLIENT_ANSWERS = ("Daniel Tan", "Malaysian", "Chief Operating Officer", "C-suite", "Shipping",
                      "Straits Harbour", "2500", "Singapore", "51", "1998",    # profile
                      "n", "n",                                                # no earlier jobs, no assets
                      "4000000", "1000000", "1", "Singapore", "50", "30", "0", "20", "n", "",   # claims
                      "My wealth came from thirty years of salary and one property sale in Singapore.",
                      "n")                                                     # no documents


def test_a_new_client_is_saved_and_returned_as_a_client_record(monkeypatch, capsys):
    saved = []
    _type(monkeypatch, *NEW_CLIENT_ANSWERS, "y", "1")                          # save, then assess now
    record = _form().create_new_client(save_fn=lambda client: saved.append(client) or True)
    assert isinstance(record, ClientRecord) and saved == [record]
    assert record.profile.name == "Daniel Tan" and record.profile.age == 51
    assert record.to_dict()["career"]["occupation"] == "Chief Operating Officer"   # kept in "career"
    assert record.claims.declared_net_worth == 4000000
    assert "Daniel Tan" in capsys.readouterr().out                             # shown before saving


def test_a_new_client_that_could_not_be_saved_is_reported(monkeypatch, capsys):
    _type(monkeypatch, *NEW_CLIENT_ANSWERS, "y", "")
    assert _form().create_new_client(save_fn=lambda client: False) is None
    assert "could not be saved" in capsys.readouterr().out
