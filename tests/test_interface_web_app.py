"""WebApp: the browser front end, driven through Flask's test client. No network: the App
behind it has a made-up AI caller and keeps its files in a temporary folder."""

import time

import pytest

from app.application.app import App
from app.interface.web_app import WebApp
from tests import fake_services
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


def test_the_web_app_only_holds_an_app(web):
    _, site, _ = web
    held = [name for name in vars(site) if not name.startswith("_WebApp__")]
    assert held == []
    assert set(vars(site)) == {"_WebApp__app", "_WebApp__jobs", "_WebApp__flask"}


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
    case, _ = application.read_case(record)
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


def test_a_second_assessment_straight_away_is_rate_limited(web):
    application, _, client = web
    record = sample_case()
    application.clients().save(record)
    case, _ = application.read_case(record)
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
