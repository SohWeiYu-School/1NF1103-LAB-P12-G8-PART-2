"""The document readers: one per kind of file."""

import base64

import pytest
from docx import Document
from openpyxl import Workbook

from app.data.document_reader import (DocumentReader, ExcelReader, ImageReader, PdfReader, TextReader,
                                      WordReader)


def test_the_abstract_reader_cannot_be_created():
    with pytest.raises(TypeError):
        DocumentReader()


def test_every_reader_is_a_document_reader():
    for reader in (PdfReader(), WordReader(), ExcelReader(), ImageReader(), TextReader()):
        assert isinstance(reader, DocumentReader)


def test_text_reader_reads_plain_text(tmp_path):
    path = tmp_path / "payslip.txt"
    path.write_text("Basic salary 5,000", encoding="utf-8")
    assert TextReader().read(str(path), "payslip.txt") == {
        "file_name": "payslip.txt", "kind": "text", "text": "Basic salary 5,000"}


def test_text_is_cut_to_the_longest_length_kept(tmp_path):
    path = tmp_path / "long.txt"
    path.write_text("x" * 500, encoding="utf-8")
    assert len(TextReader(max_chars=100).read(str(path), "long.txt")["text"]) == 100


def test_an_empty_file_is_reported_not_read(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("   \n", encoding="utf-8")
    result = TextReader().read(str(path), "empty.txt")
    assert result["kind"] == "error"
    assert result["error"] == "empty.txt: no text was found in it."


def test_word_reader_reads_paragraphs_and_tables(tmp_path):
    path = tmp_path / "letter.docx"
    document = Document()
    document.add_paragraph("Employment confirmation")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Annual salary"
    table.rows[0].cells[1].text = "240,000"
    document.save(str(path))
    text = WordReader().read(str(path), "letter.docx")["text"]
    assert "Employment confirmation" in text
    assert "Annual salary | 240,000" in text


def test_excel_reader_reads_every_sheet(tmp_path):
    path = tmp_path / "assets.xlsx"
    workbook = Workbook()
    workbook.active.title = "Assets"
    workbook.active.append(["Condo", 3100000])
    workbook.create_sheet("Income").append(["Rent", 54000])
    workbook.save(str(path))
    text = ExcelReader().read(str(path), "assets.xlsx")["text"]
    assert "[Sheet Assets]" in text and "Condo | 3100000" in text
    assert "[Sheet Income]" in text and "Rent | 54000" in text


def test_image_reader_passes_the_picture_on(tmp_path):
    path = tmp_path / "scan.JPG"
    path.write_bytes(b"\xff\xd8picture")
    result = ImageReader().read(str(path), "scan.JPG")
    assert result["kind"] == "image"
    assert result["mime"] == "image/jpeg"
    assert base64.b64decode(result["data_b64"]) == b"\xff\xd8picture"


def test_a_damaged_word_file_raises_for_the_store_to_handle(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a real word file")
    with pytest.raises(Exception):
        WordReader().read(str(path), "broken.docx")


def test_pdf_reader_reads_the_text_page_by_page():
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "marcus_lim", "02_CV_Marcus_Lim.pdf")
    result = PdfReader().read(path, "02_CV_Marcus_Lim.pdf")
    assert result["kind"] == "text"
    assert result["text"].startswith("[Page 1]")
    assert "Marcus" in result["text"]


def test_a_pdf_with_no_readable_text_is_passed_on_as_a_file(tmp_path):
    from pypdf import PdfWriter
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as handle:
        writer.write(handle)
    result = PdfReader().read(str(path), "scan.pdf")
    assert result["kind"] == "pdf"
    assert result["data_b64"]
