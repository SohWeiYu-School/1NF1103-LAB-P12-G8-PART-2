"""ConsoleUI: everything typed into or printed on the terminal."""

import datetime
import os
from typing import Callable

try:                                  # the file and folder pickers need a desktop; servers have none
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = filedialog = None

class ConsoleUI:
    """The terminal. Every print() and input() of the command line app is in this class,
    so no other class talks to the terminal directly: they ask the ConsoleUI to show
    something or to ask a question.

    Each ask_ method keeps asking until the answer is valid, and tells the officer what
    was wrong. Each keep_ method offers the current value and keeps it on a blank answer.
    """

    LINE = "-" * 72
    LETTERS = " '.-"                    # allowed besides letters: names, nationality, countries
    LABEL   = " '.-&/,()%#0123456789"     # job titles, industries, employers, asset descriptions
    MAX_EMPLOYEES = 10_000_000

    def __init__(self, read: Callable[[str], str] | None = None,
                 write: Callable[[str], None] | None = None) -> None:
        """read asks one question and returns the answer typed; write shows one line. Both
        default to the terminal (input and print). They are looked up when used, not here, so a
        test that replaces builtins.input still answers an App's ConsoleUI."""
        if read is not None and not callable(read):
            raise ValueError("read must be a function that asks a question and returns the answer")
        if write is not None and not callable(write):
            raise ValueError("write must be a function that shows a line of text")
        self.__read: Callable[[str], str] = read if read is not None else (lambda question: input(question))
        self.__write: Callable[[str], None] = write if write is not None else (lambda text: print(text))
        self.__width: int = len(ConsoleUI.LINE)

    def show_app_menu(self) -> str:
        """Display the unified main menu and return the user's choice (1-8)."""
        self.__write("\n========================================")
        self.__write("     SOURCE OF WEALTH SCREENING SYSTEM")
        self.__write("========================================")
        self.__write("1. New Client (type in, then the combined assessment)")
        self.__write("2. New Client from Documents (auto-fill from a folder of documents)")
        self.__write("3. Find / Edit Existing Client")
        self.__write("4. Assess an Existing Client (crime scan + forecast + benchmark -> one verdict)")
        self.__write("5. List Saved Assessments")
        self.__write("6. View All Clients")
        self.__write("7. Manual Sync to Cloud Database")
        self.__write("8. Quit")
        while True:
            choice = self.__read("\nEnter your choice (1-8): ").strip()
            if choice in ("1", "2", "3", "4", "5", "6", "7", "8"):
                return choice
            self.__write("Invalid choice. Please enter 1 to 8.")

    def show_message(self, text: str) -> None:
        #Print an informational message.
        self.__write(text)

    def show_error(self, text: str) -> None:
        #Print an error message.
        self.__write(f"[ERROR] {text}")

    def show_ai_unavailable(self, feature: str = "Assessment") -> None:
        self.__write(f"{feature} is not available right now — please try again later.")

    def show_unexpected_error(self) -> None:
        self.__write("An unexpected error occurred — please try again or contact support.")

    def show_rate_limit_error(self, seconds_left: int) -> None:
        self.__write(f"[RATE LIMIT] Assessment already running or recently completed.")
        self.__write(f"             Please wait {seconds_left} second{'s' if seconds_left != 1 else ''} before starting another assessment.")

    def show_sync_result(self, stats: dict) -> None:
        cases = stats.get("cases_synced", 0)
        assessments = stats.get("assessments_synced", 0)
        skipped = stats.get("skipped", 0)
        errors = stats.get("errors", [])
        synced = cases + assessments

        if not errors:
            self.__write(f"\nSync complete — {cases} case(s) and {assessments} assessment(s) pushed to cloud.")
            if skipped:
                self.__write(f"               {skipped} record(s) already up to date — skipped.")
        elif synced > 0:
            self.__write(f"\nPartial sync — {cases} case(s) and {assessments} assessment(s) pushed to cloud.")
            if skipped:
                self.__write(f"               {skipped} record(s) already up to date — skipped.")
            self.__write("Some records could not be synced — please try again later or contact your administrator.")
        else:
            self.__write("\nSync unsuccessful — please try again later or contact your administrator.")

    def show_step(self, number: int, total: int, label: str) -> None:
        """One progress line of the combined assessment (the web app shows the same steps)."""
        self.__write(f"  [{number:>2}/{total}] {label}...")

    def display_section(self, title: str):
        """Print a formatted section heading."""

        self.__write("\n" + "=" * 60)
        self.__write(title)
        self.__write("=" * 60)

    def show_client_list(self, records: list) -> None:
        """Print a compact table of all saved clients."""
        if not records:
            self.__write("\n  No clients saved yet.\n")
            return
        W = 68
        self.__write("\n" + "─" * W)
        self.__write(f"  {'#':<4}{'Reference':<18}{'Name':<28}Industry")
        self.__write("─" * W)
        for i, r in enumerate(records, start=1):
            ref      = r.get("client_ref", "—")
            name     = r.get("name") or r.get("client_profile", {}).get("full_name", "—")
            industry = r.get("career", {}).get("industry") or r.get("client_profile", {}).get("industry", "—")
            self.__write(f"  {i:<4}{ref:<18}{name:<28}{industry}")
        self.__write("─" * W + "\n")

    def ask_document_folder(self) -> str | None:
        """Ask which folder holds the client's documents. Returns the folder path, or None to cancel."""
        self.__write("\n" + "=" * 60)
        self.__write("              NEW CLIENT FROM DOCUMENTS")
        self.__write("=" * 60)
        self.__write("Put the client's documents in one folder (CV, payslips, employment letter, tax notices,")
        self.__write("bank statements, property papers, KYC form). PDF, Word, Excel, text and images are read.")
        if tk is not None and self.ask_yes_no("\nChoose the folder in a file explorer window?"):
            root = tk.Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select the folder with the client's documents")
            root.destroy()
            if folder:
                self.__write(f"Folder: {folder}")
                return folder
            self.__write("No folder was chosen.")
        folder = self.__read("\nFolder path (or press Enter to go back to the menu): ").strip()
        folder = folder.strip('"').strip("'")          # paths dragged into the terminal come quoted
        return folder or None

    def show_documents_found(self, paths: list[str]) -> None:
        self.__write(f"\nFound {len(paths)} document(s):")
        for path in paths:
            self.__write(f"  - {os.path.basename(path)}")

    def show_missing_intro(self, count: int) -> None:
        if count:
            self.__write(f"\n{count} required detail(s) weren't in the documents. Please fill them in:")
        else:
            self.__write("\nEvery required detail was found in the documents.")

    def ask_document_record_action(self) -> str:
        """After the summary: 'save', 'edit' or 'discard'."""
        options = ["Save this client", "Edit something first", "Discard (nothing is saved)"]
        return ["save", "edit", "discard"][self.ask_choice("\nIs everything correct?", options)]

    def show(self, text: str = "") -> None:
        self.__write(text)

    def money(self, value: float | None) -> str:
        return "n/a" if value is None else f"{value:,.0f}"

    def money_range(self, values: dict) -> str:
        return f"{self.money(values['cautious'])} to {self.money(values['optimistic'])} (typical {self.money(values['typical'])})"

    def read_answer(self, question: str) -> str:
        """Ask one question and return what was typed (the terminal unless a read function was handed in)."""
        return self.__read(question)

    def ask_text(self, question: str, min_length: int = 1) -> str:
        while True:
            answer = self.read_answer(f"{question}: ").strip()
            if len(answer) >= min_length:
                return answer
            self.show_error(f"Please enter at least {min_length} character(s).")

    def ask_int(self, question: str, minimum: int | None = None, maximum: int | None = None,
                allow_blank: bool = False) -> int | None:
        while True:
            answer = self.read_answer(f"{question}: ").strip()
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

    def ask_money(self, question: str, allow_zero: bool = True) -> float:
        while True:
            answer = self.read_answer(f"{question}: ").strip().replace(",", "")
            try:
                amount = float(answer)
            except ValueError:
                self.show_error("Please enter an amount, e.g. 1500000.")
                continue
            if amount < 0 or (amount == 0 and not allow_zero):
                self.show_error("Please enter an amount above zero." if not allow_zero else "Amounts can't be negative.")
                continue
            return amount

    def ask_choice(self, question: str, options: list[str], allow_back: bool = False) -> int | None:
        """Show a numbered list and return the index picked. With allow_back, 0 returns None."""
        self.show(question)
        for number, option in enumerate(options, start=1):
            self.show(f"  {number}. {option}")
        if allow_back:
            self.show("  0. Back to the main menu")
        number = self.ask_int("Choose a number", 0 if allow_back else 1, len(options))
        return None if number == 0 else number - 1

    def ask_yes_no(self, question: str) -> bool:
        while True:
            answer = self.read_answer(f"{question} (y/n): ").strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.show_error("Please answer y or n.")

    def ask_year(self, question: str, minimum: int = 1940, maximum: int | None = None,
                 allow_blank: bool = False) -> int | None:
        maximum = maximum or datetime.date.today().year
        return self.ask_int(question, minimum, maximum, allow_blank)

    def ask_currency(self) -> str:
        while True:
            code = self.read_answer("Currency (3-letter code, e.g. SGD): ").strip().upper()
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
                    v = self.__read(f"{label} (%) [{shown}]: ").strip().replace(",", "")
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
            v = self.__read(f"{label} [{current}]: ").strip()
            if not v:
                return current
            if len(v) >= min_length:
                return v
            self.show_error(f"Enter at least {min_length} characters, or press Enter to keep.")

    def keep_int(self, label: str, current, minimum: int, maximum: int):
        while True:
            v = self.__read(f"{label} [{current}]: ").strip()
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

    def keep_money(self, label: str, current: float | None) -> float | None:
        """Enter keeps the current amount; None means there is no amount yet (and stays None)."""
        while True:
            v = self.__read(f"{label} [{current}]: ").strip().replace(",", "")
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

    def __only(self, text: str, allowed: str) -> bool:
        """Must contain at least one letter, and nothing outside letters + the allowed characters."""
        return any(c.isalpha() for c in text) and all(c.isalpha() or c in allowed for c in text)

    def _words_error(self, allowed: str) -> str:
        if allowed == ConsoleUI.LETTERS:
            return "Letters only please (spaces, - ' . are fine). No numbers."
        return "Please enter a proper description. It must contain letters and can't be only numbers."

    def ask_words(self, question: str, allowed: str = LETTERS, min_length: int = 2) -> str:
        while True:
            answer = self.__read(f"{question}: ").strip()
            if len(answer) >= min_length and self.__only(answer, allowed):
                return answer
            self.show_error(self._words_error(allowed))

    def keep_words(self, label: str, current, allowed: str = LETTERS, min_length: int = 2) -> str:
        while True:
            v = self.__read(f"{label} [{current}]: ").strip()
            if not v:
                return current
            if len(v) >= min_length and self.__only(v, allowed):
                return v
            self.show_error(self._words_error(allowed))

    def ask_countries(self, question: str) -> list:
        while True:
            items = [c.strip() for c in self.ask_text(question).split(",") if c.strip()]
            if items and all(self.__only(c, ConsoleUI.LETTERS) for c in items):
                return items
            self.show_error("Enter country names separated by commas, letters only (no numbers).")

    def keep_countries(self, label: str, current: list[str]) -> list[str]:
        """Countries separated by commas, letters only. Enter keeps the current list; an answer
        that isn't a list of country names is refused once (with the reason) and the current
        list is kept, so the officer is not stuck in the question."""
        v = self.__read(f"{label} [{', '.join(current)}]: ").strip()
        if not v:
            return current
        items = [c.strip() for c in v.split(",") if c.strip()]
        if items and all(self.__only(c, ConsoleUI.LETTERS) for c in items):
            return items
        self.show_error("Not changed. Countries must be letters only, separated by commas.")
        return current

    def __parse_count(self, text: str) -> int | None:
        """'2,500' -> 2500. Returns None for ranges, text, zero or absurdly large numbers."""
        cleaned = text.strip().replace(",", "")
        if cleaned.isdigit() and 1 <= int(cleaned) <= ConsoleUI.MAX_EMPLOYEES:
            return int(cleaned)
        return None

    def ask_count(self, question: str) -> int:
        while True:
            number = self.__parse_count(self.read_answer(f"{question}: "))
            if number is not None:
                return number
            self.show_error("Please enter the number of employees as a single whole number, e.g. 2500 "
                       "(no ranges or text).")

    def keep_count(self, label: str, current):
        while True:
            v = self.__read(f"{label} [{current}]: ").strip()
            if not v:
                return current
            number = self.__parse_count(v)
            if number is not None:
                return number
            self.show_error("Please enter a single whole number, e.g. 2500, or press Enter to keep.")

    def show_case_problems(self, where: str, problems: list[str]) -> None:
        self.show_error(f"{where} can't be assessed yet:")
        for problem in problems:
            self.show(f"    - {problem}")
        self.show("  Fix the client record (Find / Edit Existing Client) and try again.")

    def ask_client_ref(self) -> str | None:
        ref = self.ask_text("Client reference (e.g. CL-1A2B3C4D, 0 to go back)")
        return None if ref == "0" else ref

    def show_ai_progress(self, results: dict) -> None:
        """One line per AI request: where the reply came from and whether it passed the checks."""
        for name, result in results.items():
            source = "saved reply" if result["from_cache"] else f"API, {result['attempts']} attempt(s)"
            status = "ok" if result["ok"] else "FAILED"
            self.show(f"  {name:<40} {source:<20} {status}")

    def read_number(self, text: object) -> float | None:
        """Read an amount typed in the form: '1,650,000', 'S$1.65m', '2.5 million', '410k'. None if unreadable."""
        if isinstance(text, (int, float)):
            return float(text)
        cleaned = str(text or "").strip().lower().replace(",", "").replace(" ", "")
        for prefix in ("sgd", "s$", "$"):
            cleaned = cleaned.removeprefix(prefix)
        multiplier = 1.0
        for suffix, factor in (("million", 1e6), ("mil", 1e6), ("m", 1e6), ("k", 1e3), ("%", 1.0)):
            if cleaned.endswith(suffix):
                cleaned, multiplier = cleaned[: -len(suffix)], factor
                break
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None

    def read_year(self, text: object) -> int | None:
        value = self.read_number(text)
        return int(value) if value is not None and 1900 <= value <= 2100 else None
