"""The command line (menu option 2) and the web app must turn the same documents into the same client.

Uses the specimen documents in tests/documents/marcus_lim/ and marcus_lim_expected_extract.json, which is
what a correct AI reading of them looks like (no AI calls are made here).
"""

import datetime
import json
import os

import pytest

from app.application.app import App
from app.data.document_store import DocumentStore
from app.interface.case_builder import CaseBuilder
from app.interface.console_ui import ConsoleUI
from app.interface.web_app import WebApp
from app.logic.case_reader import CaseReader
from app.logic.document_record_builder import DocumentRecordBuilder
from app.model.client_record import ClientRecord
from tests.logic_fixtures import CONFIG
from tests.web_session import sign_in

FOLDER = os.path.join(os.path.dirname(__file__), "documents", "marcus_lim")
TODAY = "2026-10-13"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    folder = tmp_path_factory.mktemp("parity")
    return WebApp(App(None, data_folder=str(folder)))


def expected_reply() -> dict:
    with open(FOLDER + "_expected_extract.json", encoding="utf-8") as handle:
        return json.load(handle)


def cli_record(reply: dict) -> dict:
    """What menu option 2 saves: documents -> record, the officer types what's missing."""
    builder = DocumentRecordBuilder(CONFIG, TODAY)
    record, _, _ = builder.build(reply, "CL-MARCUS")
    for field in builder.missing_fields(record):
        assert field["path"] == ["investments", 2, "income_produced"], field   # the only gap
        record = builder.set_path(record, field["path"], 0)
    return builder.finish(record).to_dict()


def web_record(site: WebApp, reply: dict) -> dict:
    """What the web form saves: auto-fill an empty form, the officer saves it unchanged."""
    empty = site.values_from_record({"current_date": TODAY})
    values, _ = site.fill_blanks(empty, site.extracted_to_values(reply, TODAY))
    record, problems, _ = site.build_record(values, "CL-MARCUS")
    assert problems == []
    return record


def test_all_specimen_documents_are_read_as_text():
    store = DocumentStore()
    read = [store.read_for_extraction(path) for path in store.list_folder(FOLDER)]

    assert len(read) == 9
    assert all(document["kind"] == "text" for document in read)
    kyc = next(d for d in read if d["file_name"].startswith("01_KYC"))
    assert "SGD 14,500,000" in kyc["text"] and "Sentosa Cove" in kyc["text"]


def test_cli_and_web_save_the_same_client(site):
    cli, web = cli_record(expected_reply()), web_record(site, expected_reply())

    for key in ("name", "nationality", "career", "career_history", "investments", "sow_declaration"):
        assert cli[key] == web[key], key
    for key in ("declared_net_worth", "expected_aum", "pep_status", "wealth_countries",
                "asset_composition", "biggest_wealth_jump", "declared_counterparties"):
        assert cli["claims"][key] == web["claims"][key], key


def test_the_record_holds_the_declared_figures(site):
    record = web_record(site, expected_reply())

    assert record["career"]["age"] == 47                      # born 22 April 1979
    assert record["career"]["career_start_year"] == 2001
    assert record["career"]["employer_name"] == "Lim Precision Trading Pte Ltd"
    assert [job["start_year"] for job in record["career_history"]] == [2001, 2003, 2011]
    assert record["investments"][1] == {
        "asset_type": "Property - Condo, The Coralis, Sentosa Cove (own residence)", "country": "Singapore",
        "year_acquired": 2023, "price_paid": 4200000, "current_declared_value": 4600000,
        "payment_method": "loan", "income_produced": 0}
    assert record["claims"]["asset_composition"] == {
        "property": 0.45, "listed_equities": 0.15, "private_business": 0.30, "cash": 0.10}
    assert record["claims"]["declared_net_worth"] == 14500000
    # evidence the client did not declare stays out of the declared fields
    assert "Arcadia Holdings Ltd" not in json.dumps(record)


def test_both_records_pass_the_forecasting_checks(site):
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "schemas", "case_input.schema.json")
    with open(schema_path, encoding="utf-8") as handle:
        builder = CaseBuilder(ConsoleUI(), json.load(handle))
    for record in (cli_record(expected_reply()), web_record(site, expected_reply())):
        case = {key: value for key, value in record.items() if key != "supporting_documents"}
        assert builder.validate_case(case) == []


def test_the_ai_gets_the_same_inputs_from_both(site):
    cli, web = cli_record(expected_reply()), web_record(site, expected_reply())
    reader = CaseReader()

    assert reader.crime_scan_input(cli) == reader.crime_scan_input(web)
    cli_bench, cli_missing = reader.benchmark_input(cli, reader.crime_scan_input(cli))
    web_bench, web_missing = reader.benchmark_input(web, reader.crime_scan_input(web))
    assert cli_bench == web_bench and cli_missing == web_missing == []
    # whole percents, as the benchmark rules expect
    assert (cli_bench["property"], cli_bench["listed_equities"],
            cli_bench["private_business"], cli_bench["cash"]) == (45, 15, 30, 10)


def test_the_case_uses_the_saved_values_without_asking(site):
    for record in (cli_record(expected_reply()), web_record(site, expected_reply())):
        case, missing = CaseReader(TODAY).forecasting_case(record)
        assert missing == []
        assert case["investments"][0]["current_declared_value"] == 1900000
        assert case["investments"][0]["income_produced"] == 54000


def test_the_split_matches_the_listed_assets():
    builder = DocumentRecordBuilder(CONFIG, TODAY)
    record = ClientRecord.from_dict(cli_record(expected_reply()))
    assert builder.check(record) == []

    misread = builder.set_path(record, ["investments", 0, "current_declared_value"], 19000000)
    assert any("property assets listed are worth" in warning for warning in builder.check(misread))


def test_assessments_are_always_dated_today(site, tmp_path):
    today = datetime.date.today().isoformat()
    application = App(None, data_folder=str(tmp_path))

    case, _ = application.read_case(ClientRecord.from_dict(cli_record(expected_reply())))
    assert case["current_date"] == today                       # command line: not asked

    assert web_record(site, expected_reply())["current_date"] == today   # web form: no date box
    browser = site.flask().test_client()
    sign_in(browser, site._WebApp__app)
    page = browser.get("/client/new").get_data(as_text=True)
    assert 'name="client.current_date"' not in page
