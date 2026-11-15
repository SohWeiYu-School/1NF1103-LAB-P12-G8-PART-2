"""WebApp: the browser front end, driven through Flask's test client. No network: the App
behind it has a made-up AI caller and keeps its files in a temporary folder."""

import io
import re
import shutil
import time

import pytest
from markupsafe import escape

from app.application.app import App
from app.interface.rate_limiter import RateLimiter
from app.interface.web_app import WebApp
from app.model.client_record import ClientRecord
from tests import fake_ai, fake_services
from tests.logic_fixtures import sample_case


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
    return application, site, site.flask().test_client()


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
    _, site, _ = web
    with site.flask().test_request_context("/find?ref=NOBODY"):
        assert isinstance(site.home(), str)
        assert isinstance(site.find(), Response)
        assert isinstance(site.sync_to_cloud(), Response)
        assert site.assess_poll("no-such-job") == {"status": "error", "error": "Job not found."}


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
    assert "1 typologies checked" in fresh and "1 matched" in fresh
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
    return application, site, site.flask().test_client()


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
    client = WebApp(App(fake_ai.caller(documents_reply=reading), data_folder=str(tmp_path))).flask().test_client()
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
