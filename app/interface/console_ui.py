"""ConsoleUI: everything typed into or printed on the terminal."""

import datetime
import os
from typing import Callable

try:                                  # the file and folder pickers need a desktop; servers have none
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = filedialog = None

Ask = Callable[[str], str]


class ConsoleUI:
    """The terminal. Every print() and input() of the command line app is in this class,
    so no other class talks to the terminal directly: they ask the ConsoleUI to show
    something or to ask a question.

    Each ask_ method keeps asking until the answer is valid, and tells the officer what
    was wrong. Each keep_ method offers the current value and keeps it on a blank answer.
    """

    LINE = "-" * 72
    LETTERS = " '.-"                    # allowed besides letters: names, nationality, countries
    MAX_EMPLOYEES = 10_000_000

    def __init__(self) -> None:
        self.__width: int = len(ConsoleUI.LINE)

    def show_app_menu(self) -> str:
        """Display the unified main menu and return the user's choice (1-8)."""
        print("\n========================================")
        print("     SOURCE OF WEALTH SCREENING SYSTEM")
        print("========================================")
        print("1. New Client (type in, then the combined assessment)")
        print("2. New Client from Documents (auto-fill from a folder of documents)")
        print("3. Find / Edit Existing Client")
        print("4. Assess an Existing Client (crime scan + forecast + benchmark -> one verdict)")
        print("5. List Saved Assessments")
        print("6. View All Clients")
        print("7. Manual Sync to Cloud Database")
        print("8. Quit")
        while True:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ("1", "2", "3", "4", "5", "6", "7", "8"):
                return choice
            print("Invalid choice. Please enter 1 to 8.")

    def show_message(self, text: str) -> None:
        #Print an informational message.
        print(text)

    def show_error(self, text: str) -> None:
        #Print an error message.
        print(f"[ERROR] {text}")

    def show_ai_unavailable(self, feature: str = "Assessment") -> None:
        print(f"{feature} is not available right now — please try again later.")

    def show_unexpected_error(self) -> None:
        print("An unexpected error occurred — please try again or contact support.")

    def show_rate_limit_error(self, seconds_left: int) -> None:
        print(f"[RATE LIMIT] Assessment already running or recently completed.")
        print(f"             Please wait {seconds_left} second{'s' if seconds_left != 1 else ''} before starting another assessment.")

    def show_sync_result(self, stats: dict) -> None:
        cases = stats.get("cases_synced", 0)
        assessments = stats.get("assessments_synced", 0)
        skipped = stats.get("skipped", 0)
        errors = stats.get("errors", [])
        synced = cases + assessments

        if not errors:
            print(f"\nSync complete — {cases} case(s) and {assessments} assessment(s) pushed to cloud.")
            if skipped:
                print(f"               {skipped} record(s) already up to date — skipped.")
        elif synced > 0:
            print(f"\nPartial sync — {cases} case(s) and {assessments} assessment(s) pushed to cloud.")
            if skipped:
                print(f"               {skipped} record(s) already up to date — skipped.")
            print("Some records could not be synced — please try again later or contact your administrator.")
        else:
            print("\nSync unsuccessful — please try again later or contact your administrator.")

    def show_step(self, number: int, total: int, label: str) -> None:
        """One progress line of the combined assessment (the web app shows the same steps)."""
        print(f"  [{number:>2}/{total}] {label}...")

    def display_section(self, title: str):
        """Print a formatted section heading."""

        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)

    def show_client_list(self, records: list) -> None:
        """Print a compact table of all saved clients."""
        if not records:
            print("\n  No clients saved yet.\n")
            return
        W = 68
        print("\n" + "─" * W)
        print(f"  {'#':<4}{'Reference':<18}{'Name':<28}Industry")
        print("─" * W)
        for i, r in enumerate(records, start=1):
            ref      = r.get("client_ref", "—")
            name     = r.get("name") or r.get("client_profile", {}).get("full_name", "—")
            industry = r.get("career", {}).get("industry") or r.get("client_profile", {}).get("industry", "—")
            print(f"  {i:<4}{ref:<18}{name:<28}{industry}")
        print("─" * W + "\n")

    def ask_document_folder(self) -> str | None:
        """Ask which folder holds the client's documents. Returns the folder path, or None to cancel."""
        print("\n" + "=" * 60)
        print("              NEW CLIENT FROM DOCUMENTS")
        print("=" * 60)
        print("Put the client's documents in one folder (CV, payslips, employment letter, tax notices,")
        print("bank statements, property papers, KYC form). PDF, Word, Excel, text and images are read.")
        if tk is not None and self.ask_yes_no("\nChoose the folder in a file explorer window?"):
            root = tk.Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select the folder with the client's documents")
            root.destroy()
            if folder:
                print(f"Folder: {folder}")
                return folder
            print("No folder was chosen.")
        folder = input("\nFolder path (or press Enter to go back to the menu): ").strip()
        folder = folder.strip('"').strip("'")          # paths dragged into the terminal come quoted
        return folder or None

    def show_documents_found(self, paths: list[str]) -> None:
        print(f"\nFound {len(paths)} document(s):")
        for path in paths:
            print(f"  - {os.path.basename(path)}")

    def show_missing_intro(self, count: int) -> None:
        if count:
            print(f"\n{count} required detail(s) weren't in the documents. Please fill them in:")
        else:
            print("\nEvery required detail was found in the documents.")

    def ask_document_record_action(self) -> str:
        """After the summary: 'save', 'edit' or 'discard'."""
        options = ["Save this client", "Edit something first", "Discard (nothing is saved)"]
        return ["save", "edit", "discard"][self.ask_choice("\nIs everything correct?", options)]

    def show(self, text: str = "") -> None:
        print(text)

    def money(self, value: float | None) -> str:
        return "n/a" if value is None else f"{value:,.0f}"

    def money_range(self, values: dict) -> str:
        return f"{self.money(values['cautious'])} to {self.money(values['optimistic'])} (typical {self.money(values['typical'])})"

    def read_answer(self, question: str) -> str:
        """The normal way to ask: type into the terminal."""
        return input(question)

    def ask_text(self, question: str, ask: Ask | None = None, min_length: int = 1) -> str:
        ask = ask or self.read_answer
        while True:
            answer = ask(f"{question}: ").strip()
            if len(answer) >= min_length:
                return answer
            self.show_error(f"Please enter at least {min_length} character(s).")

    def ask_int(self, question: str, ask: Ask | None = None, minimum: int | None = None,
                maximum: int | None = None, allow_blank: bool = False) -> int | None:
        ask = ask or self.read_answer
        while True:
            answer = ask(f"{question}: ").strip()
            if allow_blank and answer == "":
                return None
            try:
                number = int(answer)
            except ValueError:
                self.show_error("Please enter a whole number.")
                continue
            if minimum is not None and number < minimum:
                self.show_error(f"Please enter {minimum} or more.")
            elif maximum is not None and number > maximum:
                self.show_error(f"Please enter {maximum} or less.")
            else:
                return number

    def ask_money(self, question: str, ask: Ask | None = None, allow_zero: bool = True) -> float:
        ask = ask or self.read_answer
        while True:
            answer = ask(f"{question}: ").strip().replace(",", "")
            try:
                amount = float(answer)
            except ValueError:
                self.show_error("Please enter an amount, e.g. 1500000.")
                continue
            if amount < 0 or (amount == 0 and not allow_zero):
                self.show_error("Please enter an amount above zero." if not allow_zero else "Amounts can't be negative.")
                continue
            return amount

    def ask_choice(self, question: str, options: list[str], ask: Ask | None = None, allow_back: bool = False) -> int | None:
        """Show a numbered list and return the index picked. With allow_back, 0 returns None."""
        ask = ask or self.read_answer
        self.show(question)
        for number, option in enumerate(options, start=1):
            self.show(f"  {number}. {option}")
        if allow_back:
            self.show("  0. Back to the main menu")
        number = self.ask_int("Choose a number", ask, 0 if allow_back else 1, len(options))
        return None if number == 0 else number - 1

    def ask_yes_no(self, question: str, ask: Ask | None = None) -> bool:
        ask = ask or self.read_answer
        while True:
            answer = ask(f"{question} (y/n): ").strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.show_error("Please answer y or n.")

    def ask_year(self, question: str, minimum: int = 1940, maximum: int | None = None,
                 allow_blank: bool = False) -> int | None:
        maximum = maximum or datetime.date.today().year
        return self.ask_int(question, self.read_answer, minimum, maximum, allow_blank)

    def ask_currency(self, ask: Ask | None = None) -> str:
        ask = ask or self.read_answer
        while True:
            code = ask("Currency (3-letter code, e.g. SGD): ").strip().upper()
            if len(code) == 3 and code.isalpha():
                return code
            self.show_error("Please enter a 3-letter currency code like SGD or USD.")

    def ask_composition(self, current: dict | None = None) -> dict:
        """Four percentages that must add up to 100. Enter keeps the current value when editing."""
        labels = [("property", "Property"), ("listed_equities", "Listed Equities"),
                  ("private_business", "Private Business"), ("cash", "Cash")]
        while True:
            split = {}
            for key, label in labels:
                if current is None:
                    split[key] = self.ask_money(f"{label} (%)") / 100
                else:
                    shown = f"{current.get(key, 0) * 100:.0f}"
                    v = input(f"{label} (%) [{shown}]: ").strip().replace(",", "")
                    try:
                        split[key] = float(v) / 100 if v else current.get(key, 0.0)
                    except ValueError:
                        self.show_error("Please enter a number, or press Enter to keep.")
                        split = None
                        break
                    if split[key] < 0:
                        self.show_error("Percentages can't be negative.")
                        split = None
                        break
            if split is None:
                continue
            total = sum(split.values())
            if abs(total - 1.0) <= 0.005:
                return split
            self.show_error(f"That adds up to {total:.1%}. It must be 100%. Please re-enter.")

    def keep_text(self, label: str, current, min_length: int = 2) -> str:
        while True:
            v = input(f"{label} [{current}]: ").strip()
            if not v:
                return current
            if len(v) >= min_length:
                return v
            self.show_error(f"Enter at least {min_length} characters, or press Enter to keep.")

    def keep_int(self, label: str, current, minimum: int, maximum: int):
        while True:
            v = input(f"{label} [{current}]: ").strip()
            if not v:
                return current
            try:
                n = int(v)
            except ValueError:
                self.show_error("Please enter a whole number, or press Enter to keep.")
                continue
            if minimum <= n <= maximum:
                return n
            self.show_error(f"Please enter a value between {minimum} and {maximum}.")

    def keep_money(self, label: str, current):
        while True:
            v = input(f"{label} [{current}]: ").strip().replace(",", "")
            if not v:
                return current
            try:
                n = float(v)
            except ValueError:
                self.show_error("Please enter an amount like 1500000, or press Enter to keep.")
                continue
            if n >= 0:
                return n
            self.show_error("Amounts can't be negative.")

    def _only(self, text: str, allowed: str) -> bool:
        """Must contain at least one letter, and nothing outside letters + the allowed characters."""
        return any(c.isalpha() for c in text) and all(c.isalpha() or c in allowed for c in text)

    def _words_error(self, allowed: str) -> str:
        if allowed == ConsoleUI.LETTERS:
            return "Letters only please (spaces, - ' . are fine). No numbers."
        return "Please enter a proper description. It must contain letters and can't be only numbers."

    def ask_words(self, question: str, allowed: str = LETTERS, min_length: int = 2) -> str:
        while True:
            answer = input(f"{question}: ").strip()
            if len(answer) >= min_length and self._only(answer, allowed):
                return answer
            self.show_error(self._words_error(allowed))

    def keep_words(self, label: str, current, allowed: str = LETTERS, min_length: int = 2) -> str:
        while True:
            v = input(f"{label} [{current}]: ").strip()
            if not v:
                return current
            if len(v) >= min_length and self._only(v, allowed):
                return v
            self.show_error(self._words_error(allowed))

    def ask_countries(self, question: str) -> list:
        while True:
            items = [c.strip() for c in self.ask_text(question).split(",") if c.strip()]
            if items and all(self._only(c, ConsoleUI.LETTERS) for c in items):
                return items
            self.show_error("Enter country names separated by commas, letters only (no numbers).")

    def _parse_count(self, text: str) -> int | None:
        """'2,500' -> 2500. Returns None for ranges, text, zero or absurdly large numbers."""
        cleaned = text.strip().replace(",", "")
        if cleaned.isdigit() and 1 <= int(cleaned) <= ConsoleUI.MAX_EMPLOYEES:
            return int(cleaned)
        return None

    def ask_count(self, question: str, ask: Ask | None = None) -> int:
        ask = ask or self.read_answer
        while True:
            number = self._parse_count(ask(f"{question}: "))
            if number is not None:
                return number
            self.show_error("Please enter the number of employees as a single whole number, e.g. 2500 "
                       "(no ranges or text).")

    def keep_count(self, label: str, current):
        while True:
            v = input(f"{label} [{current}]: ").strip()
            if not v:
                return current
            number = self._parse_count(v)
            if number is not None:
                return number
            self.show_error("Please enter a single whole number, e.g. 2500, or press Enter to keep.")

    def show_case_problems(self, where: str, problems: list[str]) -> None:
        self.show_error(f"{where} can't be assessed yet:")
        for problem in problems:
            self.show(f"    - {problem}")
        self.show("  Fix the client record (Find / Edit Existing Client) and try again.")

    def ask_client_ref(self, ask: Ask | None = None) -> str | None:
        ask = ask or self.read_answer
        ref = self.ask_text("Client reference (e.g. CL-1A2B3C4D, 0 to go back)", ask)
        return None if ref == "0" else ref

    def show_ai_progress(self, results: dict) -> None:
        """One line per AI request: where the reply came from and whether it passed the checks."""
        for name, result in results.items():
            source = "saved reply" if result["from_cache"] else f"API, {result['attempts']} attempt(s)"
            status = "ok" if result["ok"] else "FAILED"
            self.show(f"  {name:<40} {source:<20} {status}")
