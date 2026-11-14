"""Tests for filling in the client form from uploaded documents.

No AI calls are made: the AI step is replaced with a fixed reply.
"""

import os

from docx import Document
from openpyxl import Workbook

from app import ai_manager, data_manager


AI_REPLY = {
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


# ---- reading files ----

def test_reads_word_document_including_tables(tmp_path):
    path = tmp_path / "letter.docx"
    document = Document()
    document.add_paragraph("Employment letter for Daniel Tan")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Annual salary"
    table.rows[0].cells[1].text = "SGD 240,000"
    document.save(path)

    read = data_manager.read_document_for_extraction(str(path))

    assert read["kind"] == "text"
    assert "Daniel Tan" in read["text"]
    assert "Annual salary | SGD 240,000" in read["text"]


def test_reads_spreadsheet_rows(tmp_path):
    path = tmp_path / "assets.xlsx"
    workbook = Workbook()
    workbook.active.append(["Asset", "Price"])
    workbook.active.append(["Condo", 1800000])
    workbook.save(path)

    read = data_manager.read_document_for_extraction(str(path))

    assert read["kind"] == "text"
    assert "Condo | 1800000" in read["text"]


def test_image_is_kept_as_image(tmp_path):
    path = tmp_path / "payslip.png"
    path.write_bytes(b"\x89PNG fake")

    read = data_manager.read_document_for_extraction(str(path))

    assert read["kind"] == "image"
    assert read["mime"] == "image/png"


def test_unsupported_and_empty_files_give_an_error(tmp_path):
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"MZ")
    blank = tmp_path / "blank.txt"
    blank.write_text("   ")

    assert data_manager.read_document_for_extraction(str(exe))["kind"] == "error"
    assert data_manager.read_document_for_extraction(str(blank))["kind"] == "error"


# ---- what is sent to the AI ----

def test_no_readable_documents_skips_the_ai():
    data, warnings = ai_manager.extract_client_details(
        [{"file_name": "x.exe", "kind": "error", "error": "x.exe: this file type can't be read"}])

    assert data is None
    assert warnings == ["x.exe: this file type can't be read"]


def test_list_documents_in_folder_skips_other_files(tmp_path):
    for name in ["b.pdf", "a.docx", "notes.TXT", "~$a.docx", ".hidden.pdf", "setup.exe"]:
        (tmp_path / name).write_text("x")
    (tmp_path / "sub").mkdir()

    found = [os.path.basename(p) for p in data_manager.list_documents_in_folder(str(tmp_path))]

    assert found == ["a.docx", "b.pdf", "notes.TXT"]
    assert data_manager.list_documents_in_folder(str(tmp_path / "nope")) is None