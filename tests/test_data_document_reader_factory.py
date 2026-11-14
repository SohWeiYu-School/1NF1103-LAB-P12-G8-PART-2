"""DocumentReaderFactory: the right reader for each file type."""

import pytest

from app.data.document_reader import ExcelReader, ImageReader, PdfReader, TextReader, WordReader
from app.data.document_reader_factory import DocumentReaderFactory


@pytest.mark.parametrize("file_name, reader", [
    ("statement.pdf", PdfReader), ("letter.docx", WordReader), ("assets.xlsx", ExcelReader),
    ("macro.xlsm", ExcelReader), ("scan.png", ImageReader), ("photo.JPEG", ImageReader),
    ("notes.txt", TextReader), ("rows.csv", TextReader)])
def test_the_factory_picks_the_reader_by_file_type(file_name, reader):
    assert isinstance(DocumentReaderFactory().create(file_name), reader)


@pytest.mark.parametrize("file_name", ["program.exe", "archive.zip", "no_extension", "", None])
def test_a_file_type_with_no_reader_gives_none(file_name):
    assert DocumentReaderFactory().create(file_name) is None


def test_every_call_creates_a_new_reader():
    factory = DocumentReaderFactory()
    assert factory.create("a.pdf") is not factory.create("b.pdf")


def test_the_factory_passes_its_length_limit_to_the_reader(tmp_path):
    path = tmp_path / "long.txt"
    path.write_text("x" * 500, encoding="utf-8")
    reader = DocumentReaderFactory(max_chars=50).create("long.txt")
    assert len(reader.read(str(path), "long.txt")["text"]) == 50


def test_supported_types_lists_every_type_a_reader_exists_for():
    types = DocumentReaderFactory().supported_types()
    assert ".pdf" in types and ".docx" in types and ".xlsx" in types and ".png" in types and ".txt" in types
    assert ".exe" not in types
