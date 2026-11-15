"""ClientForm: the questions that create and edit a client record."""

import datetime
import logging
import os
import uuid

from app.interface.console_ui import ConsoleUI
from app.interface.report_view import ReportView
from app.model.client_record import ClientRecord

try:                                  # the file pickers need a desktop; servers have none
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = filedialog = None

logger = logging.getLogger(__name__)


class ClientForm:
    """Asks the officer for a new client's details, and lets them find, review and edit a
    saved client. It asks every question through the ConsoleUI and shows records through
    the ReportView; both are handed in.

    It never saves or loads by itself: the caller passes in the functions that do
    (save_fn, find_fn, upload_fn, ...), so this class does not know where records are kept.
    The answers are collected in the saved layout and handed back as a ClientRecord.
    """

    PAYMENT_METHODS = ["cash", "loan", "asset_sale"]

    PEP_OPTIONS: list[str] = ["None", "Domestic PEP", "Foreign PEP", "International organisation PEP",
                              "Family member / close associate of a PEP"]

    def __init__(self, ui: ConsoleUI | None = None, report_view: ReportView | None = None) -> None:
        self.__ui: ConsoleUI = ui or ConsoleUI()
        self.__report_view: ReportView = report_view or ReportView(self.__ui)

    def generate_client_id(self) -> str:
        """Generate a unique client reference ID."""

        return "CL-" + uuid.uuid4().hex[:8].upper()

    def get_client_profile(self) -> dict:
        """Collect name, nationality and current position."""
        self.__ui.show("\n=== Client Profile ===")
        name        = self.__ui.ask_words("Full name")
        nationality = self.__ui.ask_words("Nationality")
        self.__ui.show("\n=== Current Position ===")
        occupation    = self.__ui.ask_words("Current job title", ConsoleUI.LABEL)
        seniority     = self.__ui.ask_words("Seniority (e.g. Senior Manager, C-suite)", ConsoleUI.LABEL)
        industry      = self.__ui.ask_words("Industry", ConsoleUI.LABEL)
        employer_name = self.__ui.ask_words("Employer name", ConsoleUI.LABEL)
        employer_size = self.__ui.ask_count("Employer size (number of employees, e.g. 2500)")
        residence     = self.__ui.ask_words("Country of residence")
        age           = self.__ui.ask_int("Age", minimum=18, maximum=100)
        while True:
            start = self.__ui.ask_year("Year first career started")
            if start >= datetime.date.today().year - age + 14:
                break
            self.__ui.show_error("That would mean the client started working before age 14. Please check the age and year.")
        career = {"occupation": occupation, "seniority": seniority, "industry": industry,
                  "employer_name": employer_name, "employer_size": employer_size,
                  "country_of_residence": residence, "age": age, "career_start_year": start}
        return {"name": name, "nationality": nationality, "career": career}

    def _ask_job(self, previous: bool = False) -> dict:
        """One job. A previous job must have an end year: the current job is asked for in the
        profile, so an open "previous" job would replace it when the record is saved."""
        start_year = self.__ui.ask_year("Start year")
        if previous:
            end_year = self.__ui.ask_year("End year", minimum=start_year)
        else:
            end_year = self.__ui.ask_year("End year (leave blank if current)", minimum=start_year, allow_blank=True)
        return {
            "start_year": start_year, "end_year": end_year,
            "occupation":    self.__ui.ask_words("Job title", ConsoleUI.LABEL),
            "seniority":     self.__ui.ask_words("Seniority", ConsoleUI.LABEL),
            "industry":      self.__ui.ask_words("Industry", ConsoleUI.LABEL),
            "employer_name": self.__ui.ask_words("Employer name", ConsoleUI.LABEL),
            "employer_size": self.__ui.ask_count("Employer size (number of employees)"),
            "country":       self.__ui.ask_words("Country"),
        }

    def get_career_history(self) -> list:
        """Collect previous jobs (before the current one)."""
        career_history = []
        prompt = "\nDoes the client have a previous job to add?"
        while self.__ui.ask_yes_no(prompt):
            self.__ui.show("\n=== Previous Job ===")
            career_history.append(self._ask_job(previous=True))
            prompt = "\nAdd another previous job?"
        return career_history

    def _ask_asset(self) -> dict:
        asset_type  = self.__ui.ask_words("Asset type (e.g. Property, Shares)", ConsoleUI.LABEL)
        description = self.__ui.ask_words("Description", ConsoleUI.LABEL)
        country     = self.__ui.ask_words("Country")
        year_acquired = self.__ui.ask_year("Year acquired")
        price_paid    = self.__ui.ask_money("Price paid", allow_zero=False)
        payment_method = ClientForm.PAYMENT_METHODS[self.__ui.ask_choice("Payment method", ClientForm.PAYMENT_METHODS)]
        year_sold = sale_price = None
        if self.__ui.ask_yes_no("Has this asset been sold?"):
            year_sold  = self.__ui.ask_year("Year sold", minimum=year_acquired)
            sale_price = self.__ui.ask_money("Sale price", allow_zero=True)
        # Same layout as the web form and the documents auto-fill: "Property - Condo", current_declared_value,
        # income_produced. year_sold, sale_price and currency are extra details only this screen asks for.
        return {
            "asset_type": f"{asset_type} - {description}" if description.lower() not in asset_type.lower() else asset_type,
            "country": country,
            "year_acquired": year_acquired, "price_paid": price_paid,
            "payment_method": payment_method, "year_sold": year_sold, "sale_price": sale_price,
            "current_declared_value": self.__ui.ask_money("Current value (0 if sold)", allow_zero=True),
            "income_produced":        self.__ui.ask_money("Yearly income from this asset (0 if none)", allow_zero=True),
            "currency":               self.__ui.ask_currency(),
        }

    def get_investments(self) -> list:
        investments = []
        prompt = "\nDoes the client have any investments or assets?"
        while self.__ui.ask_yes_no(prompt):
            self.__ui.show("\n=== Investment / Asset ===")
            investments.append(self._ask_asset())
            prompt = "\nAdd another investment or asset?"
        return investments

    def get_claims(self) -> dict:
        """Collect financial claims and asset composition."""
        self.__ui.show("\n=== Financial Claims ===")
        declared_net_worth = self.__ui.ask_money("Declared net worth (SGD)", allow_zero=False)
        expected_aum       = self.__ui.ask_money("Expected assets to be managed by the bank (SGD)", allow_zero=False)
        pep_status = ClientForm.PEP_OPTIONS[self.__ui.ask_choice("PEP status", ClientForm.PEP_OPTIONS)]
        wealth_countries = self.__ui.ask_countries("Countries where wealth was generated (comma-separated)")

        self.__ui.show("\n=== Asset Composition ===")
        self.__ui.show("Enter the percentage of total wealth for each category (must add up to 100%).")
        asset_composition = self.__ui.ask_composition()

        self.__ui.show("\n=== Wealth Velocity ===")
        biggest_wealth_jump = wealth_jump_years = None
        if self.__ui.ask_yes_no("Is there a known biggest single-period wealth increase?"):
            biggest_wealth_jump = self.__ui.ask_money("Biggest single-period wealth increase (SGD)", allow_zero=False)
            wealth_jump_years   = self.__ui.ask_int("Over how many years did this increase occur", minimum=1, maximum=60)

        self.__ui.show("\n=== Counterparties ===")
        cp_str = self.__ui.read_answer("Known counterparties, banks/brokers/firms (comma-separated, blank if none): ").strip()
        declared_counterparties = [c.strip() for c in cp_str.split(",") if c.strip()]

        return {
            "declared_net_worth": declared_net_worth, "expected_aum": expected_aum,
            "pep_status": pep_status, "wealth_countries": wealth_countries,
            "asset_composition": asset_composition,
            "biggest_wealth_jump": biggest_wealth_jump, "wealth_jump_years": wealth_jump_years,
            "declared_counterparties": declared_counterparties,
        }

    def get_sow_declaration(self) -> str:
        self.__ui.show("\n=== Source of Wealth Declaration ===")
        return self.__ui.ask_text("Describe how the client accumulated their wealth (min 50 characters)", min_length=50)

    def get_supporting_documents(self, upload_fn=None) -> list:
        """
        Ask whether the client has supporting documents.

        If yes, open a Tkinter file picker and upload
        the selected documents.
        """

        self.__ui.show("\n=== Supporting Documents ===")

        if not self.__ui.ask_yes_no("Does the client have any supporting documents?"):
            return []

        if tk is None:
            self.__ui.show("The file picker isn't available on this computer (tkinter is not installed).")
            return []

        self.__ui.show("\nOpening file explorer...")

        root = tk.Tk()
        root.withdraw()

        file_paths = filedialog.askopenfilenames(
            title="Select Supporting Documents",
            filetypes=[
                ("All supported files", "*.*"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.docx"),
                ("Excel files", "*.xlsx"),
                ("Images", "*.png;*.jpg;*.jpeg")
            ]
        )

        root.destroy()

        if not file_paths:
            self.__ui.show("No documents were selected.")
            return []

        documents = []

        self.__ui.show("\nSaving documents locally...")

        for path in file_paths:

            stored_path = upload_fn(path) if upload_fn else None

            if stored_path is None:
                self.__ui.show(f"ERROR: Could not save {os.path.basename(path)}")
                continue

            documents.append({
                "file_name": os.path.basename(path),
                "file_path": stored_path
            })

            self.__ui.show(f"Saved locally: {os.path.basename(path)}")

        self.__ui.show(f"\n{len(documents)} document(s) saved locally. They upload to the cloud when you run Manual Sync.")

        return documents

    def create_new_client(self, save_fn=None, upload_fn=None) -> ClientRecord | None:
        """Collect, review and optionally save a new client. save_fn is given the ClientRecord.
        Returns the saved record when the officer wants to assess it now, otherwise None."""

        self.__ui.show("\n")
        self.__ui.show("=" * 60)
        self.__ui.show("                    NEW CLIENT")
        self.__ui.show("=" * 60)

        # Generate client reference
        client_ref = self.generate_client_id()

        self.__ui.show(f"\nGenerated Client Reference: {client_ref}")

        # Collect information
        profile_data         = self.get_client_profile()
        career_history       = self.get_career_history()
        investments          = self.get_investments()
        claims               = self.get_claims()
        sow_declaration      = self.get_sow_declaration()
        supporting_documents = self.get_supporting_documents(upload_fn)

        # Create complete record
        answers = {
            "client_ref":          client_ref,
            "name":                profile_data["name"],
            "nationality":         profile_data["nationality"],
            "current_date":        datetime.date.today().isoformat(),
            "career":              profile_data["career"],
            "career_history":      career_history,
            "investments":         investments,
            "claims":              claims,
            "sow_declaration":     sow_declaration,
            "supporting_documents": supporting_documents,
        }
        try:
            client_record = ClientRecord.from_dict(answers)
        except ValueError as error:
            logger.error("ClientForm.create_new_client: the answers for %s are not a valid record: %r",
                         client_ref, error)
            self.__ui.show_error(f"The client could not be created because {error}. Nothing was saved.")
            self.__ui.read_answer("\nPress Enter to return to the main menu...")
            return None

        # Show everything before saving
        self.__report_view.display_client_record(client_record)

        # Ask whether to save
        if self.__ui.ask_yes_no("\nWould you like to save this client locally?"):

            self.__ui.show("\nSaving client locally...")

            success = save_fn(client_record) if save_fn else False

            if success:
                self.__ui.show("\nClient successfully saved!")
                self.__ui.show(f"Client Reference: {client_ref}")

                next_step = self.__ui.ask_choice(
                    "\nWhat would you like to do next?",
                    ["Run the combined assessment now (crime scan, forecast and benchmark -> one verdict)",
                     "Return to the main menu"],
                )
                if next_step == 1:
                    self.__ui.show("\nReturning to the main menu. You can run the assessment later with option 4.")
                    client_record = None   # None tells main.py not to start the assessment

            else:
                self.__ui.show("\nERROR: The client could not be saved to the local file.")
                client_record = None
                self.__ui.read_answer("\nPress Enter to return to the main menu...")

        else:

            self.__ui.show("\nClient was NOT saved.")
            self.__ui.show("The information has been discarded.")
            client_record = None
            self.__ui.read_answer("\nPress Enter to return to the main menu...")

        return client_record

    def ask_missing_field(self, field: dict):
        """Ask for one detail the documents didn't give. field comes from logic_manager.missing_client_fields."""
        label, kind = field["label"], field["kind"]
        if kind == "words":
            return self.__ui.ask_words(label)
        if kind == "label":
            return self.__ui.ask_words(label, ConsoleUI.LABEL)
        if kind == "count":
            return self.__ui.ask_count(label)
        if kind == "text":
            return self.__ui.ask_text(label)
        if kind == "age":
            return self.__ui.ask_int(label, minimum=18, maximum=100)
        if kind == "year":
            return self.__ui.ask_year(label)
        if kind == "money_positive":
            return self.__ui.ask_money(label, allow_zero=False)
        if kind == "money":
            return self.__ui.ask_money(label, allow_zero=True)
        if kind == "payment":
            return ClientForm.PAYMENT_METHODS[self.__ui.ask_choice(label, ClientForm.PAYMENT_METHODS)]
        if kind == "pep":
            return ClientForm.PEP_OPTIONS[self.__ui.ask_choice(label, ClientForm.PEP_OPTIONS)]
        if kind == "countries":
            return self.__ui.ask_countries(label)
        if kind == "composition":
            self.__ui.show(f"\n{label}. Enter the percentage of total wealth for each category.")
            return self.__ui.ask_composition()
        if kind == "sow":
            self.__ui.show("\nThe documents don't contain a usable source of wealth declaration "
                  "(it must be at least 50 characters).")
            return self.__ui.ask_text("Describe how the client accumulated their wealth", min_length=50)
        return self.__ui.ask_text(label)

    def ask_after_save(self, record: ClientRecord) -> bool:
        """After a client is saved: view the saved details, run the assessment, or go back.
        Returns True if the assessment should run now."""
        options = ["View the saved client details",
                   "Run the combined assessment now (documents, crime scan, forecast and benchmark -> one verdict)",
                   "Return to the main menu (you can assess later with option 4)"]
        while True:
            choice = self.__ui.ask_choice("\nWhat would you like to do next?", options)
            if choice == 0:
                self.__report_view.display_client_record(record)
                continue
            return choice == 1

    def edit_client_profile(self, record):
        """Edit name, nationality and current career info."""
        self.__ui.show("\n=== Edit Client Profile ===")
        self.__ui.show("Press Enter to keep the existing value.")
        this_year = datetime.date.today().year

        record["name"]        = self.__ui.keep_words("Full name", record.get("name", ""))
        record["nationality"] = self.__ui.keep_words("Nationality", record.get("nationality", ""))

        career = record.setdefault("career", {})
        for key, label in [("occupation", "Current job title"), ("seniority", "Seniority"),
                           ("industry", "Industry"), ("employer_name", "Employer name")]:
            career[key] = self.__ui.keep_words(label, career.get(key, ""), ConsoleUI.LABEL)
        career["employer_size"]        = self.__ui.keep_count("Employer size (number of employees)", career.get("employer_size", ""))
        career["country_of_residence"] = self.__ui.keep_words("Country of residence", career.get("country_of_residence", ""))
        career["age"] = self.__ui.keep_int("Age", career.get("age", ""), 18, 100)
        career["career_start_year"] = self.__ui.keep_int("Year first career started",
                                               career.get("career_start_year", ""), 1940, this_year)
        # The current job is also listed in career_history (web form, documents): keep the two the same.
        open_jobs = [job for job in record.get("career_history") or [] if job.get("end_year") in (None, "")]
        if open_jobs:
            for key in ClientRecord.CAREER_JOB_KEYS:
                open_jobs[-1][key] = career[key]

        self.__ui.show("\nClient profile updated.")

    def add_career_record(self, record):
        """Add a job to career_history."""
        self.__ui.show("\n=== Add Career Record ===")
        record.setdefault("career_history", []).append(self._ask_job())
        self.__ui.show("\nCareer record added.")

    def edit_career_record(self, record):
        """Edit a job in career_history."""
        careers = record.get("career_history", [])
        if not careers:
            self.__ui.show("\nNo career records found.")
            return
        self.__ui.show("\n=== Career History ===")
        for i, c in enumerate(careers, start=1):
            self.__ui.show(f"{i}. {c.get('occupation','?')} - {c.get('employer_name','?')} "
                  f"({c.get('start_year','?')} - {c.get('end_year','present')})")
        choice = self.__ui.read_answer("\nSelect career record to edit: ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(careers)):
            self.__ui.show("Invalid selection.")
            return
        career = careers[int(choice) - 1]
        self.__ui.show("\nPress Enter to keep the existing value.")
        this_year = datetime.date.today().year
        career["start_year"] = self.__ui.keep_int("Start year", career.get("start_year", ""), 1940, this_year)
        start = self.__ui.read_year(career["start_year"]) or 1940
        while True:
            v = self.__ui.read_answer(f"End year [{career.get('end_year') or 'present'}] (type 'present' for current job): ").strip()
            if not v:
                break
            if v.lower() in ("present", "now"):
                career["end_year"] = None
                break
            if v.isdigit() and start <= int(v) <= this_year:
                career["end_year"] = int(v)
                break
            self.__ui.show_error(f"Enter a year between {start} and {this_year}, 'present', or press Enter to keep.")
        for key, label in [("occupation", "Job title"), ("seniority", "Seniority"),
                           ("industry", "Industry"), ("employer_name", "Employer name")]:
            career[key] = self.__ui.keep_words(label, career.get(key, ""), ConsoleUI.LABEL)
        career["employer_size"] = self.__ui.keep_count("Employer size (number of employees)", career.get("employer_size", ""))
        career["country"]       = self.__ui.keep_words("Country", career.get("country", ""))
        self.__ui.show("\nCareer record updated.")

    def add_asset_record(self, record):
        """Add an entry to investments."""
        self.__ui.show("\n=== Add Investment / Asset ===")
        record.setdefault("investments", []).append(self._ask_asset())
        self.__ui.show("\nAsset added.")

    def edit_asset_record(self, record):
        """Edit an entry in investments."""
        assets = record.get("investments", [])
        if not assets:
            self.__ui.show("\nNo investment records found.")
            return
        self.__ui.show("\n=== Investments ===")
        for i, a in enumerate(assets, start=1):
            self.__ui.show(f"{i}. {a.get('asset_type') or '?'}")
        choice = self.__ui.read_answer("\nSelect asset to edit: ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(assets)):
            self.__ui.show("Invalid selection.")
            return
        asset = assets[int(choice) - 1]
        self.__ui.show("\nPress Enter to keep the existing value.")
        this_year = datetime.date.today().year
        asset["asset_type"]        = self.__ui.keep_words("Asset (e.g. Property - Condo)", asset.get("asset_type", ""), ConsoleUI.LABEL)
        asset["country"]           = self.__ui.keep_words("Country", asset.get("country", ""))
        asset["year_acquired"] = self.__ui.keep_int("Year acquired", asset.get("year_acquired", ""), 1940, this_year)
        asset["price_paid"]    = self.__ui.keep_money("Price paid", asset.get("price_paid"))
        while True:
            v = self.__ui.read_answer(f"Payment method {ClientForm.PAYMENT_METHODS} [{asset.get('payment_method', '')}]: ").strip().lower()
            if not v:
                break
            if v in ClientForm.PAYMENT_METHODS:
                asset["payment_method"] = v
                break
            self.__ui.show_error(f"Please type one of: {', '.join(ClientForm.PAYMENT_METHODS)}.")
        bought = self.__ui.read_year(asset.get("year_acquired")) or 1940
        while True:
            v = self.__ui.read_answer(f"Year sold [{asset.get('year_sold') or 'not sold'}] (type 'none' if still owned): ").strip().lower()
            if not v:
                break
            if v == "none":
                asset["year_sold"] = None
                asset["sale_price"] = None
                break
            if v.isdigit() and bought <= int(v) <= this_year:
                asset["year_sold"] = int(v)
                asset["sale_price"] = self.__ui.keep_money("Sale price", asset.get("sale_price") or 0)
                break
            self.__ui.show_error(f"Enter a year between {bought} and {this_year}, 'none', or press Enter to keep.")
        asset["current_declared_value"] = self.__ui.keep_money("Current value", asset.get("current_declared_value"))
        asset["income_produced"]        = self.__ui.keep_money("Yearly income", asset.get("income_produced"))
        while True:
            v = self.__ui.read_answer(f"Currency [{asset.get('currency', '')}]: ").strip().upper()
            if not v:
                break
            if len(v) == 3 and v.isalpha():
                asset["currency"] = v
                break
            self.__ui.show_error("Please enter a 3-letter currency code like SGD.")
        self.__ui.show("\nAsset updated.")

    def edit_asset_composition(self, record):
        """Edit asset composition inside claims."""
        self.__ui.show("\n=== Edit Asset Composition ===")
        composition = record.setdefault("claims", {}).setdefault("asset_composition", {})
        self.__ui.show("Press Enter to keep a value. Percentages must add up to 100%.")
        record["claims"]["asset_composition"] = self.__ui.ask_composition(current=composition)
        self.__ui.show("\nAsset composition updated.")

    def edit_client_declarations(self, record):
        """Edit claims fields."""
        self.__ui.show("\n=== Edit Financial Claims ===")
        claims = record.setdefault("claims", {})
        self.__ui.show("Press Enter to keep the existing value.")

        claims["declared_net_worth"] = self.__ui.keep_money("Declared net worth (SGD)", claims.get("declared_net_worth"))
        claims["expected_aum"]       = self.__ui.keep_money("Expected AUM (SGD)", claims.get("expected_aum"))

        self.__ui.show(f"PEP status [{claims.get('pep_status', '')}]")
        if self.__ui.ask_yes_no("Change PEP status?"):
            claims["pep_status"] = ClientForm.PEP_OPTIONS[self.__ui.ask_choice("PEP status", ClientForm.PEP_OPTIONS)]

        current = claims.get("wealth_countries", [])
        countries = self.__ui.keep_countries("Wealth countries", current)
        if countries is not current:          # only a valid new list is written back
            claims["wealth_countries"] = countries

        self.__ui.show("\nClaims updated.")

    def edit_sow_declaration(self, record):
        """Edit the Source of Wealth declaration string."""
        self.__ui.show("\n=== Edit Source of Wealth Declaration ===")
        current = record.get("sow_declaration", "")
        self.__ui.show(f"Current: {current}")
        v = self.__ui.keep_text("New declaration text (min 50 characters, Enter to keep)", "", min_length=50)
        if v: record["sow_declaration"] = v
        self.__ui.show("\nDeclaration updated.")

    def add_supporting_documents(self, record, upload_fn=None):
        """Add supporting documents to an existing client."""

        new_documents = self.get_supporting_documents(upload_fn)

        if not new_documents:
            return

        if "supporting_documents" not in record:
            record["supporting_documents"] = []

        record["supporting_documents"].extend(new_documents)

        self.__ui.show(
            f"\n{len(new_documents)} document(s) added."
        )

    def edit_existing_client(self, client: ClientRecord, upload_fn=None) -> ClientRecord:
        """Allow the user to edit or add information to an existing client. Returns the edited
        record as a new ClientRecord. If the changes do not make a valid record, it says why and
        returns the SAME object it was given, unchanged, so the caller knows not to save."""

        record = client.to_dict()     # the answers are edited in the saved layout, then checked as a whole

        while True:

            self.__ui.show("\n========================================")
            self.__ui.show("       EDIT / ADD CLIENT INFORMATION")
            self.__ui.show("========================================")

            self.__ui.show("\n1. Client Profile")
            self.__ui.show("2. Career History")
            self.__ui.show("3. Asset History")
            self.__ui.show("4. Asset Composition")
            self.__ui.show("5. Client Declarations")
            self.__ui.show("6. Source of Wealth Declaration")
            self.__ui.show("7. Supporting Documents")
            self.__ui.show("8. Finish Editing")

            choice = self.__ui.read_answer(
                "\nWhat would you like to edit or add? "
            ).strip()

            if choice == "1":

                self.edit_client_profile(record)

            elif choice == "2":

                self.__ui.show("\n1. Edit existing career")
                self.__ui.show("2. Add new career")

                career_choice = self.__ui.read_answer(
                    "\nChoose an option: "
                ).strip()

                if career_choice == "1":
                    self.edit_career_record(record)

                elif career_choice == "2":
                    self.add_career_record(record)

                else:
                    self.__ui.show("Invalid choice.")

            elif choice == "3":

                self.__ui.show("\n1. Edit existing asset")
                self.__ui.show("2. Add new asset")

                asset_choice = self.__ui.read_answer(
                    "\nChoose an option: "
                ).strip()

                if asset_choice == "1":
                    self.edit_asset_record(record)

                elif asset_choice == "2":
                    self.add_asset_record(record)

                else:
                    self.__ui.show("Invalid choice.")

            elif choice == "4":

                self.edit_asset_composition(record)

            elif choice == "5":

                self.edit_client_declarations(record)

            elif choice == "6":

                self.edit_sow_declaration(record)

            elif choice == "7":

                self.add_supporting_documents(record, upload_fn)

            elif choice == "8":

                self.__ui.show("\nFinished editing.")
                break

            else:

                self.__ui.show("\nInvalid choice.")

            if not self.__ui.ask_yes_no("Make another change?"):
                break

        try:
            return ClientRecord.from_dict(record)
        except ValueError as error:
            logger.error("ClientForm.edit_existing_client: the edited record %s is not valid: %r",
                         client.client_ref, error)
            self.__ui.show_error(f"The changes could not be kept because {error}. The record is unchanged.")
            return client

    def find_existing_client(self, find_fn=None, load_fn=None, save_fn=None, download_fn=None, upload_fn=None):
        """Find, display, edit and manage an existing client from local records.
        find_fn gives a ClientRecord or None (and raises ValueError if the saved record cannot be
        read); save_fn is given the edited ClientRecord."""

        self.__ui.show("\n=== Existing Client ===")

        client_ref = self.__ui.read_answer(
            "Enter client reference (0 to go back): "
        ).strip()

        if client_ref == "0":
            return

        self.__ui.show("\nSearching saved clients...")

        try:
            client_record = find_fn(client_ref) if find_fn else None
        except ValueError as error:      # the client exists, but the saved record cannot be read
            self.__ui.show_error(str(error))
            self.__ui.read_answer("\nPress Enter to return to the main menu...")
            return

        if client_record is None:
            self.__ui.show(f"\nNo client found with reference: {client_ref}")
            self.__ui.read_answer("\nPress Enter to return to the main menu...")
            return

        self.__ui.show("\nClient found!")

        # -------------------------------------------------
        # Initial display
        # -------------------------------------------------

        try:
            self.__report_view.display_client_record(client_record)
        except Exception as e:
            self.__ui.show("\n[ERROR] Could not display client record. Please check the data and try again.")
            self.__ui.read_answer("\nPress Enter to return to the main menu...")
            return

        # -------------------------------------------------
        # Existing Client Options
        # -------------------------------------------------

        while True:

            self.__ui.show("\n========================================")
            self.__ui.show("       CLIENT RECORD OPTIONS")
            self.__ui.show("========================================")
            self.__ui.show("1. Edit or Add Information")
            self.__ui.show("2. Download Supporting Document")
            self.__ui.show("3. Finish")

            choice = self.__ui.read_answer(
                "\nEnter your choice (1-3): "
            ).strip()

            # ---------------------------------------------
            # EDIT / ADD
            # ---------------------------------------------

            if choice == "1":

                edited = self.edit_existing_client(client_record, upload_fn)

                if edited is client_record:
                    # The changes did not make a valid record: edit_existing_client has said why.
                    self.__ui.show("\nNothing was saved.")
                else:
                    client_record = edited
                    self.__ui.show("\nSaving changes locally...")

                    success = save_fn(client_record) if save_fn else False

                    if success:
                        self.__ui.show(
                            "\nChanges saved successfully."
                        )
                    else:
                        self.__ui.show(
                            "\nERROR: Changes could not be saved."
                        )

                self.__ui.show("\n=== UPDATED CLIENT RECORD ===")

                self.__report_view.display_client_record(client_record)

            # ---------------------------------------------
            # DOWNLOAD DOCUMENT
            # ---------------------------------------------

            elif choice == "2":

                documents = client_record.documents()

                if not documents:
                    self.__ui.show(
                        "\nNo supporting documents found."
                    )
                    continue

                while True:

                    self.__ui.show("\n=== Supporting Documents ===")

                    for index, document in enumerate(
                        documents,
                        start=1
                    ):
                        self.__ui.show(
                            f"{index}. "
                            f"{document.get('file_name', 'Unknown file')}"
                        )

                    self.__ui.show("0. Return")

                    document_choice = self.__ui.read_answer(
                        "\nSelect a document to download: "
                    ).strip()

                    if document_choice == "0":
                        break

                    if not document_choice.isdigit():
                        self.__ui.show("Invalid choice.")
                        continue

                    document_index = int(document_choice) - 1

                    if (
                        document_index < 0
                        or document_index >= len(documents)
                    ):
                        self.__ui.show("Invalid document selection.")
                        continue

                    selected_document = documents[
                        document_index
                    ]

                    file_name = selected_document.get(
                        "file_name",
                        "Unknown file"
                    )

                    file_ref = selected_document.get("file_path")
                    file_id = selected_document.get("file_id")

                    if not file_ref and not file_id:
                        self.__ui.show(
                            "\nThis document does not have "
                            "a file reference."
                        )
                        self.__ui.read_answer(
                            "\nPress Enter to continue..."
                        )
                        continue

                    self.__ui.show(
                        f"\nSelected document: {file_name}"
                    )

                    if tk is None:
                        self.__ui.show("\nThe file picker isn't available on this computer "
                              "(tkinter is not installed).")
                        continue

                    # Create a temporary Tkinter root
                    root = tk.Tk()
                    root.withdraw()

                    output_path = filedialog.asksaveasfilename(
                        title="Save Supporting Document",
                        initialfile=file_name
                    )

                    root.destroy()

                    if not output_path:
                        self.__ui.show("Download cancelled.")
                        continue

                    success = False
                    if download_fn:
                        # Local copy first, then the MongoDB archive
                        success = bool(file_ref and download_fn(file_ref, output_path)) \
                            or bool(file_id and download_fn(file_id, output_path))

                    if success:
                        self.__ui.show(
                            "\nDocument downloaded successfully!"
                        )
                        self.__ui.show(
                            f"Saved to: {output_path}"
                        )
                    else:
                        self.__ui.show(
                            "\nERROR: Could not download document."
                        )

                    self.__ui.read_answer(
                        "\nPress Enter to continue..."
                    )

            # ---------------------------------------------
            # FINISH
            # ---------------------------------------------

            elif choice == "3":

                self.__ui.show(
                    "\nFinished viewing client."
                )

                break

            else:

                self.__ui.show(
                    "\nInvalid choice. "
                    "Please enter 1, 2, or 3."
                )

        self.__ui.read_answer(
            "\nPress Enter to return to the main menu..."
        )
