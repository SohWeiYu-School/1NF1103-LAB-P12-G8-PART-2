"""ConsoleUI: every question is asked again until the answer is valid. No real typing: the
answers are a hard-coded list."""

import pytest

from app.interface.console_ui import ConsoleUI


def _answers(*typed):
    """A made-up way of asking that returns the next hard-coded answer each time."""
    waiting = list(typed)
    asked = []

    def ask(question: str) -> str:
        asked.append(question)
        return waiting.pop(0)

    ask.asked = asked
    return ask


def test_a_wrong_answer_is_asked_again_with_the_reason(capsys):
    ask = _answers("maybe", "", "Y")
    assert ConsoleUI(read=ask).ask_yes_no("Save this client?") is True
    assert len(ask.asked) == 3
    assert capsys.readouterr().out.count("[ERROR] Please answer y or n.") == 2


def test_ask_int_rejects_text_and_numbers_out_of_range(capsys):
    ask = _answers("abc", "200", "51")
    assert ConsoleUI(read=ask).ask_int("Age", 18, 120) == 51
    assert capsys.readouterr().out.count("[ERROR]") == 2


def test_ask_int_may_be_left_blank_only_when_allowed():
    assert ConsoleUI(read=_answers("")).ask_int("End year", 1940, 2026, allow_blank=True) is None
    assert ConsoleUI(read=_answers("", "30")).ask_int("Age", 18, 120) == 30


def test_ask_money_accepts_commas_and_rejects_negatives(capsys):
    assert ConsoleUI(read=_answers("a lot", "-5", "1,650,000")).ask_money("Price paid", allow_zero=True) == 1650000.0
    out = capsys.readouterr().out
    assert "Please enter an amount, e.g. 1500000." in out
    assert "Amounts can't be negative." in out


def test_ask_money_refuses_zero_unless_it_is_allowed(capsys):
    assert ConsoleUI(read=_answers("0", "5")).ask_money("Net worth") == 5.0
    assert "[ERROR] Please enter an amount above zero." in capsys.readouterr().out
    assert ConsoleUI(read=_answers("0")).ask_money("Yearly income", allow_zero=True) == 0.0


def test_ask_text_needs_a_minimum_length():
    assert ConsoleUI(read=_answers("  ", "short", "long enough")).ask_text("Declaration", min_length=6) == "long enough"


def test_ask_choice_returns_the_position_picked(capsys):
    ui = ConsoleUI(read=_answers("9", "2"))
    assert ui.ask_choice("Payment method", ["cash", "loan", "asset_sale"]) == 1
    out = capsys.readouterr().out
    assert "  1. cash" in out and "  3. asset_sale" in out


def test_ask_choice_with_back_returns_none_for_zero():
    assert ConsoleUI(read=_answers("0")).ask_choice("Menu", ["a", "b"], allow_back=True) is None


def test_keep_text_keeps_the_current_value_on_a_blank_answer(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda question: "")
    assert ConsoleUI().keep_text("Name", "Daniel Tan") == "Daniel Tan"


def test_keep_text_takes_a_new_value(monkeypatch):
    typed = iter(["x", "Daniel Tan Wei Ming"])
    monkeypatch.setattr("builtins.input", lambda question: next(typed))
    assert ConsoleUI().keep_text("Name", "Daniel Tan") == "Daniel Tan Wei Ming"


def test_with_no_read_function_the_terminal_is_used(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda question: "y")
    assert ConsoleUI().ask_yes_no("Continue?") is True


def test_a_handed_in_read_and_write_replace_the_terminal(capsys):
    """Every question goes through read and every line through write: nothing reaches the terminal."""
    shown = []
    ui = ConsoleUI(read=_answers("n"), write=shown.append)
    assert ui.ask_yes_no("Continue?") is False
    ui.show_error("Could not save.")
    assert shown == ["[ERROR] Could not save."]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("given", [{"read": "y"}, {"write": 42}])
def test_read_and_write_must_be_functions(given):
    with pytest.raises(ValueError, match="must be a function"):
        ConsoleUI(**given)


def test_messages_and_errors_are_printed(capsys):
    ui = ConsoleUI()
    ui.show_message("Saved.")
    ui.show_error("Could not save.")
    out = capsys.readouterr().out
    assert "Saved." in out and "[ERROR] Could not save." in out


@pytest.mark.parametrize("value, text", [(1650000, "1,650,000"), (0, "0")])
def test_money_is_written_the_same_way_everywhere(value, text):
    assert ConsoleUI().money(value) == text


@pytest.mark.parametrize("typed, number", [("1,650,000", 1650000.0), ("S$1.65m", 1650000.0), ("410k", 410000.0)])
def test_read_number_understands_the_ways_people_type_money(typed, number):
    assert ConsoleUI().read_number(typed) == pytest.approx(number)


def test_read_number_and_read_year_give_none_for_what_cannot_be_read():
    ui = ConsoleUI()
    assert ui.read_number("a lot") is None
    assert ui.read_year("2017") == 2017
    assert ui.read_year("17") is None


def test_keep_money_keeps_the_current_value_on_enter_and_reads_a_new_amount(capsys):
    """keep_money returns the current value unchanged on Enter (a number, or None when there is no
    amount yet: never ""), and a float when a new amount is typed."""
    ask = _answers("", "", "abc", "-5", "1,500,000")
    ui = ConsoleUI(read=ask)
    assert ui.keep_money("Price paid", 250000.0) == 250000.0
    assert ui.keep_money("Price paid", None) is None
    assert ui.keep_money("Price paid", None) == 1500000.0
    assert ask.asked[0] == "Price paid [250000.0]: " and ask.asked[1] == "Price paid []: "      # an empty amount shows as [], as it always did
    assert capsys.readouterr().out.count("[ERROR]") == 2


def test_ask_count_takes_one_whole_number_and_refuses_ranges_and_text(capsys):
    assert ConsoleUI(read=_answers("2,000-3,000", "about 50", "0", "2,500")).ask_count("Employer size") == 2500
    assert capsys.readouterr().out.count("[ERROR] Please enter the number of employees") == 3


def test_ask_words_refuses_numbers_in_a_name(capsys):
    assert ConsoleUI(read=_answers("Daniel 7an", "Daniel Tan")).ask_words("Full name") == "Daniel Tan"
    assert "Letters only please" in capsys.readouterr().out


def test_keep_countries_keeps_on_enter_and_takes_a_new_list():
    ui = ConsoleUI(read=_answers("", "Singapore, Malaysia"))
    current = ["Singapore"]
    assert ui.keep_countries("Wealth countries", current) is current
    assert ui.keep_countries("Wealth countries", current) == ["Singapore", "Malaysia"]


def test_keep_countries_refuses_a_number_once_and_keeps_the_current_list(capsys):
    ask = _answers("S1ngapore")
    current = ["Singapore"]
    assert ConsoleUI(read=ask).keep_countries("Wealth countries", current) is current
    assert ask.asked == ["Wealth countries [Singapore]: "]
    assert "[ERROR] Not changed. Countries must be letters only" in capsys.readouterr().out


def test_the_dropped_document_details_are_listed_with_their_reasons(capsys):
    ConsoleUI().show_dropped_fields(["Age: the value read from the documents (200) is not possible."])
    out = capsys.readouterr().out
    assert "were left empty" in out and "Age: the value read" in out
    ConsoleUI().show_dropped_fields([])
    assert capsys.readouterr().out == ""


def test_keep_money_can_refuse_zero_and_asks_again_straight_away(capsys):
    ask = _answers("0", "-1", "250,000")
    ui = ConsoleUI(read=ask)
    assert ui.keep_money("Declared net worth", 100.0, allow_zero=False) == 250000.0
    out = capsys.readouterr().out
    assert "above zero" in out and "can't be negative" in out
    assert ConsoleUI(read=_answers("0")).keep_money("Yearly income", 5.0) == 0.0      # zero is still fine by default


def test_ask_money_and_ask_countries_can_allow_enter_for_no_answer():
    assert ConsoleUI(read=_answers("")).ask_money("Jump", allow_zero=True, allow_blank=True) is None
    assert ConsoleUI(read=_answers("")).ask_countries("Countries", allow_blank=True) == []
    assert ConsoleUI(read=_answers("", "5")).ask_money("Net worth") == 5.0       # not allowed by default: asked again


def test_a_missing_age_or_employer_size_shows_empty_brackets_not_none():
    ask = _answers("", "")
    ui = ConsoleUI(read=ask)
    assert ui.keep_int("Age", None, 18, 120) is None
    assert ui.keep_count("Employer size", None) is None
    assert ask.asked == ["Age []: ", "Employer size []: "]


def test_a_known_age_or_employer_size_is_shown_and_kept_on_enter():
    ask = _answers("", "")
    ui = ConsoleUI(read=ask)
    assert ui.keep_int("Age", 51, 18, 120) == 51
    assert ui.keep_count("Employer size", "2500") == "2500"
    assert ask.asked == ["Age [51]: ", "Employer size [2500]: "]


def test_the_main_menu_shows_the_product_name_orbit():
    shown = []
    ConsoleUI(read=_answers("1"), write=shown.append).show_app_menu()
    assert any("ORBIT" in line for line in shown)


# ---- the messages shown when the AI fails: friendly, and never the technical detail ----

@pytest.mark.parametrize("feature, shown", [(None, "Assessment"), ("Forecasting", "Forecasting"),
                                            ("Document reading", "Document reading")])
def test_show_ai_unavailable_names_the_feature_and_says_it_is_not_available(capsys, feature, shown):
    ui = ConsoleUI()
    ui.show_ai_unavailable() if feature is None else ui.show_ai_unavailable(feature)
    out = capsys.readouterr().out
    assert shown in out and "not available right now" in out


def test_show_unexpected_error_prints_a_friendly_message_with_no_technical_detail(capsys):
    ConsoleUI().show_unexpected_error()
    out = capsys.readouterr().out
    assert "unexpected error" in out.lower() and "OPENAI" not in out


def test_the_main_menu_lists_client_history_and_quit_as_zero():
    shown = []
    ConsoleUI(read=_answers("0"), write=shown.append).show_app_menu()
    assert any(line.startswith("8. Client History") for line in shown)
    assert "0. Quit" in shown
    assert not any(line.startswith("8. Quit") for line in shown)


@pytest.mark.parametrize("choice", ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
def test_every_menu_choice_is_accepted(choice):
    assert ConsoleUI(read=_answers(choice), write=lambda text: None).show_app_menu() == choice


def test_a_menu_choice_outside_the_allowed_set_is_refused_with_the_allowed_ones():
    shown = []
    ask = _answers("10", "-1", "", "x", "08", " 3 ")
    assert ConsoleUI(read=ask, write=shown.append).show_app_menu() == "3"
    assert [line for line in shown if line.startswith("Invalid choice")] == \
        ["Invalid choice. Please enter a number from 1 to 9, or 0 to quit."] * 5


def test_ask_choice_can_name_its_back_option():
    shown = []
    ui = ConsoleUI(read=_answers("0"), write=shown.append)
    assert ui.ask_choice("Which?", ["a", "b"], allow_back=True, back_label="Back to the client") is None
    assert "  0. Back to the client" in shown


def test_ask_optional_text_allows_a_blank_answer():
    ui = ConsoleUI(read=_answers("  ", " 2026-11-01 "), write=lambda text: None)
    assert ui.ask_optional_text("From") == ""
    assert ui.ask_optional_text("From") == "2026-11-01"


def test_the_main_menu_offers_the_admin_screens_as_nine():
    shown = []
    ConsoleUI(read=_answers("0"), write=shown.append).show_app_menu()
    assert "9. Admin: audit and flags" in shown


def test_ask_password_uses_the_secret_reader_and_never_shows_the_answer():
    shown, asked = [], []

    def secret(question: str) -> str:
        asked.append(question)
        return " s3cret pass "

    ui = ConsoleUI(read=_answers(), write=shown.append, secret=secret)
    assert ui.ask_password("Password") == " s3cret pass "          # exactly as typed
    assert asked == ["Password: "]
    assert shown == []                                              # nothing is echoed back


def test_ask_password_does_not_use_the_plain_reader(capsys):
    def plain(question: str) -> str:
        raise AssertionError("a password must not be read with the plain reader")

    ConsoleUI(read=plain, secret=lambda question: "x").ask_password("Password")
    assert capsys.readouterr().out == ""


def test_the_secret_reader_defaults_to_getpass(monkeypatch):
    import getpass
    asked = []
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": asked.append(prompt) or "hidden")
    assert ConsoleUI().ask_password("Password") == "hidden"
    assert asked == ["Password: "]


def test_a_secret_reader_that_cannot_be_called_is_refused():
    with pytest.raises(ValueError):
        ConsoleUI(secret="not a function")


def test_printable_replaces_control_and_format_characters_and_joins_the_lines():
    assert ConsoleUI.printable(["a\x1b[31mb", "c\x07", "d\u202ee"]) == "a?[31mb\nc?\nd?e"
    assert ConsoleUI.printable(["one\ntwo\r"]) == "one?two?"          # a break inside a value is not a new line
    assert ConsoleUI.printable([]) == ""


def test_printable_turns_a_tab_and_a_no_break_space_into_a_space():
    assert ConsoleUI.printable(["a\tb\u00a0c"]) == "a b c"


def test_printable_keeps_ordinary_text_in_other_scripts_and_symbols():
    assert ConsoleUI.printable(["Zoë 李 — →"]) == "Zoë 李 — →"
