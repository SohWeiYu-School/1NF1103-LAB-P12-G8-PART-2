"""ReportView: how results and records are laid out for the officer."""

import logging
import os
import textwrap
from datetime import datetime, timezone
from typing import Any

from app.interface.console_ui import ConsoleUI
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.client_record import ClientRecord
from app.model.typology import Typology
from app.model.verdict import Verdict

logger = logging.getLogger(__name__)


class ReportView:
    """Lays out what the officer reads: the verdict report, the evidence behind it, a
    client record, the summary of a record pre-filled from documents and the list of
    past assessments. It only arranges text; the ConsoleUI it is handed does the printing.
    """

    REPORT_WIDTH: int = 96
    _CRIME_SECTION_TITLE: str = "Crime - known patterns for his industry"
    _CRIME_INDICATOR_LABEL: dict[str, str] = {
        "counterparty_unnamed":          "Money from unnamed counterparty",
        "gift_or_inheritance_unnamed":   "Gift or inheritance from unnamed person",
        "source_contradicts_occupation": "Source of wealth contradicts occupation",
        "unvalued_source_present":       "Source with no declared amount",
        "related_party_transaction":     "Related party transaction",
    }
    _CRIME_CATEGORY_LABEL: dict[str, str] = {
        "critical":    "CRITICAL MATCH",
        "high":        "HIGH MATCH",
        "medium":      "MEDIUM MATCH",
        "partial":     "PARTIAL MATCH",
        "weak_signal": "WEAK SIGNAL",
        "no_match":    "NO MATCH",
    }
    FIELD_NAMES: dict[str, str] = {"expected_aum": "Expected AUM", "pep_status": "PEP Status",
                   "current_declared_value": "Current Value (SGD)", "income_produced": "Yearly Income (SGD)"}
    SOURCE_TAGS: dict[str, str] = {"documents": "[DOC]   ", "edited": "[EDITED]", "entered": "[YOU]   ", "blank": "[ -- ]  "}
    # What is added to a list line for an archived assessment (the keys are the archive states).
    ARCHIVE_MARKS: dict[str, str] = {"archived": " (archived)", "unreadable": " (archive state unreadable)"}
    OUTCOME_LABELS: dict[str, str] = {
        "PASSED": "PASSED",
        "MANUAL_REVIEW": "MANUAL REVIEW",
        "RISKY": "RISKY",
        "SERIOUS_RISK": "SERIOUS RISK",
    }

    MIN_WIDTH: int = 20

    def __init__(self, ui: ConsoleUI | None = None, width: int = REPORT_WIDTH) -> None:
        """width is how many characters wide the verdict report and the evidence are laid out."""
        if isinstance(width, bool) or not isinstance(width, int) or width < ReportView.MIN_WIDTH:
            raise ValueError(f"the report width must be a whole number of at least {ReportView.MIN_WIDTH} "
                             f"characters (got {width!r})")
        self.__ui: ConsoleUI = ui or ConsoleUI()
        self.__width: int = width

    def __format_crime_section(self, crime: dict, typologies: list[Typology]) -> list[str]:
        """Build lines for the structured crime section inside the verdict report. crime is
        CrimeScan.run's result: its match_results are MatchResult objects."""
        width         = self.__width
        typ_lookup    = {t.typology_id: t for t in typologies}
        match_results = crime.get("match_results", [])
        match_count   = crime.get("match_count", 0)
        total         = len(match_results)
        div           = "  " + "\u2500" * (width - 2)

        lines = ["", f"  {ReportView._CRIME_SECTION_TITLE.upper()}", div,
                 f"  {total} typologies  \u00b7  {match_count} matched  \u00b7  {total - match_count} no match"]

        for mr in match_results:
            typ_id    = mr.typology.typology_id
            name      = mr.typology.name
            category  = mr.category
            label     = ReportView._CRIME_CATEGORY_LABEL.get(category, category.upper())
            typ_data  = typ_lookup.get(typ_id)
            core_inds  = mr.typology.core_indicators()
            core_fired = set(mr.core_fired)
            sup_inds   = mr.typology.supporting_indicators()
            sup_fired  = set(mr.supporting_fired)

            unchecked = "" if mr.typology.verified else "  (not checked against research)"
            lines += ["", f"  [{label}]  {name}{unchecked}"]

            desc = (typ_data.description if typ_data else "").strip()
            if desc:
                lines += textwrap.wrap(desc, width - 4, initial_indent="    ", subsequent_indent="    ")

            if core_inds:
                lines.append("    Core:        " + "  ·  ".join(
                    f"{'✓' if i in core_fired else '—'} {ReportView._CRIME_INDICATOR_LABEL.get(i, i.replace('_', ' '))}"
                    for i in core_inds))
            if sup_inds:
                lines.append("    Supporting:  " + "  ·  ".join(
                    f"{'✓' if i in sup_fired else '—'} {ReportView._CRIME_INDICATOR_LABEL.get(i, i.replace('_', ' '))}"
                    for i in sup_inds))

            quotes = typ_data.source_quotes if typ_data else []
            if quotes and quotes[0].get("quote"):
                q   = quotes[0]
                rid = q.get("report_id", "")
                suffix = f"  [{rid}]" if rid else ""
                lines += textwrap.wrap(f'"{q["quote"]}"{suffix}', width - 6,
                                       initial_indent="    ", subsequent_indent="    ")

        lines.append(div)
        return lines

    @staticmethod
    def __missing_parts(report: object) -> list[str]:
        """The parts of a saved combined report that did not run (the same list the verdict report and the
        assessment list use). A report saved before "incomplete" existed lists them only in its "Could not run"
        section. Only non-empty text counts; a damaged list is logged as a warning and what is usable is kept."""
        if not isinstance(report, dict):
            return []
        head = report.get("header")
        incomplete = head.get("incomplete") if isinstance(head, dict) else None
        if incomplete is None:
            sections = report.get("sections")
            incomplete = [item.get("text") for part in (sections if isinstance(sections, list) else [])
                          if isinstance(part, dict) and part.get("title") == "Could not run"
                          for item in (part["items"] if isinstance(part.get("items"), list) else [])
                          if isinstance(item, dict)]
        missing = [part for part in incomplete if isinstance(part, str) and part.strip()] \
            if isinstance(incomplete, list) else []
        if not isinstance(incomplete, list) or len(missing) < len(incomplete):
            logger.warning("ReportView: the saved report's list of parts that did not run is damaged: %r", incomplete)
        return missing

    def format_verdict_report(self, verdict: Verdict, crime_result: dict | None = None,
                              typologies: list[Typology] | None = None) -> str:
        """The combined assessment as text: the same header, sections and evidence the web app shows
        (the verdict's report)."""
        report = verdict.report
        head = report["header"]
        symbols = {entry["mark"]: entry["symbol"] for entry in report["legend"]}
        rule = "\u2550" * self.__width
        lines = [rule, f"  COMBINED ASSESSMENT  {head['client_ref']}  {head['name']}  ({head['assessed_on']})", rule]
        missing = ReportView.__missing_parts(report)
        if missing:
            lines.append("  ! INCOMPLETE ASSESSMENT")
            lines += textwrap.wrap("Did not run: " + "; ".join(missing) + ".", self.__width - 2,
                                   initial_indent="    ", subsequent_indent="    ")
            lines += textwrap.wrap("This verdict rests only on the parts that ran. A person must check what is "
                                   "missing before relying on it.", self.__width - 2,
                                   initial_indent="    ", subsequent_indent="    ")
            lines.append("")
        lines += [f"  VERDICT:      {head['verdict_label']}",
                  f"  Next step:    {head['next_step']}",
                  f"  Next review:  {head['next_review_date']}",
                  f"  Policy:       {head['policy_version']}", ""]
        lines += textwrap.wrap(head["summary"], self.__width - 2, initial_indent="  ", subsequent_indent="  ")
        lines += ["", "  " + "   ".join(f"{e['symbol']} {e['meaning']}" for e in report["legend"])]

        def section(title: str, items: list[dict]) -> None:
            lines.extend(["", f"  {title.upper()}", "  " + "\u2500" * (self.__width - 2)])
            for item in items:
                lines.extend(textwrap.wrap(item["text"], self.__width - 2,
                                           initial_indent=f"  {symbols[item['mark']]} ", subsequent_indent="    "))
                for sub in item["sub"]:
                    lines.extend(textwrap.wrap(sub, self.__width - 2, initial_indent="      ",
                                               subsequent_indent="      "))

        for part in report["sections"]:
            if crime_result is not None and part["title"] == ReportView._CRIME_SECTION_TITLE:
                lines += self.__format_crime_section(crime_result, typologies or [])
            else:
                section(part["title"], part["items"])
        lines.extend(["", "  FULL EVIDENCE: " + " \u00b7 ".join(report.get("evidence_titles", [])), rule])
        return "\n".join(lines)

    def format_evidence(self, verdict: Verdict) -> str:
        """The full evidence behind the verdict (the web app shows the same sections, collapsed)."""
        report = verdict.report
        rule = "\u2550" * self.__width
        lines = [rule, f"  FULL EVIDENCE  {report['header']['client_ref']}", rule]
        for part in report["evidence"]:
            lines.extend(["", f"  {part['title']}"])
            for line in part["lines"]:
                lines.extend(textwrap.wrap(line, self.__width - 2, initial_indent="    ", subsequent_indent="      "))
        lines.append(rule)
        return "\n".join(lines)

    def show_verdict_report(self, verdict: Verdict, ask_for_evidence: bool = True,
                            crime_result: dict | None = None, typologies: list[Typology] | None = None) -> None:
        """The short report, then (if the officer wants it) the full evidence."""
        # Both texts are built before anything is printed: a damaged report prints nothing at all.
        report = self.format_verdict_report(verdict, crime_result=crime_result, typologies=typologies)
        evidence = self.format_evidence(verdict) if ask_for_evidence else ""
        self.__ui.show("\n" + report + "\n")
        if ask_for_evidence and self.__ui.ask_yes_no("Show the full evidence?"):
            self.__ui.show("\n" + evidence + "\n")

    def _field_name(self, key: str) -> str:
        return ReportView.FIELD_NAMES.get(key, key.replace("_", " ").title())

    def _field_value(self, key: str, value: Any) -> str:
        """A saved value as a person would write it: 6,000,000 not 6000000.0, Singapore not ['Singapore']."""
        if key == "end_year" and value in (None, ""):
            return "present (current job)"
        if value is None or value == "" or value == []:
            return "-"
        if key == "asset_composition" and isinstance(value, dict):
            return ", ".join(f"{k.replace('_', ' ').title()} {float(v or 0) * 100:.0f}%" for k, v in value.items())
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, int) and not key.endswith(("year", "_years", "age")) and key not in ("year_acquired", "year_sold"):
            return f"{value:,}"
        return str(value)

    def __display_section(self, title: str) -> None:
        """Print a formatted section heading."""
        self.__ui.show("\n" + "=" * 60)
        self.__ui.show(title)
        self.__ui.show("=" * 60)

    def show_client_list(self, records: list[dict], activity: dict[str, AuditEvent] | None = None,
                         activity_note: str = "") -> None:
        """Print a compact table of all saved clients. activity (App.last_activity(): client reference in
        lower case -> its newest audit event) adds a "Last activity" column; a client with none shows a dash.
        activity_note, if given, says why the column is missing (the audit log could not be read)."""
        if not records:
            self.__ui.show("\n  No clients saved yet.\n")
            if activity_note:
                self.__ui.show_error(activity_note)
            return
        W = 68 if activity is None else 100
        self.__ui.show("\n" + "─" * W)
        heading = f"  {'#':<4}{'Reference':<18}{'Name':<28}"
        self.__ui.show(heading + ("Industry" if activity is None else f"{'Industry':<20}Last activity"))
        self.__ui.show("─" * W)
        for i, r in enumerate(records, start=1):
            raw_ref  = r.get("client_ref", "—")
            ref      = ReportView.__fit(raw_ref, 18)
            name     = ReportView.__fit(r.get("name") or r.get("client_profile", {}).get("full_name", "—"), 28)
            industry = r.get("career", {}).get("industry") or r.get("client_profile", {}).get("industry", "—")
            if activity is None:
                self.__ui.show(f"  {i:<4}{ref:<18}{name:<28}{industry}")
            else:
                last = ReportView.__last_activity_text(activity.get(str(raw_ref).casefold()))
                self.__ui.show(f"  {i:<4}{ref:<18}{name:<28}{ReportView.__fit(industry, 20):<20}{last}")
        self.__ui.show("─" * W + "\n")
        if activity_note:
            self.__ui.show_error(activity_note)

    @staticmethod
    def __singapore_time(event: AuditEvent) -> datetime:
        """The moment of an audit event as Singapore time (the audit log keeps UTC)."""
        return datetime.strptime(event.at, AuditEvent.TIME_FORMAT).replace(tzinfo=timezone.utc) \
            .astimezone(AuditFilter.SINGAPORE)

    @staticmethod
    def __last_activity_text(event: AuditEvent | None) -> str:
        """"16 Nov 14:02  Client edited" for the newest event of a client; a dash if there is none."""
        if event is None:
            return "—"
        moment = ReportView.__singapore_time(event)
        return f"{moment.day} {moment:%b %H:%M}  {event.label}" + (" (failed)" if event.result == "failed" else "")

    @staticmethod
    def __by_day(events: list[AuditEvent]) -> list[tuple[str, list[AuditEvent]]]:
        """Events (newest first) grouped by Singapore day, each day labelled "15 November 2026"."""
        days: list[tuple[str, list[AuditEvent]]] = []
        for event in events:
            day = AuditFilter.event_day(event)
            label = f"{day.day} {day:%B %Y}"
            if not days or days[-1][0] != label:
                days.append((label, []))
            days[-1][1].append(event)
        return days

    def format_client_history(self, events: list[AuditEvent], total: int | None = None,
                              unreadable: int = 0) -> str:
        """One client's audit trail as text: events (newest first, already filtered) grouped by Singapore
        day, one line each with the time, what happened (a failure is marked in the text) and who did it. total is how many events
        the client has before filtering (default: len(events)), so "No history yet." (none at all) is told
        apart from "No history matches." (the filter hides them all). unreadable is how many rows of the log
        could not be read, so the trail may be incomplete."""
        total = len(events) if total is None else total
        lines: list[str] = []
        if not events:
            lines.append("No history recorded yet." if total == 0
                         else "Nothing matches these filters. Try \"All\" or \"All time\".")
        else:
            lines.append("History (times are Singapore time)")
            for label, day_events in ReportView.__by_day(events):
                lines += ["", f"  {label}"]
                for event in day_events:
                    moment = ReportView.__singapore_time(event)
                    lines.append(ConsoleUI.printable([f"    {moment:%H:%M}  {event.summary()}  |  by {event.actor}"]))
        if unreadable:
            lines += ["", f"{unreadable} {'entry' if unreadable == 1 else 'entries'} in the audit log can't be "
                          "read, so this history may be incomplete."]
        return "\n".join(lines)

    def show_client_history(self, events: list[AuditEvent], total: int | None = None, unreadable: int = 0) -> None:
        """Show format_client_history on the console."""
        self.__ui.show("\n" + self.format_client_history(events, total, unreadable) + "\n")

    def display_client_record(self, record: ClientRecord) -> None:
        """Display all information collected for the client."""

        self.__display_section("CLIENT INFORMATION REVIEW")

        self.__ui.show(f"Client Reference: {record.client_ref}")

        # Things to fix: shown, never a reason to refuse the save (the officer can complete them later)
        problems = record.problems()
        if problems:
            self.__display_section("TO FIX")
            for problem in problems:
                self.__ui.show(f"  - {problem}")

        # -------------------------------------------------
        # Client Profile
        # -------------------------------------------------

        self.__display_section("CLIENT PROFILE")
        self.__ui.show(f"Name:        {record.profile.name or '—'}")
        self.__ui.show(f"Nationality: {record.profile.nationality or '—'}")

        # -------------------------------------------------
        # Career History
        # -------------------------------------------------

        self.__display_section("CAREER HISTORY")

        for index, career in enumerate([job.to_dict() for job in record.jobs()], start=1):
            self.__ui.show(f"\n--- Job {index} ---")
            for key, value in career.items():
                self.__ui.show(f"{self._field_name(key)}: {self._field_value(key, value)}")

        # -------------------------------------------------
        # Investments
        # -------------------------------------------------

        investments = [asset.to_dict() for asset in record.investments()]
        if investments:
            self.__display_section("INVESTMENTS")
            for index, inv in enumerate(investments, start=1):
                self.__ui.show(f"\n--- Investment {index} ---")
                for key, value in inv.items():
                    if key == "asset_description" and value == inv.get("asset_type"):
                        continue   # filled from documents: same as the asset type
                    self.__ui.show(f"{self._field_name(key)}: {self._field_value(key, value)}")

        # -------------------------------------------------
        # Claims
        # -------------------------------------------------

        claims = record.claims.to_dict() if record.claims is not None else {}
        if claims:
            self.__display_section("CLAIMS")
            for key, value in claims.items():
                self.__ui.show(f"{self._field_name(key)}: {self._field_value(key, value)}")

        # -------------------------------------------------
        # Source of Wealth Declaration
        # -------------------------------------------------

        sow = record.sow_declaration
        if sow:
            self.__display_section("SOURCE OF WEALTH DECLARATION")
            self.__ui.show(sow)

        # -------------------------------------------------
        # Supporting Documents
        # -------------------------------------------------

        self.__display_section("SUPPORTING DOCUMENTS")

        documents = record.documents()

        if not documents:
            self.__ui.show("No supporting documents provided.")
        else:
            for index, document in enumerate(documents, start=1):

                self.__ui.show(f"{index}. {document.get('file_name', 'Unknown file')}")
                if document.get("file_id"):
                    self.__ui.show(f"   File ID: {document['file_id']}")

                elif document.get("file_path"):
                    self.__ui.show(
                        f"   File Path: {document['file_path']}"
                    )

                else:
                    self.__ui.show("   No document reference found.")

    def _summary_value(self, row: dict) -> str:
        value, kind = row["value"], row["kind"]
        if value is None or value == "" or value == []:
            return "(blank)"
        if kind == "composition" and isinstance(value, dict):
            return ", ".join(f"{key.replace('_', ' ')} {float(value.get(key) or 0) * 100:.0f}%"
                             for key in ("property", "listed_equities", "private_business", "cash"))
        if kind in ("money", "money_positive") and isinstance(value, (int, float)):
            return f"{value:,.0f}"
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        text = str(value)
        return text if len(text) <= 90 else textwrap.shorten(text, 90, placeholder=" ...")

    def show_document_summary(self, rows: list[dict], files: list[str], notes: list[str], checks: list[str]) -> None:
        """The check-before-saving summary: every field, its value, and where it came from."""
        self.__ui.show("\n" + "=" * 72)
        self.__ui.show("  SUMMARY - please check every value against the documents")
        self.__ui.show("=" * 72)
        self.__ui.show("  [DOC] read from the documents   [YOU] typed by you   [EDITED] changed by you   [ -- ] blank")
        section = group = None
        for row in rows:
            if row["section"] != section:
                section, group = row["section"], None
                self.__ui.show(f"\n  {section.upper()}")
            if row["group"] and row["group"] != group:
                group = row["group"]
                self.__ui.show(f"   {group}")
            indent = "    " if row["group"] else ""
            self.__ui.show(f"  {ReportView.SOURCE_TAGS[row['source']]} {indent}{row['label']}: {self._summary_value(row)}")
        sow = next((row["value"] for row in rows if row["kind"] == "sow" and row["value"]), None)
        if sow and len(str(sow)) > 90:
            self.__ui.show("\n  Full source of wealth declaration:")
            for line in textwrap.wrap(str(sow), 68):
                self.__ui.show(f"    {line}")
        counts = {tag: sum(1 for r in rows if r["source"] == tag) for tag in ReportView.SOURCE_TAGS}
        self.__ui.show(f"\n  {counts['documents']} from documents, {counts['entered']} typed, "
              f"{counts['edited']} changed, {counts['blank']} blank (optional).")
        self.__ui.show(f"  Documents read: {', '.join(os.path.basename(f) for f in files)}")
        if notes:
            self.__ui.show("\n  NOTES FROM READING THE DOCUMENTS")
            for note in notes:
                self.__ui.show(f"   - {note}")
        if checks:
            self.__ui.show("\n  PLEASE DOUBLE-CHECK")
            for check in checks:
                self.__ui.show(f"   ! {check}")
        self.__ui.show("=" * 72)

    def format_onboarding(self, assessment: dict) -> str:
        """A readable onboarding report."""
        lines = [ConsoleUI.LINE, f"ONBOARDING  {assessment['case_ref']}  ({assessment['assessed_on']})", ConsoleUI.LINE,
                 f"Outcome:      {ReportView.OUTCOME_LABELS[assessment['outcome']]}",
                 f"Action:       {assessment['routing']}",
                 f"Next review:  {assessment['next_review_date']}",
                 f"Policy:       {assessment['policy_version']}", "", "Why:"]
        lines += [f"  - {reason}" for reason in assessment["reasons"]]

        lines += ["", "Kinds of person his figures were checked against:"]
        for row in assessment["types"]:
            mark = "fits" if row["fits"] else "does not fit"
            lines.append(f"  {row['type_id']}  {row['name']}  [{mark}, fit {row['fit_score']:.2f}, "
                         f"score {row['score']:.0%}]")
            lines.append(f"      route: {row['route']} ({row['route_years']})")
            if row.get("enabled_by") and row["type_id"] != "T1":
                lines.append(f"      possible through: {row['enabled_by']}")
            lines.append(f"      wealth today: {self.__ui.money_range(row['wealth_now'])}; "
                         f"purchases affordable: {row['purchases_affordable']}")

        lines += ["", "Purchases (honest version):"]
        for row in assessment["affordability"]:
            verdict = "affordable" if row["affordable"] else "NOT affordable"
            lines.append(f"  {row['year']}  asset {row['asset_index']} ({row['payment_method']}): needed "
                         f"{self.__ui.money(row['needed'])}, had up to {self.__ui.money(row['available']['optimistic'])}  -> {verdict}")

        failed = [c for c in assessment["asset_checks"] if c["failed"]]
        if failed:
            lines += ["", "Asset checks that failed:"] + [f"  - {c['detail']}" for c in failed]

        lines += ["", "Documents to request:"]
        lines += [f"  {n}. {d['document']}  ({d['reason']})" for n, d in enumerate(assessment["documents"], 1)] or ["  none"]

        lines += ["", "Watch dates:"]
        lines += [f"  {w['date']}  {w['what']}" for w in assessment["watch_dates"]] or ["  none"]

        quality = assessment["data_quality"]
        lines += ["", f"Data quality: {quality['market_figures']} market figures, "
                      f"{quality['unverified_share']:.0%} from AI memory or missing."]
        return "\n".join(lines)

    def format_assessment_list(self, records: list[dict], states: list[str] | None = None) -> str:
        """One line per assessment. states (one per record, in the same order: "archived" or
        "unreadable") marks the archived ones and the ones whose archive record is damaged; any other
        state, or no states, adds no mark."""
        states = states or []
        if not records:
            return "No saved assessments match."
        lines = [f"{'Client':<16} {'Kind':<20} {'Date':<12} {'Assessment ID':<14} Outcome"]
        for position, record in enumerate(records):
            state = states[position] if position < len(states) else ""
            lines.append(ReportView.format_assessment_row(record, state))
        return "\n".join(lines)

    @staticmethod
    def __fit(value: object, width: int) -> str:
        """value as text that fits a column of this width (one space is left free): a longer one is cut
        and ends with "…"."""
        text = " ".join(str(value).split())
        return text if len(text) < width else text[:width - 2] + "…"

    @staticmethod
    def __text_or_unknown(value: object) -> str:
        """value if it is non-empty text, else "?"."""
        return value if isinstance(value, str) and value.strip() else "?"

    @staticmethod
    def format_assessment_row(record: object, state: str = "", labelled: bool = False) -> str:
        """One line of the assessment list (client, kind, date, the first 8 characters of the assessment id,
        outcome, then the (incomplete) and archive marks; state is "archived", "unreadable" or anything else
        for no mark); the same line is used to pick an assessment. With labelled (a line with no heading
        above it) the id reads "Assessment ID a72de5e5"; a record with no usable id shows "no ID"
        ("Assessment ID: none" when labelled); an id is never made up. A damaged saved record shows "?" for what cannot be read (and is
        logged once); it never stops the list."""
        if not isinstance(record, dict):
            logger.warning("ReportView: a saved assessment is not a record and is shown as '?': %r", record)
            record = {}
        verdict = record.get("verdict")
        assessment = record.get("assessment")
        source, key = (verdict, "verdict") if verdict else (assessment, "outcome")
        if not isinstance(source, dict):
            source = {}
        date, outcome = source.get("assessed_on"), source.get(key)
        unreadable = [name for name, value in (("client_ref", record.get("client_ref")), ("kind", record.get("kind")),
                                               ("date", date)) if not isinstance(value, str)]
        if unreadable or (verdict and not isinstance(verdict, dict)) or (assessment and not verdict
                                                                          and not isinstance(assessment, dict)):
            logger.warning("ReportView: a saved assessment is damaged (%s) and is shown with '?': %r",
                           ", ".join(unreadable) or "verdict", record.get("assessment_id"))
        date_text = date if isinstance(date, str) else "?"
        raw_id = record.get("assessment_id")
        short_id = raw_id.strip()[:8] if isinstance(raw_id, str) else ""
        if labelled:
            id_text = f"{'Assessment ID ' + short_id if short_id else 'Assessment ID: none':<23}"
        else:
            id_text = f"{short_id or 'no ID':<14}"
        incomplete = " (incomplete)" if ReportView.__missing_parts(record.get("report")) else ""
        label = ReportView.OUTCOME_LABELS.get(outcome, "?") if isinstance(outcome, str) else "?"
        return (f"{ReportView.__fit(ReportView.__text_or_unknown(record.get('client_ref')), 16):<16} "
                f"{ReportView.__fit(ReportView.__text_or_unknown(record.get('kind')), 20):<20} {date_text:<12} "
                f"{id_text} {label}{incomplete}{ReportView.ARCHIVE_MARKS.get(state, '')}")

    def show_onboarding(self, assessment: dict) -> None:
        """A forecast-only report (assessments saved before the combined verdict)."""
        W = 68
        text = self.format_onboarding(assessment)        # first, so a damaged record shows nothing at all
        self.__ui.show("\n" + "═" * W)
        self.__ui.show("  FORECASTING — ONBOARDING ASSESSMENT (saved before the combined verdict)")
        self.__ui.show("═" * W)
        self.__ui.show(text)
        self.__ui.show("═" * W + "\n")

    def show_assessment_list(self, records: list[dict], states: list[str] | None = None) -> None:
        self.__ui.show(self.format_assessment_list(records, states))