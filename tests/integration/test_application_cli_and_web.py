"""The command line and the web app run the same assessment through the same App, so they give
the same verdict and the same report. The AI is a made-up caller; no network."""

import copy
import html
import os
import time
from unittest.mock import patch

import pytest

from app.application.app import App
from app.interface.web_app import WebApp
from app.model.client_record import ClientRecord
from tests import fake_ai, fake_services
from tests.logic_fixtures import sample_case
from tests.web_session import sign_in

MARCUS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "documents", "marcus_lim")


def _app(tmp_path, monkeypatch, **replies) -> App:
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    return App(fake_ai.caller(**replies), data_folder=str(tmp_path))


def _client_record() -> dict:
    record = sample_case()
    record["claims"].update({"biggest_wealth_jump": 3_000_000, "wealth_jump_years": 2,
                             "declared_counterparties": ["Straits Harbour Logistics Pte Ltd"]})
    return record


def _save_replies(application: App, record: dict) -> None:
    case, missing = application.read_case(ClientRecord.from_dict(record))
    assert missing == []
    fake_services.save_forecast_replies(application.response_cache(), case)


def _assess_on_the_web(application: App, client_ref: str) -> tuple[dict, str]:
    """Press Run Assessment, wait for the background job, and return (the saved assessment, the page)."""
    browser = WebApp(application).flask().test_client()
    sign_in(browser, application)
    reply = browser.post(f"/client/{client_ref}/assess")
    assert reply.status_code == 302 and "/assess/loading/" in reply.headers["Location"]
    job_id = reply.headers["Location"].rstrip("/").split("/")[-1]
    for _ in range(400):
        if browser.get(f"/assess/poll/{job_id}").get_json()["status"] != "running":
            break
        time.sleep(0.05)
    state = browser.get(f"/assess/poll/{job_id}").get_json()
    assert state["status"] == "done", state.get("error")
    page = html.unescape(browser.get(f"/assess/result/{job_id}").get_data(as_text=True))
    return application.assessments().for_client(client_ref)[0], page


def test_cli_and_web_app_give_the_same_report(tmp_path, monkeypatch, capsys):
    application = _app(tmp_path, monkeypatch)
    record = _client_record()
    _save_replies(application, record)
    application.clients().save(copy.deepcopy(record))

    # the command line (menu option 4)
    with patch("builtins.input", return_value="y") as answer:
        cli = application.assess_client_record(ClientRecord.from_dict(record))
    printed = capsys.readouterr().out
    assert "COMBINED ASSESSMENT" in printed and cli.report["header"]["verdict_label"] in printed
    assert "Show the full evidence?" in answer.call_args.args[0]       # asked before the evidence
    assert printed.index("FULL EVIDENCE  ") > printed.index("WHAT CAME BACK CLEAN")

    # the web app (Run Assessment button), on the same App
    web, page = _assess_on_the_web(application, record["client_ref"])

    assert web["report"] == cli.report                     # the same verdict, reasons and evidence
    saved = [a for a in application.assessments().load() if a.get("report")]
    assert len(saved) == 2 and saved[0]["report"] == saved[1]["report"]
    for part in cli.report["sections"]:                     # and the page shows every line of it
        if "Crime" in part["title"]:
            continue                                           # the crime section renders as cards
        for item in part["items"]:
            assert item["text"] in page, item["text"]
    assert cli.report["header"]["verdict_label"] in page


def test_the_web_page_shows_a_saved_assessment(tmp_path, monkeypatch):
    application = _app(tmp_path, monkeypatch)
    record = _client_record()
    _save_replies(application, record)
    application.clients().save(copy.deepcopy(record))
    case, _ = application.read_case(ClientRecord.from_dict(record))
    result = application.assess(case, show_failures=False)
    assessment_id = application.save_assessment(result, ClientRecord.from_dict(record))
    browser = WebApp(application).flask().test_client()
    sign_in(browser, application)
    page = browser.get(f"/assessment/{assessment_id}").get_data(as_text=True)
    assert result["verdict"].report["header"]["summary"] in html.unescape(page)


@pytest.fixture
def marcus(tmp_path):
    """The Marcus Lim specimen: (client record as the form saves it, the correct reading of his documents)."""
    import json
    from app.data.document_store import DocumentStore
    from app.logic.document_record_builder import DocumentRecordBuilder
    from tests.logic_fixtures import CONFIG

    with open(MARCUS + "_expected_extract.json", encoding="utf-8") as handle:
        reading = json.load(handle)
    builder = DocumentRecordBuilder(CONFIG, App(None, data_folder=str(tmp_path / "x")).today())
    record, _, _ = builder.build(reading, "CL-MARCUS")
    record = builder.finish(builder.set_path(record, ["investments", 2, "income_produced"], 0)).to_dict()
    record["supporting_documents"] = [{"file_name": os.path.basename(path), "file_path": path}
                                      for path in DocumentStore().list_folder(MARCUS)]
    return record, reading


def test_cli_and_web_app_read_the_documents_the_same_way(tmp_path, monkeypatch, marcus):
    record, reading = marcus
    application = _app(tmp_path, monkeypatch, documents_reply=reading)
    _save_replies(application, record)
    application.clients().save(copy.deepcopy(record))
    with patch("builtins.input", return_value="n"):
        cli = application.assess_client_record(ClientRecord.from_dict(record))
    application.rate_limiter().reset()
    web, page = _assess_on_the_web(application, record["client_ref"])
    assert web["report"] == cli.report
    assert "Documents - what his papers show" in page and "Arcadia Holdings Ltd" in page
