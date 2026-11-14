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
    assert ConsoleUI().ask_yes_no("Save this client?", ask) is True
    assert len(ask.asked) == 3
    assert capsys.readouterr().out.count("[ERROR] Please answer y or n.") == 2


def test_ask_int_rejects_text_and_numbers_out_of_range(capsys):
    ask = _answers("abc", "200", "51")
    assert ConsoleUI().ask_int("Age", ask, 18, 120) == 51
    assert capsys.readouterr().out.count("[ERROR]") == 2


def test_ask_int_may_be_left_blank_only_when_allowed():
    assert ConsoleUI().ask_int("End year", _answers(""), 1940, 2026, allow_blank=True) is None
    assert ConsoleUI().ask_int("Age", _answers("", "30"), 18, 120) == 30


def test_ask_money_accepts_commas_and_rejects_negatives(capsys):
    assert ConsoleUI().ask_money("Price paid", _answers("a lot", "-5", "1,650,000")) == 1650000.0
    out = capsys.readouterr().out
    assert "Please enter an amount, e.g. 1500000." in out
    assert "Amounts can't be negative." in out


def test_ask_money_can_refuse_zero():
    assert ConsoleUI().ask_money("Net worth", _answers("0", "5"), allow_zero=False) == 5.0


def test_ask_text_needs_a_minimum_length():
    assert ConsoleUI().ask_text("Declaration", _answers("  ", "short", "long enough"), min_length=6) == "long enough"


def test_ask_choice_returns_the_position_picked(capsys):
    ui = ConsoleUI()
    assert ui.ask_choice("Payment method", ["cash", "loan", "asset_sale"], _answers("9", "2")) == 1
    out = capsys.readouterr().out
    assert "  1. cash" in out and "  3. asset_sale" in out


def test_ask_choice_with_back_returns_none_for_zero():
    assert ConsoleUI().ask_choice("Menu", ["a", "b"], _answers("0"), allow_back=True) is None


def test_keep_text_keeps_the_current_value_on_a_blank_answer(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda question: "")
    assert ConsoleUI().keep_text("Name", "Daniel Tan") == "Daniel Tan"


def test_keep_text_takes_a_new_value(monkeypatch):
    typed = iter(["x", "Daniel Tan Wei Ming"])
    monkeypatch.setattr("builtins.input", lambda question: next(typed))
    assert ConsoleUI().keep_text("Name", "Daniel Tan") == "Daniel Tan Wei Ming"


def test_with_no_ask_function_the_terminal_is_used(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda question: "y")
    assert ConsoleUI().ask_yes_no("Continue?") is True


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
