"""WebApp: the browser front end, driven through Flask's test client. No network: the App
behind it has a made-up AI caller and keeps its files in a temporary folder."""

import html
import io
import json
import re
import shutil
import time

import flask
import pytest
from markupsafe import escape

from app.application.app import App
from app.interface.rate_limiter import RateLimiter
from app.interface.web_app import WebApp
from app.model.client_record import ClientRecord
from tests import fake_ai, fake_services
from tests.logic_fixtures import sample_case
from tests.audit_files import break_audit, fix_audit
from tests.web_session import account_with_role, sign_in


def _no_answer(prompt, schema, options):
    """A made-up AI caller that is "available" but never answers, like a connection that fails."""
    return None


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(_no_answer, data_folder=str(tmp_path))
    site = WebApp(application)
    site.flask().config["TESTING"] = True
    client = site.flask().test_client()
    sign_in(client, application)
    return application, site, client


def _form_fields(site, record: dict) -> dict:
    """The record as the browser would post it: "claims.declared_net_worth" for single values,
    and one list per field ("jobs.start_year") for the repeated job and asset rows."""
    fields = {}
    for prefix, values in site.values_from_record(record).items():
        if isinstance(values, dict):
            fields.update({f"{prefix}.{key}": value for key, value in values.items()})
        else:
            for row in values:
                for key, value in row.items():
                    fields.setdefault(f"{prefix}.{key}", []).append(value)
    return fields


def _wait_for(site_client, job_id, seconds=20):
    for _ in range(seconds * 10):
        state = site_client.get(f"/assess/poll/{job_id}").get_json()
        if state["status"] != "running":
            return state
        time.sleep(0.1)
    raise AssertionError("the assessment did not finish")


def test_the_web_app_only_holds_an_app_and_its_rate_limiter(web):
    _, site, _ = web
    held = [name for name in vars(site) if not name.startswith("_WebApp__")]
    assert held == []
    assert set(vars(site)) == {"_WebApp__app", "_WebApp__limiter", "_WebApp__jobs", "_WebApp__flask"}


def test_a_handed_in_rate_limiter_decides_when_an_assessment_may_start(tmp_path, monkeypatch):
    """The limiter WebApp is handed is the one it asks; without one it uses the App's own."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(_no_answer, data_folder=str(tmp_path))
    application.clients().save(sample_case())
    ref = sample_case()["client_ref"]
    limiter = RateLimiter(60)
    limiter.record("127.0.0.1")                       # this browser has just started one
    client = WebApp(application, limiter).flask().test_client()
    sign_in(client, application)
    page = client.post(f"/client/{ref}/assess", follow_redirects=True).get_data(as_text=True)
    assert "Rate limit: please wait" in page
    assert application.rate_limiter().check("127.0.0.1") == (True, 0)   # the App's limiter was not used


def test_start_serves_the_flask_app_on_the_local_machine_by_default(web, monkeypatch):
    _, site, _ = web
    served = []
    monkeypatch.setattr(site.flask(), "run", lambda **options: served.append(options))
    site.start()
    assert served == [{"host": "127.0.0.1", "port": 5000, "debug": False, "use_reloader": False}]


def test_start_uses_the_host_port_and_debug_it_is_given(web, monkeypatch):
    _, site, _ = web
    served = []
    monkeypatch.setattr(site.flask(), "run", lambda **options: served.append(options))
    site.start("0.0.0.0", 5001, True)
    assert served == [{"host": "0.0.0.0", "port": 5001, "debug": True, "use_reloader": False}]


def test_pages_return_html_text_and_redirects_return_a_response(web):
    """The type hints match what Flask really returns: a page is HTML text (str), while
    redirect() and send_file() give a werkzeug Response object, and the progress poll is a dict
    that Flask sends as JSON."""
    from werkzeug.wrappers import Response
    application, site, _ = web
    with site.flask().test_request_context("/find?ref=NOBODY"):
        flask.session["account"] = account_with_role(application).email
        assert isinstance(site.home(), str)
        assert isinstance(site.find(), Response)
        assert isinstance(site.sync_to_cloud(), Response)
        assert site.assess_poll("no-such-job") == {"status": "error", "error": "Job not found."}


def test_every_page_is_branded_orbit(web):
    _, _, client = web
    page = client.get("/").get_data(as_text=True)
    assert "<title>Orbit</title>" in page and 'class="brand"' in page and ">Orbit</a>" in page


def test_the_home_page_lists_the_saved_clients(web):
    application, _, client = web
    application.clients().save(sample_case())
    page = client.get("/")
    assert page.status_code == 200
    assert sample_case()["client_ref"] in page.get_data(as_text=True)


def test_the_new_client_form_opens(web):
    _, _, client = web
    assert client.get("/client/new").status_code == 200


def test_an_incomplete_form_is_shown_again_with_what_is_wrong(web):
    application, _, client = web
    page = client.post("/client/new", data={"name": "", "nationality": ""})
    assert page.status_code == 200
    assert application.clients().load() == []
    assert "class=\"problems\"" in page.get_data(as_text=True) or "required" in page.get_data(as_text=True).lower()


def test_a_complete_form_saves_the_client(web):
    application, site, client = web
    page = client.post("/client/new", data=_form_fields(site, sample_case()))
    assert page.status_code == 302, page.get_data(as_text=True)[:2000]
    saved = application.clients().load()
    assert len(saved) == 1
    assert saved[0]["name"] == sample_case()["name"]
    assert saved[0]["claims"]["declared_net_worth"] == sample_case()["claims"]["declared_net_worth"]


def test_a_saved_client_can_be_viewed_and_an_unknown_one_is_not_found(web):
    application, _, client = web
    application.clients().save(sample_case())
    assert client.get(f"/client/{sample_case()['client_ref']}").status_code == 200
    assert client.get("/client/NO-SUCH-CLIENT").status_code == 404


def _save_client_without_pep_answer(application) -> str:
    record = sample_case()
    record["claims"]["pep_status"] = ""
    application.clients().save(record)
    return record["client_ref"]


def test_the_client_page_and_edit_form_list_the_claim_problems_to_fix(web):
    application, _, client = web
    client_ref = _save_client_without_pep_answer(application)
    for url in (f"/client/{client_ref}", f"/client/{client_ref}/edit"):
        page = client.get(url).get_data(as_text=True)
        assert "The PEP question is not answered" in page


def test_a_complete_client_page_lists_no_problems(web):
    application, _, client = web
    application.clients().save(sample_case())
    page = client.get(f"/client/{sample_case()['client_ref']}").get_data(as_text=True)
    assert "To complete or check" not in page


def _flashes(client) -> list[str]:
    with client.session_transaction() as session:
        return [text for _, text in session.get("_flashes", [])]


def _save_broken_client(application) -> str:
    """Save a record with an impossible age, which ClientRecord cannot be built from."""
    record = sample_case()
    record["career"]["age"] = 5
    application.clients().save(record)
    return record["client_ref"]


def test_a_saved_client_that_cannot_be_read_is_reported_on_every_client_page(web):
    application, _, client = web
    client_ref = _save_broken_client(application)
    for method, url in (("get", f"/client/{client_ref}"), ("get", f"/client/{client_ref}/edit"),
                        ("get", f"/find?ref={client_ref}"), ("post", f"/client/{client_ref}/documents"),
                        ("post", f"/client/{client_ref}/autofill"),
                        ("get", f"/client/{client_ref}/documents/some-file")):
        reply = getattr(client, method)(url)
        assert reply.status_code == 302 and reply.headers["Location"].endswith("/"), url
        assert any("could not be loaded" in text and "age must be between 18 and 120" in text
                   for text in _flashes(client))
        client.get("/")                                             # shows, and so clears, the message


def test_editing_a_client_saves_the_changes(web):
    application, site, client = web
    application.clients().save(sample_case())
    fields = _form_fields(site, sample_case())
    fields["client.name"] = "Daniel K. Tan"
    reply = client.post(f"/client/{sample_case()['client_ref']}/edit", data=fields)
    assert reply.status_code == 302, reply.get_data(as_text=True)[:2000]
    assert application.find_client(sample_case()["client_ref"]).profile.name == "Daniel K. Tan"


def test_a_form_that_does_not_make_a_valid_record_is_shown_again_not_saved(web):
    application, site, client = web
    fields = _form_fields(site, sample_case())
    fields["claims.wealth_jump_years"] = "-2"                      # the form itself does not check this one
    page = client.post("/client/new", data=fields)
    assert page.status_code == 200
    assert "could not be saved because a declared figure cannot be negative" in page.get_data(as_text=True)
    assert application.clients().load() == []


def test_an_uploaded_document_is_kept_with_the_client(web):
    application, _, client = web
    application.clients().save(sample_case())
    reply = client.post(f"/client/{sample_case()['client_ref']}/documents", content_type="multipart/form-data",
                        data={"files": (io.BytesIO(b"payslip"), "payslip.txt")})
    assert reply.status_code == 302
    documents = application.find_client(sample_case()["client_ref"]).documents()
    assert [document["file_name"] for document in documents] == ["payslip.txt"]


def test_an_unknown_page_shows_the_error_page(web):
    _, _, client = web
    page = client.get("/no/such/page")
    assert page.status_code == 404
    assert "Back to home" in page.get_data(as_text=True)


def test_with_no_api_key_the_assessment_is_refused_with_a_message(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    application = App(None, data_folder=str(tmp_path))
    application.clients().save(sample_case())
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    page = client.post(f"/client/{sample_case()['client_ref']}/assess", follow_redirects=True)
    assert page.status_code == 200
    assert application.assessments().load() == []


def test_an_assessment_runs_in_the_background_and_is_saved(web):
    application, _, client = web
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    started = client.post(f"/client/{record['client_ref']}/assess")
    assert started.status_code == 302 and "/assess/loading/" in started.headers["Location"]
    job_id = started.headers["Location"].rsplit("/", 1)[-1]
    assert client.get(f"/assess/loading/{job_id}").status_code == 200
    state = _wait_for(client, job_id)
    assert state["status"] == "done", state
    assert client.get(f"/assess/result/{job_id}").status_code == 200
    saved = application.assessments().for_client(record["client_ref"])
    assert len(saved) == 1
    assert application.clients().find(record["client_ref"])["outcome"] == saved[0]["outcome"]
    assert client.get(f"/assessment/{saved[0]['assessment_id']}").status_code == 200
    assert client.get("/assessments").status_code == 200


def test_the_result_page_shows_the_crime_cards_from_the_typologies(tmp_path, monkeypatch):
    """The page template reads dicts: the web app hands it the typologies' to_dict() layout, so a
    fresh result and the same assessment opened later show the same crime cards."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(fake_ai.caller(), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    job_id = client.post(f"/client/{record['client_ref']}/assess").headers["Location"].rsplit("/", 1)[-1]
    assert _wait_for(client, job_id)["status"] == "done"
    typology = fake_ai.typologies()["sector_typologies"][0]

    def crime_cards(page: str) -> str:
        return page[page.index("Crime - known patterns for his industry"):]

    fresh = client.get(f"/assess/result/{job_id}").get_data(as_text=True)
    assert "1 typologies scanned" in fresh and "1 matched" in fresh
    for shown in (typology["name"], typology["description"], "TRADE BASED ML", "HIGH MATCH",
                  typology["source_quotes"][0]["quote"]):
        assert shown in fresh, shown
    saved = application.assessments().for_client(record["client_ref"])[0]
    reopened = client.get(f"/assessment/{saved['assessment_id']}").get_data(as_text=True)
    assert crime_cards(reopened) == crime_cards(fresh)
    # the research ran, so the typologies were checked against it and carry no "not checked" marker
    assert "not checked against research" not in fresh and "not checked against research" not in reopened


def test_when_the_research_fails_the_page_says_the_typologies_were_not_checked(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(fake_ai.caller(research_reply=None), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    job_id = client.post(f"/client/{record['client_ref']}/assess").headers["Location"].rsplit("/", 1)[-1]
    assert _wait_for(client, job_id)["status"] == "done"
    fresh = client.get(f"/assess/result/{job_id}").get_data(as_text=True)
    assert "not checked against research" in fresh
    assert "The crime scan&#39;s research" in fresh or "The crime scan's research" in fresh   # shown as not run
    saved = application.assessments().for_client(record["client_ref"])[0]
    assert saved["verdict"]["verdict"] != "PASSED"
    reopened = client.get(f"/assessment/{saved['assessment_id']}").get_data(as_text=True)
    for page in (fresh, reopened):                     # on the crime cards themselves, fresh and reopened
        cards = page[page.index("Crime - known patterns for his industry"):]
        assert "not checked against research" in cards.split("Full evidence")[0]
        assert "typologies checked" not in page               # the header doesn't claim a check that didn't happen


def test_assessing_a_saved_client_that_cannot_be_read_is_refused_with_a_message(web):
    application, _, client = web
    record = sample_case()
    record["career"]["age"] = 5                                  # impossible: ClientRecord rejects it
    application.clients().save(record)
    reply = client.post(f"/client/{record['client_ref']}/assess")
    assert reply.status_code == 302 and "/assess/loading/" not in reply.headers["Location"]
    with client.session_transaction() as session:
        messages = [text for _, text in session.get("_flashes", [])]
    assert any("could not be loaded" in text for text in messages)
    assert application.assessments().load() == []


def test_a_second_assessment_straight_away_is_rate_limited(web):
    application, _, client = web
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    first = client.post(f"/client/{record['client_ref']}/assess")
    _wait_for(client, first.headers["Location"].rsplit("/", 1)[-1])
    second = client.post(f"/client/{record['client_ref']}/assess")
    assert "/assess/loading/" not in second.headers["Location"]


def test_an_unknown_assessment_job_is_reported_as_an_error(web):
    _, _, client = web
    assert client.get("/assess/poll/no-such-job").get_json() == {"status": "error", "error": "Job not found."}


def test_syncing_with_no_database_says_so_and_goes_home(web):
    _, _, client = web
    page = client.post("/sync", follow_redirects=True)
    assert page.status_code == 200
    assert "Sync unsuccessful" in page.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Filling the form from uploaded documents (moved from the old app/web_app.py tests)
# ---------------------------------------------------------------------------

AI_READING = {
    "client": {"name": "Daniel Tan", "nationality": "Singaporean", "country_of_residence": "Singapore",
               "date_of_birth": "1980-03-15", "age": None},
    "jobs": [
        {"start_year": 2004, "end_year": 2012, "occupation": "Analyst", "seniority": "Analyst",
         "industry": "Banking", "employer_name": "DBS Bank", "employer_size": "30000",
         "country": "Singapore", "source_file": "cv.pdf"},
        {"start_year": 2012, "end_year": None, "occupation": "Portfolio Manager", "seniority": "Director",
         "industry": "Asset Management", "employer_name": "Temasek", "employer_size": None,
         "country": "Singapore", "source_file": "cv.pdf"},
    ],
    "assets": [
        {"asset_type": "Property - Condo", "country": "Singapore", "year_acquired": 2015,
         "price_paid_sgd": 1800000, "current_declared_value_sgd": 2400000, "payment_method": "loan",
         "income_produced_sgd": 60000, "source_file": "deed.pdf"},
    ],
    "composition": {"property": 50, "listed_equities": 30, "private_business": 0, "cash": 20},
    "claims": {"declared_net_worth_sgd": 4800000, "expected_aum_sgd": 2000000, "pep_status": "None",
               "wealth_countries": ["Singapore"], "biggest_wealth_jump_sgd": None,
               "wealth_jump_years": None, "declared_counterparties": ["DBS Bank", "UOB Kay Hian"]},
    "sow_declaration": None,
    "notes": ["2019 bonus is in USD (payslip.pdf) - convert to SGD"],
}


@pytest.fixture
def reading_web(tmp_path, monkeypatch):
    """A WebApp whose AI reads every upload as AI_READING."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(fake_ai.caller(documents_reply=AI_READING), data_folder=str(tmp_path))
    site = WebApp(application)
    site.flask().config["TESTING"] = True
    client = site.flask().test_client()
    sign_in(client, application)
    return application, site, client


def _empty_values(site):
    return site.values_from_record({"current_date": "2026-10-13"})


def test_an_ai_reading_becomes_form_text(web):
    _, site, _ = web
    found = site.extracted_to_values(AI_READING, "2026-10-13")
    assert found["client"]["age"] == "46"                      # worked out from the date of birth
    assert found["composition"]["property"] == "50"
    assert found["assets"][0]["price_paid"] == "1800000"
    assert found["claims"]["declared_counterparties"] == "DBS Bank, UOB Kay Hian"
    assert len(found["jobs"]) == 2


def test_fill_blanks_never_overwrites_typed_values(web):
    _, site, _ = web
    values = _empty_values(site)
    values["client"]["name"] = "Daniel K. Tan"
    merged, filled = site.fill_blanks(values, site.extracted_to_values(AI_READING, "2026-10-13"))
    assert merged["client"]["name"] == "Daniel K. Tan"
    assert "client.name" not in filled
    assert merged["client"]["nationality"] == "Singaporean"
    assert "client.nationality" in filled


def test_fill_blanks_skips_jobs_already_on_the_form_and_keeps_order(web):
    _, site, _ = web
    values = _empty_values(site)
    values["jobs"] = [{"start_year": "2012", "end_year": "", "occupation": "PM", "seniority": "",
                       "industry": "", "employer_name": "temasek", "employer_size": "", "country": ""}]
    merged, filled = site.fill_blanks(values, site.extracted_to_values(AI_READING, "2026-10-13"))
    assert [job["employer_name"] for job in merged["jobs"]] == ["DBS Bank", "temasek"]
    assert "jobs.0.employer_name" in filled                    # the added DBS job, now first
    assert "jobs.1.employer_name" not in filled                # the typed one is untouched


def test_the_wealth_split_is_left_alone_if_partly_typed(web):
    _, site, _ = web
    values = _empty_values(site)
    values["composition"]["cash"] = "100"
    merged, filled = site.fill_blanks(values, site.extracted_to_values(AI_READING, "2026-10-13"))
    assert merged["composition"]["property"] == ""
    assert not [name for name in filled if name.startswith("composition.")]


def test_only_this_apps_document_references_are_accepted(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    shutil.copytree("config", tmp_path / "config")                     # the settings App needs
    site = WebApp(App(None, root=str(tmp_path), data_folder="data"))     # laid out as in production
    assert site._is_stored_document("data/documents/ab12cd34_cv.pdf")
    assert site._is_stored_document("0123456789abcdef01234567")
    assert not site._is_stored_document("data/documents/../../.env")
    assert not site._is_stored_document("/etc/passwd")


def test_the_autofill_page_fills_the_form_and_keeps_the_upload(reading_web):
    _, _, client = reading_web
    response = client.post("/client/new/autofill", content_type="multipart/form-data", data={
        "client.current_date": "2026-10-13",
        "autofill_files": (io.BytesIO(b"Daniel Tan, Portfolio Manager at Temasek since 2012"), "cv.txt"),
    })
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'value="Daniel Tan"' in page
    assert re.search(r'value="[^"/]+/documents/[0-9a-f]{8}_cv\.txt"', page)  # carried until the client is saved
    assert "convert to SGD" in page                                          # the AI's note is shown


def test_a_reading_with_an_impossible_value_keeps_the_good_fields_and_says_which_was_dropped(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    reading = {**AI_READING, "client": {**AI_READING["client"], "age": 200, "date_of_birth": None}}
    application = App(fake_ai.caller(documents_reply=reading), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    response = client.post("/client/new/autofill", content_type="multipart/form-data", data={
        "autofill_files": (io.BytesIO(b"Daniel Tan, Portfolio Manager at Temasek since 2012"), "cv.txt"),
    })
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Age: the value read from the documents (200) is not possible" in page
    assert "so it was left empty. Please enter it." in page
    assert "Nothing was filled in" not in page
    assert 'value="Daniel Tan"' in page                                          # the good fields are kept
    assert re.search(r'name="career.age"[^>]*value="200"', page) is None        # the impossible one is not
    assert re.search(r'value="[^"/]+/documents/[0-9a-f]{8}_cv\.txt"', page)       # the upload is still kept


class _UnusableReadingApp(App):
    """An App whose documents are read, but whose reading cannot be made into any client record."""

    def record_from_reading(self, extracted, today=""):
        raise ValueError("the reading has no client details")


def test_a_reading_that_cannot_be_a_record_fills_nothing_and_says_why(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = _UnusableReadingApp(fake_ai.caller(documents_reply=AI_READING), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    response = client.post("/client/new/autofill", content_type="multipart/form-data", data={
        "autofill_files": (io.BytesIO(b"Daniel Tan, Portfolio Manager at Temasek since 2012"), "cv.txt"),
    })
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "the details cannot be used because the reading has no client details" in page
    assert "Nothing was filled in." in page
    assert 'value="Daniel Tan"' not in page                                       # nothing was filled in
    assert re.search(r'value="[^"/]+/documents/[0-9a-f]{8}_cv\.txt"', page)       # the upload is still kept


def test_saving_after_autofill_attaches_the_documents(reading_web, tmp_path):
    application, _, client = reading_web
    upload = tmp_path / "cv.txt"
    upload.write_text("Daniel Tan, Portfolio Manager", encoding="utf-8")
    stored = application.documents().upload(str(upload))
    form = {
        "client.name": "Daniel Tan", "client.nationality": "Singaporean",
        "client.country_of_residence": "Singapore", "client.age": "46", "client.current_date": "2026-10-13",
        "jobs.start_year": "2012", "jobs.end_year": "", "jobs.occupation": "Portfolio Manager",
        "jobs.seniority": "Director", "jobs.industry": "Asset Management", "jobs.employer_name": "Temasek",
        "jobs.employer_size": "10000", "jobs.country": "Singapore",
        "composition.property": "50", "composition.listed_equities": "30",
        "composition.private_business": "0", "composition.cash": "20",
        "claims.declared_net_worth": "4800000", "claims.expected_aum": "2000000",
        "claims.pep_status": "None", "claims.wealth_countries": "Singapore",
        "sow.sow_declaration": "Salary and bonuses from 2012 onwards as a portfolio manager, plus rent.",
        "doc.file_name": "cv.txt", "doc.file_id": stored,
    }
    response = client.post("/client/new", data=form)
    assert response.status_code == 302, response.get_data(as_text=True)
    assert application.clients().load()[0]["supporting_documents"] == [
        {"file_name": "cv.txt", "file_id": stored}]


def test_the_new_client_form_has_no_date_box_because_assessments_are_dated_today(web):
    _, _, client = web
    page = client.get("/client/new").get_data(as_text=True)
    assert 'name="client.current_date"' not in page


# ----- a read failure is reported, never shown as "no records" ------------------------------------

def _damage(tmp_path, name):
    path = tmp_path / "local database" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"[{broken")
    return path


def test_the_home_page_says_the_client_database_cannot_be_read_and_shows_no_empty_list(web, tmp_path):
    _, _, client = web
    path = _damage(tmp_path, "sow_cases.json")
    page = client.get("/").get_data(as_text=True)
    assert "We can&#39;t load the client database right now. Please try again later." in page
    assert "No clients yet" not in page
    assert "damaged" not in page and "JSONDecodeError" not in page
    assert path.read_bytes() == b"[{broken"


def test_an_empty_client_list_still_says_no_clients_yet(web):
    _, _, client = web
    page = client.get("/").get_data(as_text=True)
    assert "No clients yet" in page and "cannot be read" not in page


def test_the_assessments_page_says_the_saved_assessments_cannot_be_read(web, tmp_path):
    _, _, client = web
    _damage(tmp_path, "ai_assessments.json")
    page = client.get("/assessments").get_data(as_text=True)
    assert "We can&#39;t load the saved assessments right now. Please try again later." in page
    assert "No assessments saved yet" not in page


def test_a_client_page_says_the_assessment_history_cannot_be_read(web, tmp_path):
    application, _, client = web
    application.clients().save(sample_case())
    _damage(tmp_path, "ai_assessments.json")
    page = client.get(f"/client/{sample_case()['client_ref']}").get_data(as_text=True)
    assert page.count("We can&#39;t load the saved assessments right now.") == 1
    assert "assessment history cannot be shown" in page


def test_opening_a_saved_assessment_from_a_damaged_file_goes_home_with_a_message(web, tmp_path):
    _, _, client = web
    _damage(tmp_path, "ai_assessments.json")
    reply = client.get("/assessment/A1")
    assert reply.status_code == 302 and reply.headers["Location"].endswith("/")
    assert App.ASSESSMENTS_UNAVAILABLE in _flashes(client)


def test_a_client_page_for_a_damaged_client_file_says_the_database_cannot_be_read(web, tmp_path):
    _, _, client = web
    _damage(tmp_path, "sow_cases.json")
    reply = client.get("/client/CL-1")
    assert reply.status_code == 302
    assert App.CLIENTS_UNAVAILABLE in _flashes(client)


def test_the_database_message_is_shown_once_after_going_home(web, tmp_path):
    _, _, client = web
    _damage(tmp_path, "sow_cases.json")
    page = client.get("/client/CL-1", follow_redirects=True).get_data(as_text=True)
    assert page.count("We can&#39;t load the client database right now.") == 1


def test_saving_a_new_client_into_a_damaged_file_says_it_was_not_saved_and_keeps_the_file(web, tmp_path):
    _, site, client = web
    path = _damage(tmp_path, "sow_cases.json")
    reply = client.post("/client/new", data=_form_fields(site, sample_case()))
    # the new reference can't be checked against the unreadable file, so the page says the database
    # can't be read (an error, never "the reference is free") and nothing is saved
    assert escape(App.CLIENTS_UNAVAILABLE).encode() in reply.data
    assert b"database connection" not in reply.data
    assert path.read_bytes() == b"[{broken"


def test_an_assessment_that_could_not_be_saved_says_so_and_leaves_the_client_unchanged(web, tmp_path):
    application, _, client = web
    record = sample_case()
    application.clients().save(record)
    before = application.clients().find(record["client_ref"])
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    path = _damage(tmp_path, "ai_assessments.json")
    started = client.post(f"/client/{record['client_ref']}/assess")
    job_id = started.headers["Location"].rsplit("/", 1)[-1]
    assert _wait_for(client, job_id)["status"] == "done"
    page = client.get(f"/assess/result/{job_id}").get_data(as_text=True)
    assert "This assessment was NOT saved" in page
    assert application.clients().find(record["client_ref"]) == before
    assert path.read_bytes() == b"[{broken"


def test_the_web_app_refuses_an_app_whose_settings_could_not_be_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    broken = App(_no_answer, root=str(tmp_path), data_folder=str(tmp_path / "data"))    # no config folder here
    with pytest.raises(RuntimeError, match="settings could not be loaded"):
        WebApp(broken)


def test_a_blocked_assessment_flashes_a_short_message_and_the_page_lists_the_items(web):
    application, _, client = web
    client_ref = _save_client_without_pep_answer(application)
    client.post(f"/client/{client_ref}/assess")
    flashes = _flashes(client)
    assert flashes == ["Complete the client record before assessing: see the list below."]
    page = client.get(f"/client/{client_ref}").get_data(as_text=True)
    assert "The PEP question is not answered" in page and "To complete or check" in page


def test_the_edit_form_shows_the_items_in_the_notes_box_not_the_errors_box(web):
    application, _, client = web
    client_ref = _save_client_without_pep_answer(application)
    page = client.get(f"/client/{client_ref}/edit").get_data(as_text=True)
    assert "The PEP question is not answered" in page
    assert "To complete or check" in page
    assert "issue found" not in page and "issues found" not in page and "fix the fields highlighted" not in page


def test_a_form_record_that_cannot_be_read_gives_a_plain_message_and_nothing_is_saved(web):
    application, site, _ = web
    bad = {**sample_case(), "claims": 5}                           # makes ClientRecord.from_dict raise AttributeError
    problems = site.save_form_record(bad)
    assert len(problems) == 1
    assert "could not be saved because some of the details are not in the expected layout" in problems[0]
    assert "AttributeError" not in problems[0]
    assert application.clients().load() == []


class _CapturingWebApp(WebApp):
    """A WebApp that keeps what the result page was given."""

    def __init__(self, application: App) -> None:
        super().__init__(application)
        self.shown_times: list[str] = []

    def show_report(self, record, report, assessed_at="", *args, **kwargs):
        self.shown_times.append(assessed_at)
        return super().show_report(record, report, assessed_at, *args, **kwargs)


def test_the_result_page_gets_the_time_the_assessment_was_saved_with(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(fake_ai.caller(), data_folder=str(tmp_path))
    site = _CapturingWebApp(application)
    client = site.flask().test_client()
    sign_in(client, application)
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    job_id = client.post(f"/client/{record['client_ref']}/assess").headers["Location"].rsplit("/", 1)[-1]
    assert _wait_for(client, job_id)["status"] == "done"
    assert client.get(f"/assess/result/{job_id}").status_code == 200
    saved = application.assessments().for_client(record["client_ref"])
    assert site.shown_times == [saved[0]["assessed_at"]] and saved[0]["assessed_at"]


class _BrokenAssessApp(App):
    """An App whose assessment breaks with a technical error, or stops at a critical step."""

    def __init__(self, *args, stop: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.stop = stop

    def assess(self, case, documents=None, on_step=None, show_failures=True, actor=App.TERMINAL):
        if self.stop:
            return None
        raise KeyError("benchmark")


@pytest.mark.parametrize("stop, expected", [(False, WebApp.ASSESSMENT_FAILED), (True, WebApp.ASSESSMENT_STOPPED)])
def test_a_failed_web_assessment_shows_a_plain_message_and_logs_the_real_error(tmp_path, monkeypatch, caplog,
                                                                              stop, expected):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = _BrokenAssessApp(fake_ai.caller(), data_folder=str(tmp_path), stop=stop)
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    record = sample_case()
    application.clients().save(record)
    job_id = client.post(f"/client/{record['client_ref']}/assess").headers["Location"].rsplit("/", 1)[-1]
    state = _wait_for(client, job_id)
    assert state == {**state, "status": "error", "error": expected}
    assert "KeyError" not in state["error"] and "benchmark" not in state["error"]
    if not stop:
        assert "KeyError" in caplog.text                       # the real error is in the log


def test_without_a_secret_key_each_start_gets_its_own_random_one(monkeypatch):
    # No App here: App would load the developer's own .env, which may set SECRET_KEY.
    monkeypatch.delenv("SECRET_KEY", raising=False)
    first, second = WebApp().flask().secret_key, WebApp().flask().secret_key
    assert first != second and len(first) == 64
    assert "dev-only" not in first


def test_the_secret_key_from_env_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setenv("SECRET_KEY", "a-key-for-this-test")
    assert WebApp(App(None, data_folder=str(tmp_path))).flask().secret_key == "a-key-for-this-test"


# ----- archive and restore -------------------------------------------------------------------

def _two_assessments(application):
    application.clients().save(sample_case())
    ref = sample_case()["client_ref"]
    for number in (1, 2):
        assert application.assessments().save({
            "assessment_id": f"A{number}", "client_ref": ref, "kind": "onboarding", "outcome": "PASSED",
            "assessed_at": f"2026-0{number}-05T10:30:00+00:00", "report": None})
    return ref


def test_archive_hides_an_assessment_and_says_it_is_not_deleted(web):
    application, _, client = web
    ref = _two_assessments(application)
    reply = client.post("/assessment/A1/archive")
    assert reply.status_code == 302 and reply.headers["Location"].endswith(f"/client/{ref}")
    assert "Assessment archived. It is hidden from the lists, not deleted." in _flashes(client)
    assert [a["assessment_id"] for a in application.all_assessments()] == ["A2"]
    assert len(application.assessments().load()) == 2


def test_the_archive_form_has_an_optional_reason_that_is_saved_and_shown(web):
    application, _, client = web
    ref = _two_assessments(application)
    page = client.get(f"/client/{ref}").get_data(as_text=True)
    assert 'name="reason"' in page and 'maxlength="200"' in page and "Reason (optional)" in page
    client.post("/assessment/A1/archive", data={"reason": "  typed the wrong net worth  "})
    assert "Assessment archived. It is hidden from the lists, not deleted." in _flashes(client)
    assert application.find_assessment("A1")["archive_log"][-1]["reason"] == "typed the wrong net worth"
    assert ": typed the wrong net worth." in client.get("/assessment/A1").get_data(as_text=True)
    page = client.get(f"/client/{ref}?archived=1").get_data(as_text=True)
    assert page.count('name="reason"') == 1                      # only the active row asks for a reason


def test_a_reason_with_html_is_shown_as_text_and_restore_ignores_a_reason(web):
    application, _, client = web
    _two_assessments(application)
    client.post("/assessment/A1/archive", data={"reason": "<script>alert(1)</script>"})
    page = client.get("/assessment/A1").get_data(as_text=True)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page and "<script>alert(1)</script>" not in page
    _flashes(client)
    client.post("/assessment/A1/restore", data={"reason": "should not be saved"})
    assert "Assessment restored." in _flashes(client)
    assert "reason" not in application.find_assessment("A1")["archive_log"][-1]


def test_a_bad_reason_archives_nothing_and_says_why(web):
    application, _, client = web
    ref = _two_assessments(application)
    reply = client.post("/assessment/A1/archive", data={"reason": "x" * 201})
    assert reply.headers["Location"].endswith(f"/client/{ref}")
    flashes = _flashes(client)
    assert any(f.startswith("Nothing was archived. The reason is too long: at most 200") for f in flashes)
    assert App.ASSESSMENTS_UNAVAILABLE not in flashes
    assert "archive_log" not in application.find_assessment("A1")


def test_archive_and_restore_need_post_and_an_assessment_that_exists(web):
    application, _, client = web
    _two_assessments(application)
    assert client.get("/assessment/A1/archive").status_code != 200          # a link cannot archive
    assert "archive_log" not in application.find_assessment("A1")
    assert client.post("/assessment/NOPE/archive").status_code == 404
    assert client.post("/assessment/NOPE/restore").status_code == 404


def test_archiving_twice_and_restoring_an_active_one_say_so(web):
    application, _, client = web
    _two_assessments(application)
    client.post("/assessment/A1/restore")
    assert "This assessment is not archived." in _flashes(client)
    client.post("/assessment/A1/archive")
    client.post("/assessment/A1/archive")
    assert "This assessment is already archived." in _flashes(client)
    assert len(application.find_assessment("A1")["archive_log"]) == 1


def test_restore_brings_it_back_and_keeps_the_archived_view_while_others_are_archived(web):
    application, _, client = web
    ref = _two_assessments(application)
    client.post("/assessment/A1/archive")
    client.post("/assessment/A2/archive")
    reply = client.post("/assessment/A1/restore")
    assert reply.headers["Location"].endswith(f"/client/{ref}?archived=1")
    assert "Assessment restored." in _flashes(client)
    reply = client.post("/assessment/A2/restore")
    assert reply.headers["Location"].endswith(f"/client/{ref}")


def test_a_damaged_archive_record_cannot_be_changed(web):
    application, _, client = web
    ref = _two_assessments(application)
    records = application.assessments().load()
    records[0]["archive_log"] = "broken"
    application.assessments()._write_all(records)
    for action in ("archive", "restore"):
        client.post(f"/assessment/A1/{action}")
        assert "This assessment's archive record is damaged, so it cannot be changed." in _flashes(client)
    assert application.assessments().find("A1")["archive_log"] == "broken"


def test_archiving_that_could_not_be_saved_says_so(web, monkeypatch):
    application, _, client = web
    _two_assessments(application)
    monkeypatch.setattr(application.assessments(), "_write_all", lambda records: False)
    client.post("/assessment/A1/archive")
    assert "The assessment was not archived because saving failed. Please try again later." in _flashes(client)
    assert "archive_log" not in application.find_assessment("A1")
    application.assessments().__dict__.pop("_write_all")
    client.post("/assessment/A1/archive")
    monkeypatch.setattr(application.assessments(), "_write_all", lambda records: False)
    client.post("/assessment/A1/restore")
    assert "The assessment was not restored because saving failed. Please try again later." in _flashes(client)


def test_archiving_from_a_damaged_file_goes_home_with_the_safe_message(web, tmp_path):
    _, _, client = web
    _damage(tmp_path, "ai_assessments.json")
    for action in ("archive", "restore"):
        reply = client.post(f"/assessment/A1/{action}")
        assert reply.status_code == 302 and reply.headers["Location"].endswith("/")
        assert App.ASSESSMENTS_UNAVAILABLE in _flashes(client)


def test_the_client_page_hides_archived_ones_and_can_show_them(web):
    application, _, client = web
    ref = _two_assessments(application)
    client.post("/assessment/A1/archive")
    page = client.get(f"/client/{ref}").get_data(as_text=True)
    assert "/assessment/A2/archive" in page and "/assessment/A1/" not in page
    assert "Show archived (1)" in page and "(archived)" not in page
    page = client.get(f"/client/{ref}?archived=1").get_data(as_text=True)
    assert "/assessment/A1/restore" in page and "/assessment/A2/archive" in page
    assert "(archived)" in page and "Hide archived" in page and "Show archived" not in page


def test_a_client_whose_assessments_are_all_archived_still_has_the_history_panel(web):
    application, _, client = web
    ref = _two_assessments(application)
    client.post("/assessment/A1/archive")
    client.post("/assessment/A2/archive")
    page = client.get(f"/client/{ref}").get_data(as_text=True)
    assert "Assessment History" in page and "Show archived (2)" in page


def test_a_damaged_archive_record_is_marked_and_has_no_button(web):
    application, _, client = web
    ref = _two_assessments(application)
    records = application.assessments().load()
    records[0]["archive_log"] = [{"action": "bogus"}]
    application.assessments()._write_all(records)
    page = client.get(f"/client/{ref}?archived=1").get_data(as_text=True)
    assert "(archive state unreadable)" in page
    assert "/assessment/A1/archive" not in page and "/assessment/A1/restore" not in page
    assert "/assessment/A2/archive" in page


def test_an_archived_assessment_page_has_a_banner_with_the_date_and_reason(web):
    application, _, client = web
    _two_assessments(application)
    assert application.assessments().archive("A1", "entered twice", "Shareen") == App.ARCHIVE_CHANGED
    page = client.get("/assessment/A1").get_data(as_text=True)
    assert "This assessment is archived (since " in page and ": entered twice. It is hidden from the lists" in page
    assert "The client's current outcome is not changed." in page
    assert "/assessment/A1/restore" in page
    assert "archived" not in client.get("/assessment/A2").get_data(as_text=True).split("<h1>")[1]


def test_a_damaged_archive_record_gives_a_banner_and_no_button_on_the_assessment_page(web):
    application, _, client = web
    _two_assessments(application)
    records = application.assessments().load()
    records[0]["archive_log"] = "broken"
    application.assessments()._write_all(records)
    page = client.get("/assessment/A1").get_data(as_text=True)
    assert "This assessment's archive record is damaged, so it cannot be archived or restored." in page
    assert "/assessment/A1/restore" not in page and "/assessment/A1/archive" not in page


def test_an_archive_line_with_a_time_that_is_not_text_gives_the_damaged_banner_not_an_error(web):
    application, _, client = web
    _two_assessments(application)
    records = application.assessments().load()
    records[0]["archive_log"] = [{"action": "archived", "at": 12345}]
    application.assessments()._write_all(records)
    reply = client.get("/assessment/A1")
    assert reply.status_code == 200
    assert "This assessment's archive record is damaged" in reply.get_data(as_text=True)


def test_old_records_without_an_id_each_show_their_own_archive_state(web):
    application, _, client = web
    application.clients().save(sample_case())
    ref = sample_case()["client_ref"]
    application.assessments()._write_all([
        {"client_ref": ref, "kind": "onboarding", "outcome": "PASSED", "assessed_at": "2026-02-05T10:30:00+00:00",
         "archive_log": [{"action": "archived", "at": "2026-03-01T00:00:00+00:00"}]},
        {"client_ref": ref, "kind": "onboarding", "outcome": "SERIOUS_RISK", "assessed_at": "2026-01-05T10:30:00+00:00"}])
    page = client.get(f"/client/{ref}").get_data(as_text=True)
    assert "SERIOUS RISK" in page and "Show archived (1)" in page and "(archived)" not in page
    page = client.get(f"/client/{ref}?archived=1").get_data(as_text=True)
    assert page.count("(archived)") == 1


def test_a_restore_that_worked_is_reported_even_if_the_list_cannot_be_read_afterwards(web, monkeypatch):
    application, _, client = web
    ref = _two_assessments(application)
    client.post("/assessment/A1/archive")
    _flashes(client)

    def unreadable(client_ref, include_archived=False):
        raise ValueError("the file is damaged")

    monkeypatch.setattr(application, "client_assessments", unreadable)
    reply = client.post("/assessment/A1/restore")
    assert reply.headers["Location"].endswith(f"/client/{ref}")
    flashes = _flashes(client)
    assert "Assessment restored." in flashes and App.ASSESSMENTS_UNAVAILABLE not in flashes
    assert application.find_assessment("A1")["archive_log"][-1]["action"] == "restored"


def test_an_assessment_page_uses_the_name_the_client_had_when_it_was_assessed(web):
    application, _, client = web
    ref = _two_assessments(application)
    records = application.assessments().load()
    records[0]["case"] = {"name": "Old Name Pte"}
    application.assessments()._write_all(records)
    assert "Old Name Pte" in client.get("/assessment/A1").get_data(as_text=True)
    assert "Old Name Pte" not in client.get("/assessment/A2").get_data(as_text=True)


def test_the_assessments_page_hides_archived_ones_and_says_when_all_are_archived(web):
    application, _, client = web
    _two_assessments(application)
    client.post("/assessment/A1/archive")
    page = client.get("/assessments").get_data(as_text=True)
    assert "/assessment/A2" in page and "/assessment/A1" not in page
    client.post("/assessment/A2/archive")
    page = client.get("/assessments").get_data(as_text=True)
    assert "All 2 assessment(s) are archived." in page and "No assessments saved yet" not in page


# ----- sign-in, the gate and the roles -------------------------------------------------------

def _anonymous(tmp_path, monkeypatch, ai=_no_answer):
    """A WebApp with nobody signed in: (application, site, browser)."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(ai, data_folder=str(tmp_path))
    site = WebApp(application)
    site.flask().config["TESTING"] = True
    return application, site, site.flask().test_client()


def _events(application):
    from app.model.audit_filter import AuditFilter
    return list(reversed(application.audit_log(AuditFilter(days=0))[0]))


def test_nobody_signed_in_is_sent_to_the_sign_in_page_from_every_route(tmp_path, monkeypatch):
    _, site, browser = _anonymous(tmp_path, monkeypatch)
    routes = [rule for rule in site.flask().url_map.iter_rules() if rule.endpoint not in ("signin", "static")]
    assert routes
    for rule in routes:
        url = re.sub(r"<[^>]+>", "x", rule.rule)
        for method in sorted(rule.methods & {"GET", "POST"}):
            reply = browser.open(url, method=method)
            if rule.endpoint == "assess_poll":
                assert reply.status_code == 401 and reply.get_json()["status"] == "error", url
            else:
                assert reply.status_code == 302 and reply.headers["Location"].endswith("/signin"), (method, url)
    assert browser.get("/no/such/page").status_code == 302


def test_the_sign_in_page_lists_every_account_with_its_role(tmp_path, monkeypatch):
    application, _, browser = _anonymous(tmp_path, monkeypatch)
    page = browser.get("/signin").get_data(as_text=True)
    for account in application.accounts():
        assert account.name in page and account.email in page and f"({account.role})" in page
    assert "Signed in as" not in page


def test_choosing_an_officer_signs_in_records_it_and_goes_home(tmp_path, monkeypatch):
    application, _, browser = _anonymous(tmp_path, monkeypatch)
    officer = account_with_role(application, "officer")
    reply = browser.post("/signin", data={"email": officer.email})
    assert reply.status_code == 302 and reply.headers["Location"].endswith("/")
    with browser.session_transaction() as session:
        assert dict(session) == {"account": officer.email}
    page = browser.get("/").get_data(as_text=True)
    assert f"Signed in as {officer.name} (officer)" in page and "Sign out" in page
    assert "Audit" not in page.split("<main>")[0]
    [event] = _events(application)
    assert (event.action, event.actor) == ("signed_in", officer.name)


def test_signing_in_as_the_admin_hides_the_officer_buttons(tmp_path, monkeypatch):
    application, _, browser = _anonymous(tmp_path, monkeypatch)
    admin = account_with_role(application, "admin")
    assert browser.post("/signin", data={"email": admin.email}).status_code == 302
    page = browser.get("/").get_data(as_text=True)
    assert f"Signed in as {admin.name} (admin)" in page
    assert "New client" not in page and "Sync to Cloud" not in page


def test_an_unknown_or_missing_account_shows_the_page_again_and_signs_nobody_in(tmp_path, monkeypatch):
    application, _, browser = _anonymous(tmp_path, monkeypatch)
    for data in ({"email": "nobody@example.com"}, {"email": ""}, {}):
        reply = browser.post("/signin", data=data)
        assert reply.status_code == 200
        assert "Please choose one of the listed accounts." in reply.get_data(as_text=True)
    with browser.session_transaction() as session:
        assert "account" not in session
    assert _events(application) == []


def test_a_signed_in_visitor_who_opens_the_sign_in_page_goes_home(web):
    _, _, browser = web
    reply = browser.get("/signin")
    assert reply.status_code == 302 and reply.headers["Location"].endswith("/")


def test_an_email_that_is_no_longer_configured_counts_as_signed_out(web):
    _, _, browser = web
    with browser.session_transaction() as session:
        session["account"] = "gone@orbit.local"
    assert browser.get("/").headers["Location"].endswith("/signin")
    with browser.session_transaction() as session:
        session["account"] = 5
    assert browser.get("/").headers["Location"].endswith("/signin")


def test_signing_out_records_it_empties_the_session_and_closes_the_gate(web):
    application, _, browser = web
    reply = browser.post("/signout")
    assert reply.status_code == 302 and reply.headers["Location"].endswith("/signin")
    with browser.session_transaction() as session:
        assert "account" not in session
    assert browser.get("/").headers["Location"].endswith("/signin")
    assert [event.action for event in _events(application)] == ["signed_out"]


def test_signing_out_needs_a_post_and_a_signed_in_visitor(web, tmp_path, monkeypatch):
    _, _, browser = web
    assert browser.get("/signout").status_code in (405, 500)     # the app turns every error into its error page
    _, _, stranger = _anonymous(tmp_path / "other", monkeypatch)
    assert stranger.post("/signout").headers["Location"].endswith("/signin")


def test_the_poll_of_a_signed_out_visitor_is_a_401_not_a_redirect(tmp_path, monkeypatch):
    _, _, browser = _anonymous(tmp_path, monkeypatch)
    reply = browser.get("/assess/poll/anything")
    assert reply.status_code == 401 and reply.get_json() == {"status": "error", "error": "Please sign in again."}


def test_the_session_holds_only_the_email_and_the_cookie_is_not_readable_by_scripts(tmp_path, monkeypatch):
    application, _, browser = _anonymous(tmp_path, monkeypatch)
    officer = account_with_role(application)
    reply = browser.post("/signin", data={"email": officer.email})
    cookie = reply.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def _admin_web(web):
    application, site, browser = web
    sign_in(browser, application, "admin")
    return application, site, browser


def test_the_admin_may_view_clients_and_assessments_and_download_documents(web):
    application, _, browser = _admin_web(web)
    ref = _two_assessments(application)
    assert browser.get("/").status_code == 200
    page = browser.get(f"/client/{ref}")
    assert page.status_code == 200
    assert browser.get("/assessments").status_code == 200
    assert browser.get("/assessment/A1").status_code == 200
    body = page.get_data(as_text=True)
    for hidden in ("Run Assessment", ">Edit<", "Upload", ">Archive<", "Add documents"):
        assert hidden not in body, hidden


def test_the_admin_is_refused_on_every_write_route_and_each_refusal_is_recorded(web):
    application, _, browser = _admin_web(web)
    ref = _two_assessments(application)
    admin = account_with_role(application, "admin")
    before = application.clients().find(ref)
    writes = [("get", "/client/new"), ("post", "/client/new"), ("post", "/client/new/autofill"),
              ("get", f"/client/{ref}/edit"), ("post", f"/client/{ref}/edit"),
              ("post", f"/client/{ref}/autofill"), ("post", f"/client/{ref}/documents"),
              ("post", f"/client/{ref}/assess"), ("post", "/assessment/A1/archive"),
              ("post", "/assessment/A1/restore"), ("post", "/sync")]
    for method, url in writes:
        reply = getattr(browser, method)(url)
        assert reply.status_code == 302, url
        assert reply.headers["Location"].endswith(f"/client/{ref}" if f"/client/{ref}" in url else "/"), url
        assert "The admin account can only review the audit log." in _flashes(browser), url
        browser.get("/")                                             # shows, and so clears, the message
    refused = [event for event in _events(application) if event.action == "access_refused"]
    assert len(refused) == len({event.details["what"] for event in refused}) == 9    # a repeat within a minute is not written again
    assert {event.actor for event in refused} == {admin.name}
    assert "archiving an assessment" in {event.details["what"] for event in refused}
    assert application.clients().find(ref) == before
    assert application.find_assessment("A1").get("archive_log") is None
    assert application.assessments().load()[0].get("archive_log") is None


def test_a_client_saved_on_the_web_is_recorded_under_the_signed_in_name(web):
    application, site, browser = web
    officer = account_with_role(application)
    assert browser.post("/client/new", data=_form_fields(site, sample_case())).status_code == 302
    [event] = _events(application)
    assert (event.action, event.actor) == ("client_created", officer.name)


def test_every_web_write_passes_the_signed_in_name_as_the_actor(web):
    application, site, browser = web
    officer = account_with_role(application)
    ref = _two_assessments(application)
    fields = _form_fields(site, sample_case())
    fields["client.name"] = "Daniel K. Tan"
    browser.post(f"/client/{ref}/edit", data=fields)
    browser.post(f"/client/{ref}/documents", content_type="multipart/form-data",
                 data={"files": (io.BytesIO(b"payslip"), "payslip.txt")})
    file_id = application.find_client(ref).documents()[0]["file_id"]
    assert browser.get(f"/client/{ref}/documents/{file_id}").status_code == 200
    browser.post("/assessment/A1/archive", data={"reason": "duplicate"})
    browser.post("/assessment/A1/restore")
    browser.post("/sync")
    events = _events(application)
    assert [event.action for event in events] == [
        "client_edited", "document_uploaded", "client_edited", "document_downloaded",
        "assessment_archived", "assessment_restored", "cloud_sync"]
    assert {event.actor for event in events} == {officer.name}
    assert [event.client_ref for event in events[1:4]] == [ref] * 3
    assert [entry["by"] for entry in application.find_assessment("A1")["archive_log"]] == [officer.name] * 2


def test_reading_documents_on_the_web_records_the_reading_and_the_uploads(tmp_path, monkeypatch):
    application = App(fake_ai.caller(documents_reply=AI_READING), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    officer = sign_in(client, application)
    client.post("/client/new/autofill", content_type="multipart/form-data", data={
        "autofill_files": (io.BytesIO(b"Daniel Tan, Portfolio Manager"), "cv.txt")})
    assert [(event.action, event.actor) for event in _events(application)] == [
        ("document_uploaded", officer.name), ("autofill_used", officer.name)]


def test_a_web_assessment_is_recorded_under_the_name_taken_in_the_request(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(fake_ai.caller(), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    officer = sign_in(client, application)
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    job_id = client.post(f"/client/{record['client_ref']}/assess").headers["Location"].rsplit("/", 1)[-1]
    assert _wait_for(client, job_id)["status"] == "done"
    assert [(event.action, event.actor) for event in _events(application)] == [("assessment_run", officer.name)]
    assert "could not be written" not in client.get(f"/assess/result/{job_id}").get_data(as_text=True)


def test_an_audit_line_that_could_not_be_written_is_flashed_after_a_web_save(web, tmp_path):
    application, site, browser = web
    break_audit(tmp_path)
    assert browser.post("/client/new", data=_form_fields(site, sample_case())).status_code == 302
    assert App.AUDIT_NOT_WRITTEN in _flashes(browser)
    assert len(application.clients().load()) == 1


def test_an_audit_failure_in_the_assessment_job_is_shown_on_the_result_page(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(fake_ai.caller(), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    break_audit(tmp_path)
    job_id = client.post(f"/client/{record['client_ref']}/assess").headers["Location"].rsplit("/", 1)[-1]
    assert _wait_for(client, job_id)["status"] == "done"
    page = client.get(f"/assess/result/{job_id}").get_data(as_text=True)
    assert App.AUDIT_NOT_WRITTEN in page
    assert len(application.assessments().load()) == 1


def test_a_stopped_web_assessment_whose_audit_line_failed_says_so_in_its_message(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = _StopAssessApp(fake_ai.caller(), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    record = sample_case()
    application.clients().save(record)
    break_audit(tmp_path)
    job_id = client.post(f"/client/{record['client_ref']}/assess").headers["Location"].rsplit("/", 1)[-1]
    state = _wait_for(client, job_id)
    assert state["status"] == "error"
    assert state["error"] == f"{WebApp.ASSESSMENT_STOPPED} {App.AUDIT_LINE_NOT_WRITTEN}"


class _StopAssessApp(App):
    """An App whose assessment stops at once (as if a critical step failed) and, in the test, whose
    audit log cannot be written."""

    def assess(self, case, documents=None, on_step=None, show_failures=True, actor=App.TERMINAL):
        self.refused(actor, "forcing an audit line")               # in the test this fails, so the thread's flag is True
        return None


# ----- the audit log page ----------------------------------------------------------------------

def _put_events(application, count: int, actor: str = "Shareen") -> None:
    for number in range(count):          # a different text each time: the same refusal is written only once a minute
        application.refused(actor, f"opening the audit log ({number})")


def test_the_admin_signing_in_lands_on_the_audit_log(tmp_path, monkeypatch):
    application, _, browser = _anonymous(tmp_path, monkeypatch)
    admin = account_with_role(application, "admin")
    reply = browser.post("/signin", data={"email": admin.email})
    assert reply.headers["Location"].endswith("/audit")
    page = browser.get("/audit")
    assert page.status_code == 200 and ">Audit</a>" in page.get_data(as_text=True)
    assert "Signed in as" in page.get_data(as_text=True)


def test_an_officer_opening_the_audit_log_gets_a_403_page_and_the_refusal_is_recorded(web):
    application, _, browser = web
    officer = account_with_role(application)
    for method, url in (("get", "/audit"), ("get", "/audit?days=all"), ("post", "/audit/verify")):
        reply = getattr(browser, method)(url)
        assert reply.status_code == 403, url
        assert "Only the admin can open the audit log." in reply.get_data(as_text=True)
    refused = [event for event in _events(application) if event.action == "access_refused"]
    assert len(refused) == 1 and {event.actor for event in refused} == {officer.name}     # repeats within a minute: one line
    assert refused[0].details == {"what": "opening the audit log"}
    assert ">Audit</a>" not in browser.get("/").get_data(as_text=True)


def test_an_empty_log_says_no_activity_recorded_yet(web):
    _, _, browser = _admin_web(web)
    page = browser.get("/audit").get_data(as_text=True)
    assert "No activity recorded yet." in page and "<table" not in page


def test_the_log_shows_time_in_singapore_actor_label_client_summary_and_result(web):
    application, site, browser = _admin_web(web)
    application.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    ref = sample_case()["client_ref"]
    page = browser.get("/audit").get_data(as_text=True)
    event = _events(application)[0]
    assert site.singapore_time(event.at) in page
    for shown in ("Shareen", "Client created", f"Created client {ref}", f'href="/client/{ref}"', "badge-pass"):
        assert shown in page, shown


def test_singapore_time_is_eight_hours_ahead_and_odd_text_is_left_alone(web):
    _, site, _ = web
    assert site.singapore_time("2026-11-16T06:02:11Z") == "16 Nov 2026 14:02"
    assert site.singapore_time("2026-12-31T20:30:00Z") == "1 Jan 2027 04:30"
    assert site.singapore_time("not a time") == "not a time" and site.singapore_time(None) == "None"


def test_an_edit_row_lists_before_and_after_in_a_details_block_and_escapes_them(web):
    application, _, browser = _admin_web(web)
    record = ClientRecord.from_dict(sample_case())
    application.save_client(record, "Shareen")
    application.save_client(ClientRecord.from_dict({**record.to_dict(), "name": "<script>alert(1)</script>"}), "Adrian")
    page = browser.get("/audit").get_data(as_text=True)
    assert "<details>" in page and "<code>name</code>" in page and "&rarr;" in page
    assert sample_case()["name"] in page
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_the_filters_narrow_the_log_and_show_a_chip_that_removes_each_one(web):
    application, _, browser = _admin_web(web)
    application.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    application.sign_in("adrian@orbit.local")
    application.sync_to_cloud("Shareen")
    page = browser.get("/audit?actor=Adrian&group=Sign-in&result=ok&days=30&client_ref=").get_data(as_text=True)
    assert "Signed in</td>" in page and "Cloud sync</td>" not in page and "Client created</td>" not in page
    for label in ("Period: Last 30 days", "Officer: Adrian", "Group: Sign-in", "Result: OK"):
        assert label in page, label
    assert 'href="/audit?actor=Adrian&amp;group=Sign-in&amp;result=ok"' in page          # the Period chip's remove link
    assert 'aria-label="Remove the Officer filter"' in page
    assert re.search(r'<option value="30" selected>', page) and re.search(r"<option selected>Adrian</option>", page)
    assert "1 event &middot; page 1 of 1" in page


def test_a_client_filter_matches_one_clients_events_whatever_the_case(web):
    application, _, browser = _admin_web(web)
    ref = sample_case()["client_ref"]
    application.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    application.sync_to_cloud("Shareen")
    page = browser.get(f"/audit?client_ref={ref.lower()}").get_data(as_text=True)
    assert "Client created</td>" in page and "Cloud sync</td>" not in page


def test_filters_that_match_nothing_say_so_instead_of_no_activity_yet(web):
    application, _, browser = _admin_web(web)
    application.sync_to_cloud("Shareen")
    page = browser.get("/audit?actor=Nobody").get_data(as_text=True)
    assert "No activity matches these filters." in page and "No activity recorded yet." not in page


def test_bad_filter_values_fall_back_and_are_explained_on_the_page(web):
    application, _, browser = _admin_web(web)
    application.sync_to_cloud("Shareen")
    page = browser.get("/audit?days=999&group=Nonsense&result=maybe&page=zero")
    assert page.status_code == 200
    text = html.unescape(page.get_data(as_text=True))
    for problem in ("'days' must be one of 1, 7, 30, 90 or all", "'group' must be one of Sign-in",
                    "'result' must be ok or failed", "'page' must be a whole number"):
        assert problem in text, problem
    assert "Cloud sync</td>" in text                          # the defaults still show the log


def test_the_log_is_paged_fifty_to_a_page_newest_first(web):
    application, _, browser = _admin_web(web)
    _put_events(application, 52)
    application.sync_to_cloud("Adrian")                       # the newest
    first = browser.get("/audit").get_data(as_text=True)
    assert first.count("Access refused</td>") == 49 and first.index("Cloud sync</td>") < first.index("Access refused</td>")
    assert "53 events &middot; page 1 of 2" in first and "Older &rarr;" in first and "Newer" not in first
    second = browser.get("/audit?page=2").get_data(as_text=True)
    assert second.count("Access refused</td>") == 3 and "page 2 of 2" in second
    assert "Newer" in second and "Older" not in second
    assert "page 2 of 2" in browser.get("/audit?page=99").get_data(as_text=True)      # past the end shows the last page
    assert 'href="/audit?page=2"' in first


def test_verify_log_reports_an_untouched_log_as_a_success_and_records_it(web):
    application, _, browser = _admin_web(web)
    _put_events(application, 2)
    admin = account_with_role(application, "admin")
    reply = browser.post("/audit/verify")
    assert reply.status_code == 200
    page = reply.get_data(as_text=True)
    assert 'class="msg msg-success"' in page and "No changes found in the 2 entries." in page
    assert "Changed outside the app" not in page
    last = _events(application)[-1]
    assert (last.action, last.actor, last.result) == ("audit_verified", admin.name, "ok")


def test_verify_log_after_the_file_was_changed_shows_a_warning(web, tmp_path):
    application, _, browser = _admin_web(web)
    _put_events(application, 3)
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[1]["actor"] = "Somebody Else"
    path.write_text(json.dumps(rows), encoding="utf-8")
    page = browser.post("/audit/verify").get_data(as_text=True)
    assert 'class="msg msg-warning"' in page and "changed outside the app" in page
    assert _events(application)[-1].result == "failed"
    rows_html = page.split("<tbody>")[1].split("</tbody>")[0].split("<tr>")[1:]
    marked = [row for row in rows_html if "Changed outside the app" in row]
    assert len(marked) == 1 and "Somebody Else" in marked[0]               # only the tampered row is marked
    assert "Changed outside the app" not in browser.get("/audit").get_data(as_text=True)


def test_verify_keeps_the_filters_of_the_page_it_was_pressed_on_and_marks_a_row_on_it(web, tmp_path):
    application, _, browser = _admin_web(web)
    _put_events(application, 2, "Shareen")
    _put_events(application, 2, "Adrian")
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[3]["actor"] = "Adrian "                                           # still Adrian, but the hash no longer fits
    rows[3]["details"] = {"what": "changed"}
    path.write_text(json.dumps(rows), encoding="utf-8")
    page = browser.get("/audit?actor=Adrian").get_data(as_text=True)
    assert 'action="/audit/verify?actor=Adrian"' in page
    shown = browser.post("/audit/verify?actor=Adrian").get_data(as_text=True)
    assert "Officer: Adrian" in shown
    assert shown.count("Changed outside the app") == 1
    assert "Shareen</td>" not in shown


def test_an_unreadable_audit_log_says_so_and_shows_no_table(web, tmp_path):
    application, _, browser = _admin_web(web)
    application.sync_to_cloud("Shareen")
    path = tmp_path / "local database" / "audit_log.json"
    path.unlink()
    path.mkdir()                                              # cannot be read as a file
    page = browser.get("/audit")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert html.unescape(text).count(App.AUDIT_UNAVAILABLE) == 1 and "<table" not in text and "No activity" not in text
    browser.post("/audit/verify")
    assert App.AUDIT_UNAVAILABLE in _flashes(browser)


def test_the_filter_form_offers_every_account_the_terminal_and_every_group(web):
    application, _, browser = _admin_web(web)
    page = browser.get("/audit").get_data(as_text=True)
    for account in application.accounts():
        assert f"<option>{account.name}</option>" in page
    assert "<option>terminal</option>" in page
    for group in ("Sign-in", "Client", "Documents", "Assessment", "System"):
        assert f"<option>{group}</option>" in page
    for choice in ("all", "1", "7", "30", "90"):
        assert f'<option value="{choice}"' in page


def _add_unreadable_rows(tmp_path, count):
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    rows += [{"action": "cloud_sync", "actor": "Shareen"} for _ in range(count)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_the_audit_page_warns_when_some_entries_cannot_be_read(web, tmp_path):
    application, _, browser = _admin_web(web)
    _put_events(application, 2)
    assert "can't be read" not in browser.get("/audit").get_data(as_text=True)
    _add_unreadable_rows(tmp_path, 1)
    page = html.unescape(browser.get("/audit").get_data(as_text=True))
    assert "1 entry in the audit log can't be read. Use Verify log to see which." in page
    assert "<table" in page                                          # the readable entries are still listed
    _add_unreadable_rows(tmp_path, 1)
    page = html.unescape(browser.get("/audit?actor=Nobody").get_data(as_text=True))
    assert "2 entries in the audit log can't be read. Use Verify log to see which." in page


def test_a_log_where_every_entry_is_unreadable_does_not_say_no_activity_recorded(web, tmp_path):
    _, _, browser = _admin_web(web)
    _add_unreadable_rows(tmp_path, 2)
    page = html.unescape(browser.get("/audit").get_data(as_text=True))
    assert "2 entries in the audit log can't be read." in page
    assert "No activity recorded yet." not in page and "<table" not in page


def test_the_client_history_warns_both_roles_when_entries_cannot_be_read(web, tmp_path):
    application, _, browser = web
    ref = sample_case()["client_ref"]
    application.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    for role in ("officer", "admin"):
        sign_in(browser, application, role)
        assert "can't be read" not in browser.get(f"/client/{ref}").get_data(as_text=True)
    _add_unreadable_rows(tmp_path, 1)
    for role in ("officer", "admin"):
        sign_in(browser, application, role)
        history = html.unescape(browser.get(f"/client/{ref}").get_data(as_text=True))
        history = history[history.index('id="history"'):]
        assert "1 entry in the audit log can't be read, so this history may be incomplete." in history
        assert "Client created" in history
    _add_unreadable_rows(tmp_path, 2)
    page = html.unescape(browser.get(f"/client/{ref}").get_data(as_text=True))
    assert "3 entries in the audit log can't be read, so this history may be incomplete." in page


# ----- the client's History ---------------------------------------------------------------------

def test_the_client_page_shows_its_history_newest_first_to_both_roles(web):
    application, _, browser = web
    ref = sample_case()["client_ref"]
    record = ClientRecord.from_dict(sample_case())
    application.save_client(record, "Shareen")
    application.save_client(ClientRecord.from_dict({**record.to_dict(), "name": "Daniel K. Tan"}), "Adrian")
    application.sync_to_cloud("Shareen")                               # not about this client
    for role in ("officer", "admin"):
        sign_in(browser, application, role)
        page = browser.get(f"/client/{ref}").get_data(as_text=True)
        history = page[page.index('id="history"'):]
        assert "Client edited" in history and "Client created" in history and "Cloud sync" not in history
        assert history.index("Client edited") < history.index("Client created")
        assert "Adrian" in history and "Shareen" in history and "<th>Client</th>" not in history
        assert "<code>name</code>" in history and "Daniel K. Tan" in history


def test_a_client_with_no_events_says_no_history_recorded_yet(web):
    application, _, browser = web
    application.clients().save(sample_case())                           # saved behind App's back: no event
    page = browser.get(f"/client/{sample_case()['client_ref']}").get_data(as_text=True)
    assert "No history recorded yet." in page


def test_only_the_newest_fifty_events_of_a_client_are_shown(web):
    application, _, browser = web
    ref = sample_case()["client_ref"]
    application.clients().save(sample_case())
    for number in range(55):
        application.upload_document("/no/such/file", "Shareen", ref)
    page = browser.get(f"/client/{ref}").get_data(as_text=True)
    assert page.count("<tr>") >= 50 and "Showing the latest 50 of 55 events." in page


def test_an_unreadable_audit_log_shows_the_message_in_history_and_the_rest_of_the_page_still_renders(web, tmp_path):
    application, _, browser = web
    application.clients().save(sample_case())
    path = tmp_path / "local database" / "audit_log.json"
    path.mkdir(parents=True)
    page = browser.get(f"/client/{sample_case()['client_ref']}")
    text = html.unescape(page.get_data(as_text=True))
    assert page.status_code == 200
    history = text[text.index('id="history"'):]
    assert App.AUDIT_UNAVAILABLE in history[:400] and "No history recorded yet." not in text
    assert sample_case()["name"] in text and "Supporting documents" in text


def test_an_archived_assessment_shows_who_archived_it(web):
    application, _, browser = web
    ref = _two_assessments(application)
    officer = account_with_role(application)
    browser.post("/assessment/A1/archive", data={"reason": "duplicate"})
    page = browser.get(f"/client/{ref}?archived=1").get_data(as_text=True)
    assert f"(archived) &middot; by {officer.name}" in page
    banner = browser.get("/assessment/A1").get_data(as_text=True)
    assert f"Archived by: {officer.name}." in banner


def test_an_old_archive_line_without_by_says_it_was_not_recorded(web):
    application, _, browser = web
    ref = _two_assessments(application)
    rows = application.assessments().load()
    rows[0]["archive_log"] = [{"action": "archived", "at": "2026-01-06T00:00:00+00:00", "reason": "old"}]
    assert application.assessments()._write_all(rows)
    page = browser.get(f"/client/{ref}?archived=1").get_data(as_text=True)
    assert "Not recorded (before sign-in existed)" in page
    assert "Archived by: Not recorded (before sign-in existed)." in browser.get("/assessment/A1").get_data(as_text=True)


# ----- web errors keep their own status ----------------------------------------------------------

def test_a_wrong_method_is_a_405_not_a_500(web):
    _, _, browser = web
    for method, url in (("get", "/signout"), ("put", "/"), ("get", "/sync"), ("delete", "/audit/verify")):
        reply = getattr(browser, method)(url)
        assert reply.status_code == 405, (method, url)
        assert "Back to home" in reply.get_data(as_text=True)


def test_an_upload_that_is_too_large_is_a_413_with_the_error_page(web):
    _, site, browser = web
    site.flask().config["MAX_CONTENT_LENGTH"] = 100
    reply = browser.post("/client/new/autofill", content_type="multipart/form-data",
                         data={"autofill_files": (io.BytesIO(b"x" * 5000), "big.txt")})
    assert reply.status_code == 413
    assert "Back to home" in reply.get_data(as_text=True)


def test_an_unknown_page_is_still_a_404_and_a_real_error_is_still_a_500(web, monkeypatch):
    application, _, browser = web
    assert browser.get("/no/such/page").status_code == 404
    monkeypatch.setattr(application, "all_clients", lambda: 1 / 0)
    reply = browser.get("/")
    assert reply.status_code == 500 and "Something went wrong" in reply.get_data(as_text=True)


def test_a_hand_added_row_is_on_neither_the_log_nor_the_history_but_verify_reports_it(web, tmp_path):
    application, _, browser = web
    ref = sample_case()["client_ref"]
    application.save_client(ClientRecord.from_dict(sample_case()), "Shareen")
    path = tmp_path / "local database" / "audit_log.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows.append({"action": "client_edited", "actor": "Mallory", "client_ref": ref, "details": {"changes": []}})
    path.write_text(json.dumps(rows), encoding="utf-8")
    assert "Mallory" not in browser.get(f"/client/{ref}").get_data(as_text=True)
    sign_in(browser, application, "admin")
    assert "Mallory" not in browser.get("/audit?days=all").get_data(as_text=True)
    assert "changed outside the app" in html.unescape(browser.post("/audit/verify").get_data(as_text=True))


def test_auto_filling_an_existing_client_shows_in_that_clients_history(tmp_path, monkeypatch):
    application = App(fake_ai.caller(documents_reply=AI_READING), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    ref = sample_case()["client_ref"]
    application.clients().save(sample_case())
    client.post(f"/client/{ref}/autofill", content_type="multipart/form-data", data={
        "autofill_files": (io.BytesIO(b"Daniel Tan, Portfolio Manager"), "cv.txt")})
    assert {event.action for event in application.audit_trail(ref)[0]} == {"document_uploaded", "autofill_used"}
    page = client.get(f"/client/{ref}").get_data(as_text=True)
    assert "Used document auto-fill" in page


def test_the_result_page_says_when_the_outcome_could_not_be_written_to_the_client(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(fake_ai.caller(), data_folder=str(tmp_path))
    client = WebApp(application).flask().test_client()
    sign_in(client, application)
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(ClientRecord.from_dict(record))
    fake_services.save_forecast_replies(application.response_cache(), case)
    monkeypatch.setattr(application.clients(), "save", lambda data: False)      # only the outcome write uses it here
    job_id = client.post(f"/client/{record['client_ref']}/assess").headers["Location"].rsplit("/", 1)[-1]
    assert _wait_for(client, job_id)["status"] == "done"
    page = html.unescape(client.get(f"/assess/result/{job_id}").get_data(as_text=True))
    assert App.OUTCOME_NOT_UPDATED in page and "NOT saved" not in page
    assert len(application.assessments().load()) == 1


# ----- which audit message the web shows ----------------------------------------------------------

def test_only_actions_that_saved_something_flash_saved_but(web, tmp_path):
    application, site, browser = web
    ref = _two_assessments(application)
    break_audit(tmp_path)
    browser.post(f"/client/{ref}/edit", data={**_form_fields(site, sample_case()), "client.name": "Daniel K. Tan"})
    assert App.AUDIT_NOT_WRITTEN in _flashes(browser)                         # the edit was saved
    browser.get("/")
    browser.post("/assessment/A1/archive")
    assert App.AUDIT_NOT_WRITTEN in _flashes(browser)                         # the archive was saved
    browser.get("/")
    browser.post("/sync")
    flashes = _flashes(browser)
    assert App.AUDIT_LINE_NOT_WRITTEN in flashes and App.AUDIT_NOT_WRITTEN not in flashes
    browser.get("/")
    browser.post("/signout")
    assert App.AUDIT_LINE_NOT_WRITTEN in _flashes(browser)


def test_a_refusal_a_sign_in_a_check_and_a_download_flash_only_that_the_action_was_not_written(tmp_path, monkeypatch):
    application, site, browser = _anonymous(tmp_path, monkeypatch)
    break_audit(tmp_path)
    officer, admin = account_with_role(application), account_with_role(application, "admin")
    browser.post("/signin", data={"email": officer.email})
    assert _flashes(browser) == [App.AUDIT_LINE_NOT_WRITTEN]
    browser.get("/")
    refused = browser.get("/audit")                                            # refused (403): nothing saved
    assert refused.status_code == 403 and html.escape(App.AUDIT_LINE_NOT_WRITTEN) in refused.get_data(as_text=True)
    browser.get("/")
    sign_in(browser, application, "admin")
    browser.post("/audit/verify")                                              # the log cannot even be read
    assert App.AUDIT_UNAVAILABLE in _flashes(browser)
    assert App.AUDIT_NOT_WRITTEN not in _flashes(browser)


def test_a_download_whose_audit_line_failed_flashes_only_that_the_action_was_not_written(web, tmp_path):
    application, _, browser = web
    ref = sample_case()["client_ref"]
    application.clients().save(sample_case())
    browser.post(f"/client/{ref}/documents", content_type="multipart/form-data",
                 data={"files": (io.BytesIO(b"payslip"), "payslip.txt")})
    file_id = application.find_client(ref).documents()[0]["file_id"]
    browser.get("/")
    break_audit(tmp_path)
    assert browser.get(f"/client/{ref}/documents/{file_id}").status_code == 200
    assert _flashes(browser) == [App.AUDIT_LINE_NOT_WRITTEN]


def test_a_failed_audit_request_then_a_good_one_on_the_same_thread_shows_no_stale_message(web, tmp_path):
    application, _, browser = web
    break_audit(tmp_path)
    shown = browser.post("/sync", follow_redirects=True).get_data(as_text=True)
    assert html.escape(App.AUDIT_LINE_NOT_WRITTEN) in shown and application.audit_write_failed() is True
    fix_audit(tmp_path)
    shown = browser.post("/sync", follow_redirects=True).get_data(as_text=True)
    assert application.audit_write_failed() is False
    assert "could not be written" not in shown


def test_shown_value_writes_numbers_like_the_rest_of_the_app(web):
    _, site, _ = web
    for value, expected in ((16500000, "16,500,000"), (9500000.0, "9,500,000"), (7.5, "7.5"),
                            (1234.25, "1,234.25"), (0, "0"), (-2500000.0, "-2,500,000"),
                            (None, "(empty)"), ("Daniel Tan", "Daniel Tan"), (True, "True"),
                            ("16500000", "16500000"), (["SG", "UK"], "['SG', 'UK']")):
        assert site.shown_value(value) == expected, value


def test_an_edit_in_the_log_and_the_history_shows_numbers_with_separators(web):
    application, _, browser = web
    ref = sample_case()["client_ref"]
    record = ClientRecord.from_dict(sample_case())
    application.save_client(record, "Shareen")
    data = record.to_dict()
    data["claims"] = {**data["claims"], "declared_net_worth": 9500000.0}
    application.save_client(ClientRecord.from_dict(data), "Shareen")
    old = f"{sample_case()['claims']['declared_net_worth']:,.0f}"
    history = browser.get(f"/client/{ref}").get_data(as_text=True)
    assert f"{old} &rarr; 9,500,000</li>" in history and "9500000.0" not in history
    sign_in(browser, application, "admin")
    assert f"{old} &rarr; 9,500,000</li>" in browser.get("/audit").get_data(as_text=True)
