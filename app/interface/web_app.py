"""WebApp: the browser front end. It only calls App."""

import io
import logging
import os
import secrets
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, send_file, session, url_for)
from jinja2 import DictLoader
from markupsafe import Markup, escape
from werkzeug.datastructures import FileStorage, MultiDict
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
from werkzeug.wrappers import Response

from app.application.app import App
from app.interface.client_form import ClientForm
from app.interface.rate_limiter import RateLimiter
from app.interface.web_templates import TEMPLATES
from app.model.account import Account
from app.model.audit_event import AuditEvent
from app.model.audit_filter import AuditFilter
from app.model.audit_page import AuditPage
from app.model.client_record import ClientRecord
from app.model.flag import Flag
from app.model.flag_ticket import FlagTicket
from app.model.overview_page import OverviewPage
from app.model.trail_filter import TrailFilter
from app.model.typology import Typology

logger = logging.getLogger(__name__)


class WebApp:
    """The web front end: the same clients, the same assessment and the same report as the
    command line, shown in a browser.

    WebApp is the one IO class that talks to App. It never touches the Data, AI or Logic
    managers: every record it shows, saves or assesses goes through the App it is handed.
    Assessments run in a background thread; the loading page polls for the step reached.
    """

    CLIENT_FIELDS: list[tuple[str, str, str]] = [
        ("name", "Full name", "text"),
        ("nationality", "Nationality", "text"),
        ("country_of_residence", "Country of residence", "text"),
        ("age", "Age", "int"),
    ]
    JOB_FIELDS: list[tuple[str, str, str]] = [
        ("start_year", "Start year", "int"),
        ("end_year", "End year (blank for the current job)", "int"),
        ("occupation", "Job title", "text"),
        ("seniority", "Seniority", "text"),
        ("industry", "Industry", "text"),
        ("employer_name", "Employer", "text"),
        ("employer_size", "Employer size (e.g. 10000)", "text"),
        ("country", "Country of the job", "text"),
    ]
    ASSET_FIELDS: list[tuple[str, str, str]] = [
        ("asset_type", "Asset (e.g. Property - Condo)", "text"),
        ("country", "Country", "text"),
        ("year_acquired", "Year bought", "int"),
        ("price_paid", "Price paid (SGD)", "money"),
        ("current_declared_value", "Value the client declares now (SGD)", "money"),
        ("payment_method", "How it was paid for", "payment"),
        ("income_produced", "Income it produces per year (SGD, 0 if none)", "money"),
    ]
    COMPOSITION_FIELDS: list[tuple[str, str, str]] = [
        ("property", "Property (%)", "percent"),
        ("listed_equities", "Listed equities (%)", "percent"),
        ("private_business", "Private business (%)", "percent"),
        ("cash", "Cash (%)", "percent"),
    ]
    CLAIM_FIELDS: list[tuple[str, str, str]] = [
        ("declared_net_worth", "Declared net worth (SGD)", "money"),
        ("expected_aum", "Expected assets to be managed by the bank (SGD)", "money"),
        ("pep_status", "PEP status", "pep"),
        ("wealth_countries", "Countries the wealth came from (comma separated)", "countries"),
        ("biggest_wealth_jump", "Biggest single-period wealth increase in SGD (leave blank if unknown)", "text"),
        ("wealth_jump_years", "Over how many years did this increase occur (leave blank if unknown)", "text"),
        ("declared_counterparties", "Known counterparties — banks, brokers, firms (comma separated, leave blank if none)", "text"),
    ]
    SOW_FIELDS: list[tuple[str, str, str]] = [
        ("sow_declaration", "Declaration (at least 50 characters)", "textarea"),
    ]
    SECTIONS: list[tuple[str, str, list[tuple[str, str, str]], str]] = [
        ("client", "Client", CLIENT_FIELDS, "dict"),
        ("jobs", "Career history (include the current job and leave its end year blank)",
         JOB_FIELDS, "list"),
        ("assets", "Assets the client still owns", ASSET_FIELDS, "list"),
        ("composition", "How the client says their wealth is split (must add up to 100%)",
         COMPOSITION_FIELDS, "dict"),
        ("claims", "Client declarations", CLAIM_FIELDS, "dict"),
        ("sow", "Source of wealth declaration", SOW_FIELDS, "dict"),
    ]

    OFFICER_KEY: str = "officer"           # session keys: one browser can be signed in to both portals
    ADMIN_KEY: str = "admin"
    ADMIN_ENDPOINTS: tuple[str, ...] = ("admin_home", "admin_signin", "admin_signout", "audit_log_view", "audit_verify",
                                        "admin_flag", "admin_clients", "admin_view_client", "admin_view_assessment",
                                        "admin_download_document")
    AUDIT_ENDPOINTS: tuple[str, ...] = ("audit_log_view", "audit_verify", "admin_home", "admin_flag")
    # The officer page an admin page's address is the twin of: the admin portal shows the same page read-only.
    ADMIN_TWINS: dict[str, str] = {"home": "admin_clients", "view_client": "admin_view_client",
                                   "view_assessment": "admin_view_assessment",
                                   "download_document": "admin_download_document"}
    # The demo accounts shown beside the sign-in form (the passwords config/accounts.json is shipped with).
    DEMO_PASSWORDS: dict[str, str] = {"officer": "officer123", "admin": "admin123"}
    # The colour variable (in the page's CSS) of each audit group, for the dots in the log and the timeline.
    GROUP_COLOURS: dict[str, str] = {"Sign-in": "--g-signin", "Client": "--g-client", "Documents": "--g-documents",
                                     "Assessment": "--g-assessment", "System": "--g-system"}
    # "Done by" in an entry's Info, by action ("Done by" if an action is not here).
    DONE_BY: dict[str, str] = {"client_created": "Created by", "client_edited": "Edited by",
                               "assessment_run": "Assessed by", "assessment_failed": "Started by",
                               "document_uploaded": "Uploaded by", "document_downloaded": "Downloaded by",
                               "autofill_used": "Filled in by", "assessment_archived": "Archived by",
                               "assessment_restored": "Restored by", "cloud_sync": "Started by",
                               "audit_verified": "Checked by"}
    SEVERITY_CLASS: dict[str, str] = {"high": "alert", "medium": "warning", "low": "info"}   # the mockup's names for the colours
    SEVERITY_COLOURS: dict[str, str] = {"high": "var(--bad)", "medium": "var(--warn)", "low": "#7b8794"}
    OVERVIEW_RANGES: tuple[tuple[str, str], ...] = (("today", "Today"), ("7", "7 days"), ("30", "30 days"),
                                                    ("90", "90 days"))
    # The fields the flag rules watch, in words (a field that is not here is named from its path).
    FLAG_FIELDS: dict[str, str] = {
        "claims.declared_net_worth": "Declared net worth", "career.annual_income": "Annual income",
        "claims.expected_aum": "Expected AUM", "claims.asset_composition": "Asset composition",
        "claims.pep_status": "PEP status", "sow_declaration": "Source of wealth story"}
    FLAG_FIELDS_SHORT: dict[str, str] = {
        "claims.declared_net_worth": "net worth", "career.annual_income": "income", "claims.expected_aum": "AUM",
        "claims.asset_composition": "asset split", "claims.pep_status": "PEP status",
        "sow_declaration": "SoW story"}
    FAILURE_KINDS: tuple[str, ...] = ("AI step not run", "Save failed", "Read failed", "Sync failed")
    WEEKDAYS: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    SAFE_FLAG_ERRORS: tuple[str, ...] = (App.AUDIT_UNAVAILABLE, App.AUDIT_KEY_MISSING, App.FLAGS_UNAVAILABLE)
    MAX_FORM_TEXT: int = 1000                    # a longer note is cut, then refused by the model as too long
    PROFILE_IN_CAREER: tuple[str, ...] = ("career.age", "career.country_of_residence")   # saved under "career", shown as Client
    SINGAPORE: timezone = timezone(timedelta(hours=8))      # Singapore has no daylight saving: a fixed offset is exact
    NOT_ADMIN: str = "Only the admin can open the audit log."
    MAX_UPLOAD_BYTES: int = 40 * 1024 * 1024     # uploads for auto-fill: 40 MB per request
    ASSESSMENT_STOPPED: str = ("The assessment was stopped because a step it cannot do without failed. "
                               "Please try again later.")
    ASSESSMENT_FAILED: str = "The assessment could not be completed. Please try again later."
    ASSESSMENT_NOT_SAVED: str = ("This assessment was NOT saved, so it is not in the client's history and the "
                                 "client's outcome was not changed. Please try again later.")

    def __init__(self, app: App | None = None, limiter: RateLimiter | None = None) -> None:
        """limiter decides how often one browser may start an assessment. Without one, the App's
        own limiter (made from the policy) is used."""
        if app is not None and not app.settings_ok():
            raise RuntimeError(App.SETTINGS_UNAVAILABLE)
        self.__app: App | None = app
        self.__limiter: RateLimiter | None = limiter if limiter is not None else \
            (app.rate_limiter() if app is not None else None)
        self.__jobs: dict[str, dict] = {}        # job_id -> {status, step_num, step, result, error, client_ref}
        flask = Flask(__name__)
        # Signs the cookie that carries flash messages. Without SECRET_KEY in .env a random key is made
        # at each start (never a fixed one written in the code, which anyone could use to forge it).
        flask.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
        flask.config["MAX_CONTENT_LENGTH"] = WebApp.MAX_UPLOAD_BYTES
        flask.config["SESSION_COOKIE_SAMESITE"] = "Lax"       # the cookie holds only the signed-in email
        flask.jinja_env.loader = DictLoader(TEMPLATES)
        flask.jinja_env.filters["sgt"] = self.singapore_time
        flask.jinja_env.filters["shown"] = self.shown_value
        flask.jinja_env.filters["sgt_day"] = self.singapore_day
        flask.jinja_env.filters["initials"] = self.initials
        flask.jinja_env.filters["sgt_hm"] = self.singapore_clock
        flask.jinja_env.filters["sgt_long"] = self.singapore_long
        flask.jinja_env.filters["field_label"] = self.field_label
        flask.jinja_env.filters["short_fields"] = self.short_fields
        flask.jinja_env.filters["sgt_when"] = self.singapore_when
        flask.jinja_env.filters["sgt_ago"] = self.singapore_ago
        flask.jinja_env.filters["day_when"] = self.day_when
        flask.jinja_env.filters["flag_field"] = self.flag_field
        flask.jinja_env.filters["plain_number"] = self.trim
        flask.jinja_env.globals.update(GROUP_COLOURS=WebApp.GROUP_COLOURS, DONE_BY=WebApp.DONE_BY)
        flask.jinja_env.globals["link"] = self.portal_link
        flask.jinja_env.globals["open_flags"] = self.open_flag_count
        flask.jinja_env.globals.update(PEP_OPTIONS=ClientForm.PEP_OPTIONS, PAYMENT_OPTIONS=ClientForm.PAYMENT_METHODS)
        flask.before_request(self.gate)
        flask.context_processor(lambda: {"account": self.__current(), "portal": self.__portal()})
        flask.add_url_rule('/signin', endpoint='signin', view_func=self.signin, methods=['GET', 'POST'])
        flask.add_url_rule('/signout', endpoint='signout', view_func=self.signout, methods=['POST'])
        flask.add_url_rule('/admin', endpoint='admin_home', view_func=self.admin_home)
        flask.add_url_rule('/admin/signin', endpoint='admin_signin', view_func=self.signin, methods=['GET', 'POST'])
        flask.add_url_rule('/admin/signout', endpoint='admin_signout', view_func=self.signout, methods=['POST'])
        flask.add_url_rule('/admin/flags/<flag_id>', endpoint='admin_flag', view_func=self.admin_flag,
                           methods=['GET', 'POST'])
        flask.add_url_rule('/admin/log', endpoint='audit_log_view', view_func=self.audit_log_view)
        flask.add_url_rule('/admin/log/verify', endpoint='audit_verify', view_func=self.audit_verify, methods=['POST'])
        flask.add_url_rule('/admin/clients', endpoint='admin_clients', view_func=self.home)
        flask.add_url_rule('/admin/clients/<client_ref>', endpoint='admin_view_client', view_func=self.view_client)
        flask.add_url_rule('/admin/clients/<client_ref>/documents/<path:file_id>', endpoint='admin_download_document',
                           view_func=self.download_document)
        flask.add_url_rule('/admin/assessment/<assessment_id>', endpoint='admin_view_assessment',
                           view_func=self.view_assessment)
        flask.add_url_rule('/', endpoint='home', view_func=self.home)
        flask.add_url_rule('/find', endpoint='find', view_func=self.find)
        flask.add_url_rule('/client/new', endpoint='new_client', view_func=self.new_client, methods=['GET', 'POST'])
        flask.add_url_rule('/client/new/autofill', endpoint='new_client_autofill', view_func=self.new_client_autofill, methods=['POST'])
        flask.add_url_rule('/client/<client_ref>', endpoint='view_client', view_func=self.view_client)
        flask.add_url_rule('/assessment/<assessment_id>', endpoint='view_assessment', view_func=self.view_assessment)
        flask.add_url_rule('/client/<client_ref>/edit', endpoint='edit_client', view_func=self.edit_client, methods=['GET', 'POST'])
        flask.add_url_rule('/client/<client_ref>/autofill', endpoint='edit_client_autofill', view_func=self.edit_client_autofill, methods=['POST'])
        flask.add_url_rule('/client/<client_ref>/documents', endpoint='upload_documents', view_func=self.upload_documents, methods=['POST'])
        flask.add_url_rule('/client/<client_ref>/documents/<path:file_id>', endpoint='download_document', view_func=self.download_document)
        flask.add_url_rule('/client/<client_ref>/assess', endpoint='assess_client', view_func=self.assess_client, methods=['POST'])
        flask.add_url_rule('/assess/loading/<job_id>', endpoint='assess_loading', view_func=self.assess_loading)
        flask.add_url_rule('/assess/poll/<job_id>', endpoint='assess_poll', view_func=self.assess_poll)
        flask.add_url_rule('/assess/result/<job_id>', endpoint='assess_result', view_func=self.assess_result)
        flask.add_url_rule('/assessment/<assessment_id>/archive', endpoint='archive_assessment',
                           view_func=self.archive_assessment, methods=['POST'])
        flask.add_url_rule('/assessment/<assessment_id>/restore', endpoint='restore_assessment',
                           view_func=self.restore_assessment, methods=['POST'])
        flask.add_url_rule('/assessments', endpoint='list_assessments_view', view_func=self.list_assessments_view)
        flask.add_url_rule('/sync', endpoint='sync_to_cloud', view_func=self.sync_to_cloud, methods=['POST'])
        flask.register_error_handler(404, self.handle_404)
        flask.register_error_handler(Exception, self.handle_exception)
        self.__flask: Flask = flask
        logging.getLogger("werkzeug").setLevel(logging.WARNING)   # no per-request access logs

    def flask(self) -> Flask:
        """The Flask application (tests use its test client)."""
        return self.__flask

    def start(self, host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
        """Serve the web app until it is stopped."""
        self.__flask.run(host=host, port=port, debug=debug, use_reloader=False)

    def today(self) -> str:
        return self.__app.today()

    # ----- who is signed in ------------------------------------------------------------------

    def __portal(self) -> str:
        """"admin" for an address under /admin, otherwise "officer"."""
        path = request.path
        return App.ADMIN_PORTAL if path == "/admin" or path.startswith("/admin/") else App.OFFICER_PORTAL

    def __session_account(self, key: str) -> Account | None:
        """The account whose email the session holds under key (officer or admin), if it is still a configured
        account of the right role. None if there is none."""
        email = session.get(key)
        if not isinstance(email, str) or self.__app is None:
            return None
        found = self.__app.account(email)
        if found is None or found.is_admin() != (key == WebApp.ADMIN_KEY):
            return None
        return found

    def __current(self) -> Account | None:
        """The signed-in account of the portal this address belongs to (an officer at /, the admin under
        /admin). None if nobody is signed in there."""
        if "account" not in g:
            g.account = self.__session_account(WebApp.ADMIN_KEY if self.__portal() == App.ADMIN_PORTAL
                                               else WebApp.OFFICER_KEY)
        return g.account

    def __actor(self) -> str:
        """The name to record as the actor of a write. Raises ValueError if nobody is signed in
        (the gate stops that before any route runs)."""
        account = self.__current()
        if account is None:
            raise ValueError("Nobody is signed in.")
        return account.name

    def __flash_audit_failure(self, kept: bool = False) -> None:
        """Tell the officer when the last action's audit line could not be written. kept is True when the
        action saved something ("Saved, but ..."); otherwise the message only says the action was not written."""
        if self.__app.audit_write_failed():
            flash(App.AUDIT_NOT_WRITTEN if kept else App.AUDIT_LINE_NOT_WRITTEN)

    def portal_link(self, endpoint: str, **values: Any) -> str:
        """The address of a page for the portal being shown: the admin portal gets the read-only twin of
        the officer pages (client list, client, assessment, document download)."""
        if self.__portal() == App.ADMIN_PORTAL:
            endpoint = WebApp.ADMIN_TWINS.get(endpoint, endpoint)
        return url_for(endpoint, **values)

    def __home(self) -> Response:
        """Go to the client list of the portal being shown."""
        return redirect(self.portal_link("home"))

    def gate(self) -> Any:
        """Runs before every route. Nobody signed in at this portal: go to its sign-in page (the progress poll
        gets a 401). An officer who opens an admin page is refused (403, and the refusal is recorded)."""
        endpoint = request.endpoint
        if endpoint in ("signin", "admin_signin", "static"):
            return None
        if self.__current() is not None:
            return None
        if self.__portal() == App.ADMIN_PORTAL:
            officer = self.__session_account(WebApp.OFFICER_KEY)
            if officer is None:
                return redirect(url_for("admin_signin"))
            if endpoint is None:                # an address or method that does not exist: the 404 or 405 page
                return None
            self.__app.refused(officer.name, "opening the audit log" if endpoint in WebApp.AUDIT_ENDPOINTS
                               else "opening an admin page")
            self.__flash_audit_failure()
            return render_template("forbidden.html", message=WebApp.NOT_ADMIN), 403
        if endpoint == "assess_poll":
            return {"status": "error", "error": "Please sign in again."}, 401
        return redirect(url_for("signin"))

    def open_flag_count(self) -> int | None:
        """The number on the admin header's Overview badge: the flags still to handle. A page that has worked it
        out already leaves it in g; any other admin page asks App once. None when it cannot be worked out (the
        header then shows no badge, never a made-up 0); the reason is logged."""
        if "open_flags" not in g:
            try:
                g.open_flags = self.__app.audit_log(AuditFilter(), datetime.now(timezone.utc)).open_flags
            except ValueError as error:
                logger.error("WebApp.open_flag_count: the header badge cannot be worked out: %s", error)
                g.open_flags = None
        return g.open_flags

    @staticmethod
    def __shown_error(error: ValueError) -> str:
        """The text of an App error that is safe to show; any other ValueError is logged and shown as the
        audit log being unavailable."""
        if str(error) in WebApp.SAFE_FLAG_ERRORS:
            return str(error)
        logger.error("WebApp: an unexpected error while reading the audit log: %r", error)
        return App.AUDIT_UNAVAILABLE

    def __overview_query(self) -> tuple[str, str, int, list[str]]:
        """(range, tab, page, problems) from the web address. A value that is not allowed is replaced by its
        default and explained in problems, so the page still shows."""
        problems: list[str] = []
        preset, tab, page = OverviewPage.DEFAULT_PRESET, OverviewPage.DEFAULT_TAB, 1
        text = request.args.get("range", "").strip().lower()
        if text in OverviewPage.PRESETS:
            preset = text
        elif text:
            problems.append("'range' must be one of today, 7, 30 or 90; showing the last 7 days.")
        text = request.args.get("tab", "").strip().lower()
        if text in OverviewPage.TABS:
            tab = text
        elif text:
            problems.append(f"'tab' must be one of {', '.join(OverviewPage.TABS)}; showing "
                            f"{OverviewPage.TAB_NAMES[OverviewPage.DEFAULT_TAB]}.")
        text = request.args.get("page", "").strip()
        if text.isascii() and text.isdigit() and 1 <= len(text) <= 9 and int(text) >= 1:
            page = int(text)
        elif text:
            problems.append("'page' must be a whole number, 1 or more; showing page 1.")
        return preset, tab, page, problems

    def admin_home(self) -> str:
        """The admin Overview: the numbers, the chart and the flags table. If the log cannot be read it says
        so and shows no numbers (never an empty dashboard for an error)."""
        now = datetime.now(timezone.utc)
        local = now.astimezone(WebApp.SINGAPORE)
        today_long = f"{local:%A}, {local.day} {local:%B %Y}"
        preset, tab, page, problems = self.__overview_query()
        try:
            view = self.__app.audit_overview(preset, tab, page, now)
        except ValueError as error:
            g.open_flags = None
            return render_template("overview.html", error=WebApp.__shown_error(error), today_long=today_long)
        g.open_flags = view.open_flags
        names = self.__client_names([row.flag.client_ref for row in view.rows])
        rows = [{"ticket": ticket, "css": WebApp.SEVERITY_CLASS[ticket.flag.severity],
                 "client": names.get(ticket.flag.client_ref, ""),
                 "detail": self.__row_detail(ticket, view.evidence(ticket.flag.flag_id))} for ticket in view.rows]
        severities = [(key, Flag.SEVERITY_NAMES[key], view.severity_counts[key], WebApp.SEVERITY_COLOURS[key])
                      for key in OverviewPage.SEVERITIES]
        open_in_range = sum(view.severity_counts.values())
        types = [{"kind": kind, "name": name, "count": count, "percent": percent,
                  "priority": Flag.SEVERITY_NAMES[view.type_severity[kind]],
                  "css": WebApp.SEVERITY_CLASS[view.type_severity[kind]]}
                 for kind, name, count, percent in view.flags_by_type]
        return render_template("overview.html", error="", view=view, problems=problems, today_long=today_long,
                               ranges=WebApp.OVERVIEW_RANGES, tabs=list(OverviewPage.TAB_NAMES.items()),
                               chart=self.__failure_chart(view), rows=rows, severities=severities,
                               open_in_range=open_in_range, types=types, page_size=OverviewPage.PAGE_SIZE,
                               shown_total=view.tab_counts[view.tab])

    def __client_names(self, refs: list[str]) -> dict[str, str]:
        """The name of each client reference that has a saved record. A client that cannot be read is left
        out (the page then shows its reference); the first read failure stops the look-ups, as App has
        already logged it."""
        names: dict[str, str] = {}
        for ref in dict.fromkeys(ref for ref in refs if ref):
            try:
                record = self.__app.find_client(ref)
            except ValueError:
                break
            if record is not None and str(record.to_dict().get("name") or "").strip():
                names[ref] = str(record.to_dict()["name"]).strip()
        return names

    @staticmethod
    def __median(values: list[int]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if not ordered:
            return 0
        return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2

    def __failure_chart(self, view: OverviewPage) -> dict:
        """The "Failures over time" chart: one bar per day (per week when the range is over 31 days), the
        sentence under it, and the same numbers for the table (which also stands in when the chart cannot load)."""
        days = view.failures_by_day
        kinds = WebApp.FAILURE_KINDS
        unit, size = ("day", 1) if len(days) <= 31 else ("week", 7)
        chunks = [days[start:start + size] for start in range(0, len(days), size)]

        def short(text: str) -> str:
            day = datetime.strptime(text, "%Y-%m-%d")
            return f"{day.day} {day:%b}"
        labels = [short(chunk[0][0]) for chunk in chunks]
        longs = [short(chunk[0][0]) if len(chunk) == 1 else f"{short(chunk[0][0])}\u2013{short(chunk[-1][0])}"
                 for chunk in chunks]
        data = {kind: [sum(counts.get(kind, 0) for _, counts in chunk) for chunk in chunks] for kind in kinds}
        sums = [sum(data[kind][i] for kind in kinds) for i in range(len(chunks))]
        total = sum(sums)
        if not total:
            caption = "No failures in this range. The AI service and the database answered every time."
        else:
            biggest = max(sums)
            at = sums.index(biggest)
            usual = WebApp.__median([n for i, n in enumerate(sums) if i != at])
            ai = data["AI step not run"][at]
            where = f"on {longs[at]}" if unit == "day" else f"in the week {longs[at]}"
            ai_text = (f"{ai} were AI steps that did not run, so those assessments" if ai > 1
                       else "1 was an AI step that did not run, so that assessment")
            rest = total - biggest
            caption = (f"<b>{biggest} failure{'' if biggest == 1 else 's'} {where}</b> (a usual {unit} has "
                       f"{usual:g}). " + (f"{ai_text} may be missing evidence and should be re-run." if ai
                                          else "None were AI steps.")
                       + (f" {rest} other failure{'' if rest == 1 else 's'} in the rest of the range." if rest
                          else ""))
        return {"unit": unit, "kinds": kinds, "data": data, "sums": sums, "longs": longs, "totals":
                {kind: sum(data[kind]) for kind in kinds}, "caption": Markup(caption),
                "json": {"labels": labels, "longs": longs, "kinds": list(kinds), "data": data}}

    def __badge(self, event: AuditEvent) -> Markup:
        outcome = str(event.details.get("outcome") or "")
        if not outcome:
            return Markup(escape("Assessment saved"))
        return Markup('<span class="badge b-{}">{}</span>').format(outcome, outcome.replace("_", " ").capitalize())

    def __row_detail(self, ticket: FlagTicket, events: list[AuditEvent]) -> Markup:
        """The Detail column of the flags table: a short phrase for the kind, from the entries behind the flag
        (the flag's own headline if they cannot all be read)."""
        flag = ticket.flag
        by_number = {event.sequence: event for event in events}
        found = [by_number[n] for n in flag.sequences if n in by_number]
        if not found or len(found) != len(flag.sequences):
            return Markup(escape(flag.headline))
        if flag.kind == "shop":
            before, edit, after = found
            minutes = round((WebApp.__utc_moment(after.at) - WebApp.__utc_moment(edit.at)).total_seconds() / 60)
            fields = " & ".join(WebApp.FLAG_FIELDS_SHORT.get(str(c.get("field")), self.flag_field(c.get("field")))
                                for c in flag.changes)
            return Markup("{} &rarr; {} {} min after {} edited").format(
                self.__badge(before), self.__badge(after), minutes, fields)
        if flag.kind == "other":
            return Markup("Officer {} edited it; owner officer is {}").format(found[0].actor, flag.owner)
        if flag.kind == "repeat":
            days = max(1, round((WebApp.__utc_moment(found[-1].at) - WebApp.__utc_moment(found[0].at))
                                .total_seconds() / 86400))
            same = len({str(event.details.get("outcome")) for event in found}) == 1
            return Markup("{} runs in {} days, {}").format(len(found), days,
                                                           "same result each time" if same else "results changed")
        if flag.kind == "hours":
            return Markup("{} at {} by officer {}").format(found[0].label, self.singapore_clock(found[0].at),
                                                          found[0].actor)
        return Markup(escape(flag.headline))

    def singapore_when(self, text: str, with_time: bool = True) -> str:
        """An audit time (UTC) as "Fri 13 Nov, 14:05" in Singapore time ("Fri 13 Nov" without the time).
        Anything else is shown as it is."""
        try:
            local = WebApp.__utc_moment(text).astimezone(WebApp.SINGAPORE)
        except (TypeError, ValueError, OverflowError):
            return str(text)
        day = f"{WebApp.WEEKDAYS[local.weekday()]} {local.day} {local:%b}"
        return f"{day}, {local:%H:%M}" if with_time else day

    def day_when(self, text: str) -> str:
        """A day (2026-11-13) as "Fri 13 Nov". Anything else is shown as it is."""
        try:
            day = datetime.strptime(str(text), "%Y-%m-%d")
        except ValueError:
            return str(text)
        return f"{WebApp.WEEKDAYS[day.weekday()]} {day.day} {day:%b}"

    def singapore_ago(self, text: str) -> str:
        """How long ago an audit time was, in Singapore days: "today", "1 day ago", "6 days ago"."""
        try:
            then = WebApp.__utc_moment(text).astimezone(WebApp.SINGAPORE).date()
        except (TypeError, ValueError, OverflowError):
            return ""
        days = (datetime.now(timezone.utc).astimezone(WebApp.SINGAPORE).date() - then).days
        return "today" if days <= 0 else ("1 day ago" if days == 1 else f"{days} days ago")

    def flag_field(self, path: Any) -> str:
        """A changed field's name for the flag pages: "Declared net worth"."""
        return WebApp.FLAG_FIELDS.get(str(path)) or WebApp.field_label(path).split(" \u203a ")[-1]

    def __what_failed(self, event: AuditEvent) -> str:
        """One line for the failure table of a failure-spike flag."""
        details = event.details
        if event.action == "assessment_failed":
            return str(details.get("step") or "An assessment stopped before it finished")
        if event.action == "data_unavailable":
            return event.summary()
        if event.action == "cloud_sync":
            return "The cloud sync failed"
        return "A save failed"

    def __picture(self, ticket: FlagTicket, events: list[AuditEvent], entries: int, client_name: str,
                  history: list[AuditEvent] | None = None) -> dict:
        """Everything the "What happened" picture of a flag needs: the rule in words, the entries behind the
        flag in order (complete is False when some of them cannot be read), and the extras for the kind."""
        flag = ticket.flag
        policy = self.__app.audit_policy
        by_number = {event.sequence: event for event in events}
        ordered = [by_number[n] for n in flag.sequences if n in by_number]
        rules = {
            "shop": f"Verdict moved {policy.jump_levels}+ levels after an edit, within {policy.window_days} days",
            "other": "Client edited by an officer who doesn't own it",
            "repeat": f"More than {policy.repeat_assessments} assessments in {policy.window_days} days",
            "hours": f"Edit or assessment outside {policy.work_start}\u2013{policy.work_end}",
            "spike": f"Failures at least {self.trim(policy.spike_multiplier)}\u00d7 a usual day "
                     f"(and {policy.spike_min}+)",
            "integrity": "Fingerprint chain broken"}
        picture: dict = {"flag": flag, "rule": rules[flag.kind], "client_name": client_name, "ordered": ordered,
                         "complete": len(ordered) == len(flag.sequences), "entries": entries,
                         "created": next((e for e in (history or []) if e.action == "client_created"), None),
                         "rule_hours": f"{policy.work_start} to {policy.work_end}"}
        if flag.kind == "hours" and ordered:
            local = WebApp.__utc_moment(ordered[0].at).astimezone(WebApp.SINGAPORE)
            start, end = policy.work_start_minutes, policy.work_end_minutes
            ticks = [(minutes / 14.4, f"{minutes // 60:02d}:{minutes % 60:02d}")
                     for minutes in (0, start, 720, end, 1440)]
            picture["clock"] = {"work_left": start / 14.4, "work_width": (end - start) / 14.4,
                                "at": (local.hour * 60 + local.minute) / 14.4, "time": f"{local:%H:%M}",
                                "ticks": ticks}
        if flag.kind == "spike":
            counts = {kind: 0 for kind in WebApp.FAILURE_KINDS}
            for event in ordered:
                counts[self.__failure_kind(event)] += 1
            picture["kinds"] = [(kind, count) for kind, count in counts.items() if count]
            picture["what"] = {event.sequence: self.__what_failed(event) for event in ordered}
        return picture

    @staticmethod
    def __failure_kind(event: AuditEvent) -> str:
        if event.action == "assessment_failed":
            return "AI step not run"
        if event.action == "data_unavailable":
            return "Read failed"
        return "Sync failed" if event.action == "cloud_sync" else "Save failed"

    def __flag_log_link(self, flag: Flag, events: list[AuditEvent]) -> str:
        """The activity log narrowed as far as it can be to the entries behind a flag: the days they happened
        on, the client, and "flagged only" (the log cannot pick out one flag's entries)."""
        days = sorted({AuditFilter.event_day(event) for event in events})
        if flag.kind == "spike":
            days = [datetime.strptime(flag.day, "%Y-%m-%d").date()]
        if not days:
            days = [AuditFilter.singapore_day(WebApp.__utc_moment(flag.raised_at))]
        query: dict[str, str] = {"preset": "custom", "from": days[0].isoformat(), "to": days[-1].isoformat()}
        if flag.kind != "integrity":
            query["flagged"] = "1"
        if flag.client_ref:
            query["client_ref"] = flag.client_ref
        return url_for("audit_log_view", **query)

    def __flag_evidence(self, ticket: FlagTicket, events: list[AuditEvent], client_name: str) -> list[dict]:
        """The links under "What happened": the client's history, the log entries behind the flag, and each
        assessment involved."""
        flag = ticket.flag
        links: list[dict] = []
        if flag.client_ref:
            links.append({"href": self.portal_link("view_client", client_ref=flag.client_ref),
                          "text": f"{client_name or flag.client_ref}'s full history", "side": "\u2192"})
        if flag.sequences:
            shown = " ".join(f"#{n}" for n in flag.sequences[:4]) + (" \u2026" if len(flag.sequences) > 4 else "")
            count = len(flag.sequences)
            links.append({"href": self.__flag_log_link(flag, events),
                          "text": f"The {count} log {'entries' if count > 1 else 'entry'} behind this flag",
                          "side": f"{shown} \u2192", "mono": True})
        for event in events:
            if event.action == "assessment_run" and event.details.get("assessment_id"):
                links.append({"href": self.portal_link("view_assessment",
                                                       assessment_id=event.details["assessment_id"]),
                              "text": f"Assessment {event.details['assessment_id']} \u00b7 "
                                      f"{self.singapore_day(event.at)}", "badge": event})
        if flag.kind == "integrity":
            links.append({"href": self.__flag_log_link(flag, events),
                          "text": f"Entries around #{flag.broken_at} in the activity log", "side": "\u2192"})
        return links

    def admin_flag(self, flag_id: str) -> str | Response | tuple[str, int]:
        """One flag as a ticket: what happened, the evidence, the update form and the activity. POST saves an
        update (a new status, or a note) in the audit log."""
        if request.method == "POST":
            return self.__update_flag(flag_id)
        return self.__show_flag(flag_id)

    def __show_flag(self, flag_id: str, draft: dict[str, str] | None = None,
                    errors: list[str] | None = None) -> str | tuple[str, int]:
        """The flag page. draft is what the admin typed in the update form (kept when it is shown again with
        errors). A flag the rules no longer find gives the "no longer exists" panel and a 404."""
        now = datetime.now(timezone.utc)
        draft = draft or {}
        try:
            ticket, events, entries = self.__app.flag_evidence(flag_id, now)
        except ValueError as error:
            g.open_flags = None
            return render_template("flag.html", error=WebApp.__shown_error(error), ticket=None)
        if ticket is None:
            return render_template("flag.html", error="", ticket=None, gone=App.FLAG_GONE), 404
        flag = ticket.flag
        names = self.__client_names([flag.client_ref])
        history = None
        if flag.kind == "other":
            try:
                history = self.__app.audit_trail(flag.client_ref)[0]
            except ValueError:
                history = None                       # only the owner's "created" time is missing from the picture
        picture = self.__picture(ticket, events, entries, names.get(flag.client_ref, ""), history)
        status = draft.get("status") if draft.get("status") in FlagTicket.STATUSES else ticket.status
        return render_template(
            "flag.html", error="", ticket=ticket, pic=picture, history=list(reversed(ticket.history)),
            evidence=self.__flag_evidence(ticket, events, names.get(flag.client_ref, "")),
            sev_css=WebApp.SEVERITY_CLASS[flag.severity], statuses=list(FlagTicket.STATUSES.items()),
            statuses_by_key=FlagTicket.STATUSES, outcomes=list(FlagTicket.OUTCOMES.items()),
            outcomes_by_key=FlagTicket.OUTCOMES, waiting_on_choices=FlagTicket.WAITING_ON, draft_status=status,
            draft_wait=draft.get("waiting_on", ""), draft_outcome=draft.get("outcome", ""),
            draft_note=draft.get("note", ""), errors=errors or [])

    def __update_flag(self, flag_id: str) -> str | Response | tuple[str, int]:
        """Save the update form of a flag. Only text is taken from the form, cut to a sensible length; App
        checks it again. Saved: back to the flag page with the toast. Not valid or not written: the page
        again with what was typed and what is wrong."""
        draft = {name: request.form.get(name, "")[:limit] for name, limit in
                 (("status", 40), ("waiting_on", 80), ("outcome", 40), ("note", WebApp.MAX_FORM_TEXT))}
        try:
            ticket, problems, sequence = self.__app.update_flag(
                flag_id, self.__actor(), draft["status"].strip(), draft["note"], draft["waiting_on"].strip(),
                draft["outcome"].strip(), datetime.now(timezone.utc))
        except ValueError as error:
            g.open_flags = None
            return render_template("flag.html", ticket=None,
                                   error=WebApp.__shown_error(error) + " Your update was not saved.")
        if ticket is None:
            return render_template("flag.html", error="", ticket=None, gone=App.FLAG_GONE), 404
        if problems:
            return self.__show_flag(flag_id, draft, problems)
        if sequence:
            last = ticket.history[-1]
            moved, where = last["from"] != last["to"], f" as entry #{sequence}"
        else:
            moved, where = ticket.status != draft["status"].strip(), ""
        name = FlagTicket.STATUSES[draft["status"].strip()]
        text = (f"{ticket.flag.flag_id} is now {name}" if moved else "Note added") + f". Saved in the audit log{where}."
        flash(text, "toast")
        return redirect(url_for("admin_flag", flag_id=ticket.flag.flag_id))

    def signin(self) -> str | Response:
        """Sign in by name and password at this portal. Anyone already signed in here goes to the portal's front page."""
        admin = self.__portal() == App.ADMIN_PORTAL
        if self.__current() is not None:
            return redirect(url_for("admin_home") if admin else url_for("home"))
        name = ""
        problem = ""
        if request.method == "POST":
            name = request.form.get("name", "")
            signed_in, problem = self.__app.sign_in(name, request.form.get("password", ""), self.__portal())
            if signed_in is not None:
                session[WebApp.ADMIN_KEY if admin else WebApp.OFFICER_KEY] = signed_in.email
                g.account = signed_in
                self.__flash_audit_failure()
                return redirect(url_for("admin_home") if admin else url_for("home"))
            self.__flash_audit_failure()
        demo = [{"name": account.name, "password": WebApp.DEMO_PASSWORDS[account.role]}
                for account in self.__app.accounts() if account.is_admin() == admin]
        return render_template("signin.html", problem=problem, name=name.strip()[:App.MAX_SIGN_IN_TEXT], demo=demo,
                               max_text=App.MAX_SIGN_IN_TEXT)

    def shown_value(self, value: Any) -> str:
        """One value from an audit change as the pages show numbers: thousands separators and no trailing
        .0 on a whole number (16500000 and 9500000.0 show as 16,500,000 and 9,500,000). Text is unchanged;
        nothing (None) is "(empty)"."""
        if value is None:
            return "(empty)"
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value:,}"

    @staticmethod
    def __utc_moment(text: str) -> datetime:
        """A saved time as a UTC moment: an audit time ("2026-11-16T06:02:11Z") or an assessment time with
        its offset ("2026-11-16T06:02:11.123+00:00"). Raises ValueError for anything else, including a
        time with no offset (its zone is unknown, so it is not guessed) and TypeError for a non-text."""
        if not isinstance(text, str):
            raise TypeError("a saved time must be text")
        moment = datetime.fromisoformat(text)
        if moment.tzinfo is None:
            raise ValueError("a saved time must say its offset")
        return moment.astimezone(timezone.utc)

    @staticmethod
    def initials(name: str) -> str:
        """The first letters of the first two words of a name, in capitals ("Wei Yu" -> "WY")."""
        return "".join(word[0] for word in str(name).split()[:2]).upper()

    def singapore_day(self, text: str) -> str:
        """An audit time (UTC) as a Singapore day without the year: "16 Nov". Anything that is not such a
        time is shown as it is."""
        try:
            moment = WebApp.__utc_moment(text)
            local = moment.astimezone(WebApp.SINGAPORE)
        except (TypeError, ValueError, OverflowError):
            return str(text)
        return f"{local.day} {local:%b}"

    def singapore_clock(self, text: str) -> str:
        """An audit time (UTC) as the Singapore clock time: "14:02". Anything else is shown as it is."""
        try:
            moment = WebApp.__utc_moment(text)
            local = moment.astimezone(WebApp.SINGAPORE)
        except (TypeError, ValueError, OverflowError):
            return str(text)
        return f"{local:%H:%M}"

    def singapore_long(self, text: str) -> str:
        """An audit time (UTC) as "15 November 2026, 14:02 SGT". Anything else is shown as it is."""
        try:
            moment = WebApp.__utc_moment(text)
            local = moment.astimezone(WebApp.SINGAPORE)
        except (TypeError, ValueError, OverflowError):
            return str(text)
        return f"{local.day} {local:%B %Y}, {local:%H:%M} SGT"

    @staticmethod
    def field_label(path: Any) -> str:
        """A changed field's path in words: "claims.declared_net_worth" -> "Claims › Declared net worth",
        "investments[0].country" -> "Investments 1 › Country"."""
        parts = []
        if str(path) in WebApp.PROFILE_IN_CAREER:
            path = "client." + str(path).split(".", 1)[1]
        for part in str(path).split("."):
            name, _, index = part.partition("[")
            words = name.replace("_", " ").strip().capitalize()
            parts.append(f"{words} {int(index.rstrip(']')) + 1}" if index.rstrip("]").isdigit() else words)
        return " › ".join(parts)

    def short_fields(self, changes: Any) -> str:
        """The changed fields as one phrase for a log line: "Declared net worth and Annual income", or
        "A, B and 3 more" for many. The last part of each path is used. "" if there are none."""
        names: list[str] = []
        for change in changes if isinstance(changes, list) else []:
            field = change.get("field") if isinstance(change, dict) else None
            label = self.field_label(field).split(" › ")[-1] if isinstance(field, str) and field else ""
            if label and label not in names:
                names.append(label)
        if len(names) > 3:
            return f"{names[0]}, {names[1]} and {len(names) - 2} more"
        return names[0] if len(names) == 1 else (", ".join(names[:-1]) + " and " + names[-1] if names else "")

    def singapore_time(self, text: str) -> str:
        """An audit time (UTC, 2026-11-16T06:02:11Z) as Singapore time: "16 Nov 2026 14:02". Anything
        that is not such a time is shown as it is."""
        try:
            moment = WebApp.__utc_moment(text)
            local = moment.astimezone(WebApp.SINGAPORE)
        except (TypeError, ValueError, OverflowError):
            return str(text)
        return f"{local.day} {local:%b %Y %H:%M}"

    def audit_log_view(self) -> str:
        """The audit log (admin only, the gate checks): filter bar, chips, one page of events."""
        return self.__show_audit_log()

    def __show_audit_log(self, broken_ids: list[str] | None = None) -> str:
        """The audit log page. If the log cannot be read the page says so and shows no table (it never shows
        an empty log for an error). broken_ids are the events a Verify log found changed: their rows are marked."""
        now = datetime.now(timezone.utc)
        audit_filter = AuditFilter.from_query(request.args, now)
        log: AuditPage | None = None
        error = ""
        try:
            log = self.__app.audit_log(audit_filter, now)
        except ValueError:
            error = App.AUDIT_UNAVAILABLE
        g.open_flags = log.open_flags if log is not None else None      # the header badge: no second read
        query = audit_filter.to_query()
        chips = [(text, url_for("audit_log_view", **{k: v for k, v in query.items() if k not in (key, "page")}))
                 for key, text in audit_filter.chips()]
        keep = {k: v for k, v in query.items() if k in ("preset", "from", "to", "sort")}
        officers = [account.name for account in self.__app.accounts()] + [App.TERMINAL, App.UNKNOWN]
        if audit_filter.actor and audit_filter.actor.casefold() not in [name.casefold() for name in officers]:
            officers.append(audit_filter.actor)
        total = log.total if log is not None else 0
        newer = {k: v for k, v in query.items() if k != "page"}
        return render_template("audit.html", log=log, error=error, audit_filter=audit_filter, query=query,
                               chips=chips, clear_url=url_for("audit_log_view", **keep), officers=officers,
                               groups=list(AuditEvent.GROUPS), presets=AuditFilter.PRESETS,
                               range_text=audit_filter.range_text(now), period=audit_filter.period_text(now),
                               today=AuditFilter.singapore_day(now).isoformat(),
                               page=audit_filter.page_for(total), pages=audit_filter.page_count(total),
                               page_size=AuditFilter.PAGE_SIZE, base_query=newer,
                               broken_ids=broken_ids or [])

    def audit_verify(self) -> str | Response:
        """Check the hash chain of the whole log, say what was found, and show the log (the same filters
        as the page it was pressed on) with the changed rows marked."""
        try:
            chain = self.__app.verify_audit_log(self.__actor())
        except ValueError:
            flash(App.AUDIT_UNAVAILABLE)
            return redirect(url_for("audit_log_view"))
        self.__flash_audit_failure()
        flash(chain.summary(), "success" if chain.intact() else "warning")
        return self.__show_audit_log(chain.broken_ids())

    def signout(self) -> Response:
        """Sign out of this portal: the audit log is told, this portal's part of the session is emptied (the
        other portal, if signed in, stays signed in)."""
        admin = self.__portal() == App.ADMIN_PORTAL
        self.__app.sign_out(self.__current())
        session.pop(WebApp.ADMIN_KEY if admin else WebApp.OFFICER_KEY, None)
        g.account = None
        self.__flash_audit_failure()
        return redirect(url_for("admin_signin" if admin else "signin"))

    def trim(self, number: Any) -> str:
        """60000.0 -> '60000', 7.5 -> '7.5'. Anything that isn't a number is shown as it is."""
        try:
            number = round(float(number), 2)
        except (TypeError, ValueError):
            return str(number)
        return str(int(number)) if number == int(number) else str(number)

    def to_text(self, kind: str, value: Any) -> str:
        """How one stored value is shown in a box."""
        if value is None:
            return ""
        if kind == "percent":
            try:
                return self.trim(float(value) * 100)       # 0.25 -> '25'
            except (TypeError, ValueError):
                return str(value)
        if isinstance(value, list):                    # countries, counterparties
            return ", ".join(str(item) for item in value)
        if kind in ("int", "money") or (isinstance(value, (int, float)) and not isinstance(value, bool)):
            return self.trim(value)
        return str(value)

    def values_from_record(self, record: dict) -> dict:
        """The text for every box, taken from a saved record."""
        career = record.get("career") or {}
        claims = record.get("claims") or {}
        raw = {
            "client": {"name": record.get("name"),
                       "nationality": record.get("nationality"),
                       "country_of_residence": career.get("country_of_residence"),
                       "age": career.get("age"),
                       "current_date": record.get("current_date")},
            "jobs": record.get("career_history") or [],
            "assets": record.get("investments") or [],
            "composition": claims.get("asset_composition") or {},
            "claims": claims,
            "sow": {"sow_declaration": record.get("sow_declaration")},
        }
        values = {}
        for prefix, title, fields, kind in WebApp.SECTIONS:
            if kind == "dict":
                values[prefix] = {key: self.to_text(k, raw[prefix].get(key)) for key, label, k in fields}
            else:
                values[prefix] = [{key: self.to_text(k, item.get(key)) for key, label, k in fields}
                                  for item in raw[prefix]]
        return values

    def values_from_form(self, form: MultiDict) -> dict:
        """The text for every box, taken from the submitted form."""
        values = {}
        for prefix, title, fields, kind in WebApp.SECTIONS:
            keys = [field[0] for field in fields]
            if kind == "dict":
                values[prefix] = {key: form.get(f"{prefix}.{key}", "").strip() for key in keys}
            else:
                # every entry repeats the same field names, so getlist gives one column per field
                columns = [form.getlist(f"{prefix}.{key}") for key in keys]
                rows = []
                for cells in zip(*columns):
                    row = {key: cell.strip() for key, cell in zip(keys, cells)}
                    if any(row.values()):               # skip completely empty entries
                        rows.append(row)
                values[prefix] = rows
        return values

    def read_year(self, text: str, label: str, problems: list[str], blank_ok: bool = False) -> int | None:
        if text == "" and blank_ok:
            return None
        if text.isdigit() and 1900 <= int(text) <= 2100:
            return int(text)
        problems.append(f"{label} must be a year such as 2015.")
        return 0

    def read_amount(self, text: str, label: str, problems: list[str], allow_zero: bool = True,
                    blank_zero: bool = False) -> float:
        if text == "" and blank_zero:
            return 0.0
        number = self.__app.read_amount(text)
        if number is None or number < 0 or (number == 0 and not allow_zero):
            wanted = "an amount like 250000" if allow_zero else "an amount above zero, like 250000"
            problems.append(f"{label} must be {wanted}.")
            return 0.0
        return number

    def build_record(self, values: dict, client_ref: str, old: dict | None = None) -> tuple[dict, list[str], dict[str, str]]:
        """Turn the form text into a record. Returns (record, problems, field_errors).

        field_errors maps HTML input name -> short inline message for the form UI.
        For list items the key is  prefix.N.field  (0-based N).
        """
        problems = []
        field_errors = {}

        def _p(msg, field=None, short=None):
            problems.append(msg)
            if field:
                field_errors[field] = short or msg

        record = dict(old) if old else {}
        record["client_ref"] = client_ref
 
        # ---- client ----
        client = values["client"]
        for key, label in [("name", "Full name"), ("nationality", "Nationality"),
                           ("country_of_residence", "Country of residence")]:
            if not client[key]:
                _p(f"{label} is required.", f"client.{key}", "Required.")
        record["name"] = client["name"]
        record["nationality"] = client["nationality"]
 
        # The assessment date is always today - not typed in (the command line does the same).
        record["current_date"] = self.today()
 
        if client["age"].isdigit() and 18 <= int(client["age"]) <= 120:
            age = int(client["age"])
        else:
            _p("Age must be a whole number between 18 and 120.", "client.age", "Must be 18-120.")
            age = 0
 
        # ---- career history ----
        jobs = []
        for number, row in enumerate(values["jobs"], start=1):
            label = f"Job {number}"
            i = number - 1
            for key, text in [("occupation", "job title"), ("seniority", "seniority"),
                              ("industry", "industry"), ("employer_name", "employer"),
                              ("employer_size", "employer size"), ("country", "country")]:
                if not row[key]:
                    _p(f"{label}: {text} is required.", f"jobs.{i}.{key}", "Required.")
            n = len(problems)
            sy = self.read_year(row["start_year"], f"{label}: start year", problems)
            if len(problems) > n:
                field_errors[f"jobs.{i}.start_year"] = "Must be a year like 2015."
            n = len(problems)
            ey = self.read_year(row["end_year"], f"{label}: end year", problems, blank_ok=True)
            if len(problems) > n:
                field_errors[f"jobs.{i}.end_year"] = "Must be a year like 2020."
            jobs.append({
                "start_year": sy,
                "end_year": ey,
                "occupation": row["occupation"],
                "seniority": row["seniority"],
                "industry": row["industry"],
                "employer_name": row["employer_name"],
                "employer_size": row["employer_size"],
                "country": row["country"],
            })
        if not jobs:
            _p("Add at least one job (the current job has no end year).")
        jobs.sort(key=lambda job: job["start_year"])
        record["career_history"] = jobs
 
        # the "career" block is the current job + age + residence (same as the forecasting builds it)
        if jobs:
            current = jobs[-1]
            career = dict(record.get("career") or {})
            career.update({"occupation": current["occupation"], "seniority": current["seniority"],
                           "industry": current["industry"], "employer_name": current["employer_name"],
                           "employer_size": current["employer_size"],
                           "country_of_residence": client["country_of_residence"],
                           "age": age, "career_start_year": jobs[0]["start_year"]})
            record["career"] = career
 
        # ---- assets ----
        investments = []
        for number, row in enumerate(values["assets"], start=1):
            label = f"Asset {number}"
            i = number - 1
            for key, text in [("asset_type", "name"), ("country", "country")]:
                if not row[key]:
                    _p(f"{label}: {text} is required.", f"assets.{i}.{key}", "Required.")
            if row["payment_method"] not in ClientForm.PAYMENT_METHODS:
                _p(f"{label}: choose how it was paid for.", f"assets.{i}.payment_method", "Choose one.")
            n = len(problems)
            yr  = self.read_year(row["year_acquired"], f"{label}: year bought", problems)
            if len(problems) > n:
                field_errors[f"assets.{i}.year_acquired"] = "Must be a year like 2010."
            n = len(problems)
            pp  = self.read_amount(row["price_paid"], f"{label}: price paid", problems, allow_zero=False)
            if len(problems) > n:
                field_errors[f"assets.{i}.price_paid"] = "Must be above zero."
            n = len(problems)
            cdv = self.read_amount(row["current_declared_value"], f"{label}: declared value", problems)
            if len(problems) > n:
                field_errors[f"assets.{i}.current_declared_value"] = "Must be a number."
            n = len(problems)
            inc = self.read_amount(row["income_produced"], f"{label}: income", problems, blank_zero=True)
            if len(problems) > n:
                field_errors[f"assets.{i}.income_produced"] = "Must be a number."
            investments.append({
                "asset_type": row["asset_type"],
                "country": row["country"],
                "year_acquired": yr,
                "price_paid": pp,
                "current_declared_value": cdv,
                "payment_method": row["payment_method"],
                "income_produced": inc,
            })
        record["investments"] = investments
 
        # ---- claims ----
        claims = dict(record.get("claims") or {})
        form_claims = values["claims"]
        n = len(problems)
        claims["declared_net_worth"] = self.read_amount(form_claims["declared_net_worth"],
                                                   "Declared net worth", problems, allow_zero=False)
        if len(problems) > n:
            field_errors["claims.declared_net_worth"] = "Must be above zero."
        n = len(problems)
        claims["expected_aum"] = self.read_amount(form_claims["expected_aum"],
                                             "Expected assets to be managed", problems,
                                             allow_zero=False)
        if len(problems) > n:
            field_errors["claims.expected_aum"] = "Must be above zero."
        if not form_claims["pep_status"]:
            _p("PEP status is required.", "claims.pep_status", "Required.")
        claims["pep_status"] = form_claims["pep_status"]

        countries = [c.strip() for c in form_claims["wealth_countries"].split(",") if c.strip()]
        if not countries:
            _p("Enter at least one country the wealth came from.",
               "claims.wealth_countries", "Enter at least one country.")
        claims["wealth_countries"] = countries

        jump_str = form_claims.get("biggest_wealth_jump", "").strip()
        claims["biggest_wealth_jump"] = self.__app.read_amount(jump_str) if jump_str else None
        yrs_str = form_claims.get("wealth_jump_years", "").strip()
        try:
            claims["wealth_jump_years"] = float(yrs_str) if yrs_str else None
        except ValueError:
            claims["wealth_jump_years"] = None
        cp_str = form_claims.get("declared_counterparties", "").strip()
        claims["declared_counterparties"] = [c.strip() for c in cp_str.split(",") if c.strip()]

        split = {}
        for key, label, kind in WebApp.COMPOSITION_FIELDS:
            n = len(problems)
            split[key] = self.read_amount(values["composition"][key], label.replace(" (%)", ""), problems)
            if len(problems) > n:
                field_errors[f"composition.{key}"] = "Must be a number."
        if not 95 <= sum(split.values()) <= 105:
            _p(f"The wealth split adds up to {self.trim(sum(split.values()))}%, it must be 100%.")
        claims["asset_composition"] = {key: value / 100 for key, value in split.items()}
        record["claims"] = claims

        # ---- declaration ----
        record["sow_declaration"] = values["sow"]["sow_declaration"]
        sow_len = len(record["sow_declaration"])
        if sow_len < 50:
            _p("The source of wealth declaration must be at least 50 characters.",
               "sow.sow_declaration", f"Too short ({sow_len}/50 characters minimum).")

        record.setdefault("supporting_documents", [])
        return record, problems, field_errors

    def check_record(self, record: dict) -> list:
        """The forecasting's own checks (schema, job dates, ...). Returns problems."""
        if not record.get("career_history"):
            return ["Add at least one job."]
        # supporting_documents isn't part of the case layout, so leave it out of the check
        case = {key: value for key, value in record.items() if key != "supporting_documents"}
        return self.__app.validate_case(case)

    def extracted_to_values(self, extracted: dict, current_date: str = "") -> dict:
        """The AI's document details as form text, in the same shape values_from_form gives.

        The AI reply is turned into a client record by DocumentRecordBuilder - the very
        function the command line's "New Client from Documents" uses - so both give the same values
        (field names, age from the date of birth, wealth split as fractions, oldest job first).
        A value no client record can have is left out (autofill_form says which). Raises ValueError
        only if the reading as a whole cannot be a record."""
        record, _ = self.__app.record_from_reading(extracted, current_date or self.today())
        return self.values_from_reading(record, extracted)

    def values_from_reading(self, record: ClientRecord, extracted: dict) -> dict:
        """The record DocumentRecordBuilder made from a reading, as form text."""
        data = record.to_dict()
        if not extracted.get("jobs"):
            data["career_history"] = []        # the command line's empty "current job" is only there to be asked for
        values = self.values_from_record(data)
        for prefix, title, fields, kind in WebApp.SECTIONS:
            if kind == "list":
                values[prefix] = [row for row in values[prefix] if any(row.values())]
        return values

    def _same_entry(self, prefix: str, a: dict, b: dict) -> bool:
        """Is this extracted job / asset already on the form?"""
        def norm(text):
            return " ".join(str(text or "").lower().split())
        if prefix == "jobs":
            return (norm(a.get("employer_name")) == norm(b.get("employer_name"))
                    and norm(a.get("start_year")) == norm(b.get("start_year")))
        return (norm(a.get("asset_type")) == norm(b.get("asset_type"))
                and norm(a.get("year_acquired")) == norm(b.get("year_acquired")))

    def fill_blanks(self, values: dict, found: dict) -> tuple[dict, list[str]]:
        """Put the document details into the form without overwriting anything typed.

        Single boxes are filled only when empty. Jobs and assets found in the documents
        are added unless the same one is already there; empty entries are filled first.
        The wealth split is filled only if all four boxes are empty, so it still adds up.
        Returns (new values, input names that were filled) so the form can highlight them.
        """
        merged = {prefix: (dict(section) if isinstance(section, dict) else [dict(r) for r in section])
                  for prefix, section in values.items()}
        filled = []
        for prefix, title, fields, kind in WebApp.SECTIONS:
            new = found.get(prefix)
            if not new:
                continue
            if kind == "dict":
                current = merged.setdefault(prefix, {})
                if prefix == "composition" and any(current.get(f[0]) for f in fields):
                    continue
                for key, label, k in fields:
                    if new.get(key) and not current.get(key):
                        current[key] = new[key]
                        filled.append(f"{prefix}.{key}")
                continue

            rows = [row for row in merged.get(prefix, []) if any(row.values())]
            for row in new:
                if any(self._same_entry(prefix, row, existing) for existing in rows):
                    continue
                rows.append(row)
                index = len(rows) - 1
                filled.extend(f"{prefix}.{index}.{key}" for key, value in row.items() if value)
            if prefix == "jobs":   # keep the oldest job first, like the saved record
                order = sorted(range(len(rows)), key=lambda i: rows[i].get("start_year") or "9999")
                remap = {f"{prefix}.{old}.": f"{prefix}.{new}." for new, old in enumerate(order)}
                filled = [next((name.replace(o, n, 1) for o, n in remap.items() if name.startswith(o)), name)
                          for name in filled]
                rows = [rows[i] for i in order]
            merged[prefix] = rows
        return merged, filled

    def _is_stored_document(self, file_id: str) -> bool:
        """Only accept document references this app made (the DocumentStore decides)."""
        return self.__app.owns_document(file_id)

    def pending_documents(self, form: MultiDict) -> list[dict]:
        """Documents uploaded during auto-fill, carried in hidden boxes until the client is saved."""
        names, ids = form.getlist("doc.file_name"), form.getlist("doc.file_id")
        return [{"file_name": secure_filename(name) or "document", "file_id": file_id}
                for name, file_id in zip(names, ids) if self._is_stored_document(file_id)]

    def store_uploads(self, files: list[FileStorage], client_ref: str = "") -> tuple[list[dict], list[dict]]:
        """Keep each uploaded file as a supporting document and read it for the AI.
        Returns (supporting document entries, documents read for extraction)."""
        actor = self.__actor()
        stored, read = [], []
        for uploaded in files:
            if not uploaded or not uploaded.filename:
                continue
            name = secure_filename(uploaded.filename) or "document"
            folder = tempfile.mkdtemp()
            try:
                path = os.path.join(folder, name)
                uploaded.save(path)
                read.append(self.__app.read_document_for_extraction(path, name))
                file_id = self.__app.upload_document(path, actor, client_ref)
                self.__flash_audit_failure(kept=file_id is not None)
                if file_id is not None:
                    stored.append({"file_name": name, "file_id": file_id})
            finally:
                shutil.rmtree(folder, ignore_errors=True)
        return stored, read

    def autofill_form(self, heading: str, form: MultiDict, files: list[FileStorage], client_ref: str = "") -> str:
        """Read the uploaded documents and show the form again with the blanks filled in."""
        values = self.values_from_form(form)
        documents = self.pending_documents(form)
        stored, read = self.store_uploads(files, client_ref)
        documents += stored
        if not read:
            return self.show_form(heading, values, ["Choose at least one document to read."], documents=documents)

        extracted, warnings = self.__app.read_documents(read, self.__actor(), client_ref)
        self.__flash_audit_failure()
        if extracted is None:
            flash("Document reading is not available right now — please try again later.")
        filled, notes = [], list(warnings)
        if extracted is not None:
            try:
                record, dropped = self.__app.record_from_reading(extracted, self.today())
            except ValueError as error:
                logger.error("WebApp.autofill_form: the AI's reading is not a possible record: %r", error)
                flash(f"The documents were read, but the details cannot be used because {error}. "
                      "Nothing was filled in.")
                return self.show_form(heading, values, [], documents=documents, notes=notes)
            dropped_messages = [entry["message"] for entry in dropped]
            if dropped_messages:
                logger.warning("WebApp.autofill_form: left out of the AI's reading: %s", " | ".join(dropped_messages))
            values, filled = self.fill_blanks(values, self.values_from_reading(record, extracted))
            notes += dropped_messages
            notes += extracted.get("notes") or []
            # the same second-look checks the command line shows after reading documents
            notes += self.__app.reading_problems(record, self.today())
        if extracted is not None and filled:
            flash(f"Read {len(read)} document(s) and filled {len(filled)} box(es), highlighted in yellow. "
                  "Check every highlighted value before saving.")
        elif extracted is not None:
            flash("The documents were read, but nothing new was found to fill in.")
        return self.show_form(heading, values, [], documents=documents, autofilled=filled, notes=notes)

    def get_record(self, client_ref: str) -> ClientRecord | None:
        """Find one client record by reference. Returns None if not found; raises ValueError,
        saying what is wrong, if the saved record cannot be read."""
        return self.__app.find_client(client_ref)

    def page_record(self, client_ref: str) -> dict:
        """The client as a page header shows it (saved layout). If the record is missing or
        cannot be read, the reference stands in for the name."""
        try:
            record = self.get_record(client_ref)
        except ValueError as error:
            flash(str(error))
            record = None
        return record.to_dict() if record is not None else {"client_ref": client_ref, "name": client_ref}

    def save_form_record(self, record: dict, new_client: bool = False) -> list[str]:
        """Save a record built from the form. Returns the problems ([] = saved). new_client is True for
        the new-client page."""
        try:
            client = ClientRecord.from_dict(record)
        except (ValueError, TypeError, AttributeError) as error:
            logger.error("WebApp: the form for %s did not make a valid record: %r", record.get("client_ref"), error)
            return [f"The client could not be saved because {ClientRecord.why_unreadable(error)}."]
        saved = self.__app.save_client(client, self.__actor(), new_client)
        self.__flash_audit_failure(kept=saved)
        if not saved:
            return ["The client was not saved because the client database cannot be read or written right now. "
                    "Please try again later."]
        return []

    def flash_ai_unavailable(self, feature: str = "Assessment") -> None:
        flash(f"{feature} is not available right now — please try again later.")

    def flash_rate_limit_error(self, seconds_left: int) -> None:
        flash(f"Rate limit: please wait {seconds_left} second{'s' if seconds_left != 1 else ''} before running another assessment.")

    def flash_unexpected_error(self) -> None:
        flash("An unexpected error occurred — please try again or contact support.")

    def show_form(self, heading: str, values: dict, problems: list, field_errors: dict | None = None,
                  documents: list | None = None, autofilled: list | None = None,
                  notes: list | None = None, notes_title: str = "") -> str:
        return render_template("client_form.html", heading=heading, values=values,
                               problems=problems, SECTIONS=WebApp.SECTIONS,
                               field_errors=field_errors or {}, documents=documents or [],
                               autofilled=autofilled or [], notes=notes or [], notes_title=notes_title)

    def __run_in_background(self, job_id: str, record: ClientRecord, case: dict, actor: str) -> None:
        """The assessment, in the background: App.assess, the very method the command
        line runs, then the same save. actor is the signed-in name, taken in the request: this thread
        has no session, and the audit flag it reads is its own."""
        job = self.__jobs[job_id]

        def step(number, label):
            job["step_num"] = number
            job["step"] = label

        try:
            result = self.__app.assess(case, record.documents(), on_step=step, show_failures=False, actor=actor)
            if result is None:
                logger.error("WebApp: the assessment of %s stopped at a critical step", record.client_ref)
                job["status"] = "error"
                job["error"] = WebApp.ASSESSMENT_STOPPED + (
                    " " + App.AUDIT_LINE_NOT_WRITTEN if self.__app.audit_write_failed() else "")
                return
            assessment_id = self.__app.save_assessment(result, record, on_step=step, actor=actor)
            audit_failed = self.__app.audit_write_failed()
            outcome_failed = self.__app.client_outcome_failed()

            # Per-feature failure flags — feature names passed to flash_ai_unavailable in assess_result
            ai_warnings = []
            if result.get("typologies") is None:
                ai_warnings.append("Crime scan")
            if result["benchmark"]["findings"] is None:
                ai_warnings.append("Benchmark")
            if result.get("forecast") is None:
                ai_warnings.append("Forecasting")

            job["result"] = {
                "record":        record.to_dict(),       # the page template reads the saved layout
                "report":        result["verdict"].report,
                "assessment_id": assessment_id,
                "saved":         assessment_id is not None,
                "audit_failed":  audit_failed,
                "outcome_failed": outcome_failed,
                "assessed_at":   result["verdict"].assessed_at,   # the same time App saved
                "ai_warnings":   ai_warnings,
                "crime_result":  WebApp.__crime_result_layout(result.get("crime_result")),
                "typologies":    WebApp.__typology_layout(result.get("typologies")),
                "benchmark":     result.get("benchmark"),
            }
            job["status"] = "done"
        except Exception:
            # The real error goes to the log; the browser is told only that it failed (CLAUDE.md §9).
            logger.exception("WebApp: the assessment of %s (job %s) failed", record.client_ref, job_id)
            job["status"] = "error"
            job["error"] = WebApp.ASSESSMENT_FAILED

    @staticmethod
    def __crime_result_layout(crime_result: dict | None) -> dict | None:
        """The crime scan's result as the page template reads it (each MatchResult's to_dict())."""
        if crime_result is None:
            return None
        return {**crime_result, "match_results": [match.to_dict() for match in crime_result["match_results"]]}

    @staticmethod
    def __typology_layout(typologies: list[Typology] | None) -> list[dict] | None:
        """The typologies as the page template reads them (the typology reply's layout)."""
        return None if typologies is None else [typology.to_dict() for typology in typologies]

    def show_report(self, record: dict, report: dict | None, assessed_at: str = "", assessment_id: str | None = None,
                    crime_result: dict | None = None, typologies: list[dict] | None = None,
                    benchmark: dict | None = None, archive: dict | None = None,
                    archive_state: str | None = None) -> str:
        """The assessment page: the same report the command line prints (VerdictEngine.report).
        archive is the last line of an archived assessment's log; archive_state is App.ARCHIVE_UNREADABLE
        when its archive record is damaged (the page then says so and offers no button)."""
        symbols = {entry["mark"]: entry["symbol"] for entry in (report or {}).get("legend", [])}
        typologies_by_id = {t.get("typology_id"): t for t in (typologies or [])}
        return render_template("assess_result.html", record=record, report=report, symbols=symbols,
                               assessed_at=assessed_at, assessment_id=assessment_id,
                               crime_result=crime_result, typologies_by_id=typologies_by_id, benchmark=benchmark,
                               typologies_checked=App.typologies_checked(report),
                               archive=archive, archive_state=archive_state)

    def home(self) -> str:
        """The client list. If the saved clients cannot be read the page says so and shows no list
        (it never shows "No clients yet" for a read failure)."""
        try:
            clients = self.__app.all_clients()
        except ValueError as error:
            flash(str(error))
            clients = None
        activity: dict | None = None
        activity_error = ""
        if clients:
            try:
                activity = self.__app.last_activity()
            except ValueError:
                activity_error = f"{App.AUDIT_UNAVAILABLE} The last activity of each client cannot be shown."
        return render_template("home.html", clients=clients, activity=activity, activity_error=activity_error)

    def find(self) -> Response:
        client_ref = request.args.get("ref", "").strip().upper()
        try:
            found = bool(client_ref) and self.get_record(client_ref) is not None
        except ValueError as error:
            flash(str(error))
            return self.__home()
        if found:
            return redirect(url_for("view_client", client_ref=client_ref))
        flash(f"No client found with reference '{client_ref}'.")
        return self.__home()

    def _documents_on_save(self, form: MultiDict, files: list[FileStorage], client_ref: str = "") -> list[dict]:
        """Documents to attach when the form is saved: ones kept from auto-fill, plus any
        files chosen in the upload box without pressing "Read documents"."""
        stored, _ = self.store_uploads(files, client_ref)
        return self.pending_documents(form) + stored

    def new_client(self) -> str | Response:
        if request.method == "POST":
            values = self.values_from_form(request.form)
            documents = self._documents_on_save(request.form, request.files.getlist("autofill_files"))
            try:
                new_ref = self.__app.new_client_ref()
            except ValueError as error:          # the saved clients can't be checked, so no reference is made
                return self.show_form("New client", values, [str(error)], {}, documents=documents)
            record, problems, field_errors = self.build_record(values, new_ref)
            if not problems:
                problems = self.check_record(record)
                field_errors = {}
            if not problems:
                record["supporting_documents"] = documents
                problems = self.save_form_record(record, new_client=True)
                if not problems:
                    flash("Client saved.")
                    return redirect(url_for("view_client", client_ref=record["client_ref"]))
            return self.show_form("New client", values, problems, field_errors, documents=documents)
 
        return self.show_form("New client", self.values_from_record({"current_date": self.today()}), [])

    def new_client_autofill(self) -> str:
        return self.autofill_form("New client", request.form, request.files.getlist("autofill_files"))

    def view_client(self, client_ref: str) -> str | Response:
        try:
            record = self.get_record(client_ref)
        except ValueError as error:
            flash(str(error))
            return self.__home()
        if record is None:
            abort(404)
        saved = record.to_dict()                 # the page template reads the saved layout
        show_archived = request.args.get("archived") == "1"
        archive_states: list[str] = []           # one state per shown assessment, in the same order
        archived_count = 0
        try:
            everything = self.__app.client_assessments(client_ref, include_archived=True)
            # The state is worked out per record, not per id: old records may share a missing id.
            rows = [(a, App.archive_state(a)) for a in everything]
            archived_count = sum(1 for _, state in rows if state != App.ARCHIVE_ACTIVE)
            if not show_archived:
                rows = [(a, state) for a, state in rows if state == App.ARCHIVE_ACTIVE]
            assessments = [a for a, _ in rows]
            archive_states = [state for _, state in rows]
        except (OSError, ValueError) as error:
            logger.error("WebApp.view_client: the saved assessments cannot be read: %r", error)
            flash(App.ASSESSMENTS_UNAVAILABLE)
            assessments = None
        now = datetime.now(timezone.utc)
        trail_filter = TrailFilter.from_query(request.args, now)
        history: list | None = None
        history_error, history_unreadable, history_total, history_count = "", 0, 0, 0
        try:
            everything, history_unreadable = self.__app.audit_trail(client_ref)
            history_total = len(everything)
            shown = [event for event in everything if trail_filter.matches(event, now)]
            history_count = len(shown)
            history = self.__by_day(shown)
        except ValueError:
            history_error = App.AUDIT_UNAVAILABLE         # the rest of the page still shows
        flag_boxes, flags_error, flagged_sequences = self.__client_flag_boxes(
            client_ref, str(saved.get("name") or ""), everything if history is not None else [], bool(history_error), now)
        return render_template("client_view.html", record=saved, history=history,
                               flag_boxes=flag_boxes, flags_error=flags_error, flagged_sequences=flagged_sequences,
                               history_error=history_error, history_unreadable=history_unreadable,
                               history_total=history_total, history_count=history_count,
                               trail_filter=trail_filter, trail_shows=list(TrailFilter.SHOW_LABELS.items()),
                               trail_whens=list(TrailFilter.WHEN_LABELS.items()),
                               today=AuditFilter.singapore_day(now).isoformat(),
                               values=self.values_from_record(saved), SECTIONS=WebApp.SECTIONS,
                               assessments=assessments, problems=record.problems(),
                               show_archived=show_archived, archived_count=archived_count,
                               archive_states=archive_states, max_reason=App.MAX_ARCHIVE_REASON)

    def __client_flag_boxes(self, client_ref: str, client_name: str, history: list[AuditEvent], history_failed: bool,
                            now: datetime) -> tuple[list[dict], str, set[int]]:
        """For the admin's client page: the "Why this client is flagged" boxes (one per flag that is not
        resolved, each with the picture of what happened), the line to show if they cannot be worked out, and the
        numbers of the log entries behind them (the timeline marks those). Officers get nothing."""
        account = self.__current()
        if account is None or not account.is_admin():
            return [], "", set()
        if history_failed:                         # the page already says the log cannot be read
            return [], "", set()
        try:
            tickets = self.__app.client_flags(client_ref, now)
        except ValueError as error:
            return [], WebApp.__shown_error(error), set()
        by_number = {event.sequence: event for event in history}
        boxes = [{"ticket": ticket, "css": WebApp.SEVERITY_CLASS[ticket.flag.severity],
                  "pic": self.__picture(ticket, [by_number[n] for n in ticket.flag.sequences if n in by_number], 0,
                                        client_name, history)} for ticket in tickets]
        return boxes, "", {n for ticket in tickets for n in ticket.flag.sequences}

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

    def archive_assessment(self, assessment_id: str) -> Response:
        """Hide one assessment from the lists (nothing is deleted), then go back to its client."""
        return self.__change_archive(assessment_id, archive=True)

    def restore_assessment(self, assessment_id: str) -> Response:
        """Bring an archived assessment back into the lists, then go back to its client."""
        return self.__change_archive(assessment_id, archive=False)

    def __change_archive(self, assessment_id: str, archive: bool) -> Response:
        """Archive or restore, tell the officer what happened, and go to the client page."""
        reason = request.form.get("reason", "") if archive else ""      # optional, archive only
        try:
            saved = self.__app.find_assessment(assessment_id)
            if saved is None:
                abort(404)
            if archive:
                result = self.__app.archive_assessment(saved["assessment_id"], reason, self.__actor())
            else:
                result = self.__app.restore_assessment(saved["assessment_id"], self.__actor())
        except (OSError, ValueError) as error:
            logger.error("WebApp.__change_archive: the saved assessments cannot be read: %r", error)
            flash(App.ASSESSMENTS_UNAVAILABLE)
            return self.__home()
        self.__flash_audit_failure(kept=result == App.ARCHIVE_CHANGED)
        client_ref = saved["client_ref"]
        keep_archived = False
        if result == App.ARCHIVE_CHANGED and not archive:
            # Only chooses which view to go back to; if it cannot be read, the restore still happened.
            try:
                keep_archived = any(App.archive_state(a) != App.ARCHIVE_ACTIVE
                                    for a in self.__app.client_assessments(client_ref, include_archived=True))
            except (OSError, ValueError) as error:
                logger.error("WebApp.__change_archive: restored, but the client's list cannot be read: %r", error)
        done, nothing_to_do = (("Assessment archived. It is hidden from the lists, not deleted.",
                                "This assessment is already archived.") if archive else
                               ("Assessment restored.", "This assessment is not archived."))
        word = "archived" if archive else "restored"
        messages = {App.ARCHIVE_CHANGED: done, App.ARCHIVE_NO_CHANGE: nothing_to_do,
                    App.ARCHIVE_UNREADABLE: "This assessment's archive record is damaged, so it cannot be changed.",
                    App.ARCHIVE_NOT_SAVED: f"The assessment was not {word} because saving failed. Please try again later."}
        if result == App.ARCHIVE_NOT_FOUND:
            abort(404)
        if result == App.ARCHIVE_BAD_REASON:
            messages[result] = f"Nothing was archived. {App.archive_reason_problem(reason)}"
        flash(messages.get(result, App.ASSESSMENTS_UNAVAILABLE))
        return redirect(url_for("view_client", client_ref=client_ref, **({"archived": "1"} if keep_archived else {})))

    def view_assessment(self, assessment_id: str) -> str | Response:
        try:
            saved = self.__app.find_assessment(assessment_id)
        except (OSError, ValueError) as error:
            logger.error("WebApp.view_assessment: the saved assessments cannot be read: %r", error)
            flash(App.ASSESSMENTS_UNAVAILABLE)
            return self.__home()
        if saved is None:
            abort(404)
        record = self.page_record(saved["client_ref"])
        snapshot = saved.get("case")
        if isinstance(snapshot, dict) and snapshot.get("name"):
            record = {**record, "name": snapshot["name"]}      # the client as they were when this ran
        state = App.archive_state(saved)
        log = saved.get("archive_log")
        archive = log[-1] if state == App.ARCHIVE_ARCHIVED else None
        typologies = (saved.get("crime_scan") or {}).get("typologies", {})
        typology_list = typologies.get("sector_typologies") if isinstance(typologies, dict) else None
        return self.show_report(record, saved.get("report"), saved.get("assessed_at", ""), assessment_id,
                           crime_result=saved.get("crime_result"), typologies=typology_list,
                           benchmark=saved.get("benchmark"), archive=archive, archive_state=state)

    def edit_client(self, client_ref: str) -> str | Response:
        try:
            client = self.get_record(client_ref)
        except ValueError as error:
            flash(str(error))
            return self.__home()
        if client is None:
            abort(404)
        old = client.to_dict()                   # the form is filled from, and saved in, the saved layout
 
        if request.method == "POST":
            values = self.values_from_form(request.form)
            documents = self._documents_on_save(request.form, request.files.getlist("autofill_files"), client_ref)
            record, problems, field_errors = self.build_record(values, client_ref, old)
            if not problems:
                problems = self.check_record(record)
                field_errors = {}
            if not problems:
                known = {d.get("file_id") for d in record.get("supporting_documents", [])}
                record["supporting_documents"] = list(record.get("supporting_documents", [])) + [
                    d for d in documents if d["file_id"] not in known]
                problems = self.save_form_record(record)
                if not problems:
                    flash("Changes saved.")
                    return redirect(url_for("view_client", client_ref=client_ref))
            return self.show_form(f"Edit {client_ref}", values, problems, field_errors, documents=documents)
 
        # Shown as things to fix; they never stop the officer saving (POST checks again)
        return self.show_form(f"Edit {client_ref}", self.values_from_record(old), [],
                              notes=client.problems(), notes_title="To complete or check")

    def edit_client_autofill(self, client_ref: str) -> str | Response:
        try:
            found = self.get_record(client_ref) is not None
        except ValueError as error:
            flash(str(error))
            return self.__home()
        if not found:
            abort(404)
        return self.autofill_form(f"Edit {client_ref}", request.form, request.files.getlist("autofill_files"), client_ref)

    def upload_documents(self, client_ref: str) -> Response:
        try:
            record = self.get_record(client_ref)
        except ValueError as error:
            flash(str(error))
            return self.__home()
        if record is None:
            abort(404)
 
        actor = self.__actor()
        added = 0
        chosen = 0
        for uploaded in request.files.getlist("files"):
            if not uploaded.filename:
                continue
            chosen += 1
            name = secure_filename(uploaded.filename) or "document"
 
            # upload_supporting_document wants a file path, so save to a temp folder first
            folder = tempfile.mkdtemp()
            path = os.path.join(folder, name)
            uploaded.save(path)
            file_id = self.__app.upload_document(path, actor, client_ref)
            self.__flash_audit_failure(kept=file_id is not None)
            shutil.rmtree(folder, ignore_errors=True)
 
            if file_id is None:
                flash(f"Could not upload {name}.")
                continue
            record.add_document({"file_name": name, "file_id": file_id})
            added += 1
 
        if added:
            saved = self.__app.save_client(record, actor)
            self.__flash_audit_failure(kept=saved)
            if saved:
                flash(f"{added} document(s) uploaded.")
            else:
                flash("Documents uploaded, but the record could not be saved.")
        elif chosen == 0:
            flash("Choose at least one file first.")
        return redirect(url_for("view_client", client_ref=client_ref))

    def download_document(self, client_ref: str, file_id: str) -> Response:
        try:
            record = self.get_record(client_ref)
        except ValueError as error:
            flash(str(error))
            return self.__home()
        if record is None:
            abort(404)
 
        document = None
        for item in record.documents():
            if item.get("file_id") == file_id:
                document = item
        if document is None:
            abort(404)
 
        name = secure_filename(document.get("file_name", "")) or "document"
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, name)
        ok = self.__app.download_document(document.get("file_path") or file_id, path, self.__actor(), client_ref)   # local copy
        self.__flash_audit_failure()
        data = b""
        if ok:
            with open(path, "rb") as handle:
                data = handle.read()
        shutil.rmtree(folder, ignore_errors=True)
 
        if not ok:
            flash("Could not download that document.")
            return redirect(url_for("view_client", client_ref=client_ref))
        return send_file(io.BytesIO(data), as_attachment=True, download_name=name)

    def assess_client(self, client_ref: str) -> Response:
        try:
            record = self.get_record(client_ref)
        except ValueError as error:
            flash(str(error))
            return self.__home()
        if record is None:
            abort(404)
        if not self.__app.ai_available():
            logging.getLogger(__name__).warning("assess_client: no API key configured (client_ref=%s)", client_ref)
            self.flash_ai_unavailable("Assessment")
            return redirect(url_for("view_client", client_ref=client_ref))

        user_key = request.remote_addr or "unknown"
        allowed, seconds_left = self.__limiter.check(user_key)
        if not allowed:
            self.flash_rate_limit_error(seconds_left)
            return redirect(url_for("view_client", client_ref=client_ref))

        self.__limiter.record(user_key)
        # The same case the command line assesses, dated today (CaseReader).
        # The command line asks for anything missing; here the officer completes the record first.
        case, missing = self.__app.read_case(record)
        problems = self.__app.validate_case(case) if case is not None else []
        if case is None or problems:
            if missing and record.problems():       # the client page lists these in full under "To complete or check"
                flash("Complete the client record before assessing: see the list below.")
            else:
                flash("Complete the client record before assessing (Edit): " + "; ".join(missing or problems))
            return redirect(url_for("view_client", client_ref=client_ref))
        job_id = uuid.uuid4().hex
        self.__jobs[job_id] = {
            "status":     "running",
            "step_num":   0,
            "step":       "Starting…",
            "result":     None,
            "error":      None,
            "client_ref": client_ref,
        }
        threading.Thread(
            target=self.__run_in_background, args=(job_id, record, case, self.__actor()), daemon=True
        ).start()
        return redirect(url_for("assess_loading", job_id=job_id))

    def assess_loading(self, job_id: str) -> str:
        if job_id not in self.__jobs:
            abort(404)
        record = self.page_record(self.__jobs[job_id]["client_ref"])
        return render_template("assess_loading.html", job_id=job_id, record=record,
                               ASSESS_STEPS=self._steps())

    def assess_poll(self, job_id: str) -> dict:
        """The job's progress. Flask sends a returned dict to the browser as JSON."""
        if job_id not in self.__jobs:
            return {"status": "error", "error": "Job not found."}
        job = self.__jobs[job_id]
        return {
            "status":   job["status"],
            "step_num": job["step_num"],
            "step":     job["step"],
            "error":    job.get("error"),
        }

    def assess_result(self, job_id: str) -> str | Response:
        if job_id not in self.__jobs:
            abort(404)
        job = self.__jobs[job_id]
        if job["status"] == "running":
            return redirect(url_for("assess_loading", job_id=job_id))
        if job["status"] == "error":
            self.flash_unexpected_error()
            return redirect(url_for("view_client", client_ref=job["client_ref"]))
        for feature in job["result"].get("ai_warnings", []):
            self.flash_ai_unavailable(feature)
        r = job["result"]
        if r.get("outcome_failed"):
            flash(App.OUTCOME_NOT_UPDATED)
        if r.get("audit_failed"):
            flash(App.AUDIT_NOT_WRITTEN if r.get("saved", True) else App.AUDIT_LINE_NOT_WRITTEN)
        if not r.get("saved", True):
            flash(WebApp.ASSESSMENT_NOT_SAVED)
        return self.show_report(r["record"], r["report"], r.get("assessed_at", ""), r.get("assessment_id"),
                           crime_result=r.get("crime_result"), typologies=r.get("typologies"),
                           benchmark=r.get("benchmark"))

    def list_assessments_view(self) -> str:
        try:
            assessments = self.__app.all_assessments()
            archived_count = sum(1 for a in self.__app.all_assessments(include_archived=True)
                                 if App.archive_state(a) != App.ARCHIVE_ACTIVE)
        except ValueError as error:
            flash(str(error))
            assessments = None
            archived_count = 0
        return render_template("assessments.html", assessments=assessments, archived_count=archived_count)

    def sync_to_cloud(self) -> Response:
        stats = self.__app.sync_to_cloud(self.__actor())
        self.__flash_audit_failure()
        cases = stats["cases_synced"]
        assessments = stats["assessments_synced"]
        skipped = stats["skipped"]
        errors = stats["errors"]
        synced = cases + assessments

        if not errors:
            msg = f"Sync complete — {cases} case(s) and {assessments} assessment(s) pushed to cloud."
            if skipped:
                msg += f" {skipped} already up to date."
            flash(msg)
        elif synced > 0:
            flash(
                f"Partial sync — {cases} case(s) and {assessments} assessment(s) pushed to cloud. "
                "Some records could not be synced — please try again later or contact your administrator."
            )
        else:
            flash("Sync unsuccessful — please try again later or contact your administrator.")
        return self.__home()

    def handle_404(self, e: HTTPException) -> tuple[str, int]:
        return render_template("error.html", error_detail=None), 404

    def handle_exception(self, e: Exception) -> tuple[str, int]:
        """The error page. A web error such as 405 (wrong method) or 413 (upload too large) keeps its own
        status code; anything else is an unexpected error: logged in full, shown as a plain 500 page."""
        if isinstance(e, HTTPException):
            return render_template("error.html", error_detail=None), e.code or 500
        import logging
        import traceback
        logging.error("Unhandled exception: %s", traceback.format_exc())
        detail = str(e) if self.__flask.debug else None
        return render_template("error.html", error_detail=detail), 500

    def _steps(self) -> list[str]:
        """The steps of an assessment, as App announces them."""
        return self.__app.steps()
