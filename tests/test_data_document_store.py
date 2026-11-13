"""DocumentStore: keeping and reading supporting documents, including files that cannot be read."""

import os

from app.data.document_store import DocumentStore


def _store(tmp_path):
    return DocumentStore("data/documents", root=str(tmp_path))


def _file(tmp_path, name, text="Basic salary 5,000"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_upload_copies_the_file_and_returns_its_id(tmp_path):
    store = _store(tmp_path)
    file_id = store.upload(_file(tmp_path, "payslip.txt"))
    assert file_id.startswith("data/documents/") and file_id.endswith("_payslip.txt")
    assert os.path.isfile(os.path.join(str(tmp_path), file_id))


def test_uploading_a_file_that_is_not_there_gives_none(tmp_path):
    assert _store(tmp_path).upload(str(tmp_path / "missing.pdf")) is None
    assert _store(tmp_path).upload("") is None


def test_download_copies_a_stored_document_out(tmp_path):
    store = _store(tmp_path)
    file_id = store.upload(_file(tmp_path, "payslip.txt"))
    out = tmp_path / "out" / "copy.txt"
    assert store.download(file_id, str(out))
    assert out.read_text(encoding="utf-8") == "Basic salary 5,000"


def test_download_of_an_unknown_id_returns_false(tmp_path):
    store = _store(tmp_path)
    assert store.download("652f1c2e9b1e8a3f4c5d6e7f", str(tmp_path / "x.txt")) is False
    assert store.download("", str(tmp_path / "x.txt")) is False


def test_read_for_extraction_uses_the_reader_for_the_file_type(tmp_path):
    result = _store(tmp_path).read_for_extraction(_file(tmp_path, "payslip.txt"))
    assert result == {"file_name": "payslip.txt", "kind": "text", "text": "Basic salary 5,000"}


def test_a_file_type_with_no_reader_is_reported(tmp_path):
    result = _store(tmp_path).read_for_extraction(_file(tmp_path, "program.exe"))
    assert result["kind"] == "error"
    assert "this file type can't be read" in result["error"]


def test_a_damaged_file_is_reported_instead_of_crashing(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a real word file")
    result = _store(tmp_path).read_for_extraction(str(path))
    assert result["kind"] == "error"
    assert result["error"].startswith("broken.docx: could not be read (")


def test_read_all_reads_each_saved_document_under_its_uploaded_name(tmp_path):
    store = _store(tmp_path)
    file_id = store.upload(_file(tmp_path, "payslip.txt"))
    read = store.read_all([{"file_name": "June payslip.txt", "file_path": file_id},
                           {"file_name": "lost.txt", "file_path": "data/documents/lost.txt"}])
    assert read[0] == {"file_name": "June payslip.txt", "kind": "text", "text": "Basic salary 5,000"}
    assert read[1] == {"file_name": "lost.txt", "kind": "error",
                       "error": "lost.txt: the saved copy couldn't be found."}


def test_read_all_of_nothing_is_an_empty_list(tmp_path):
    assert _store(tmp_path).read_all(None) == []


def test_list_folder_gives_only_readable_documents_sorted_by_name(tmp_path):
    folder = tmp_path / "client"
    folder.mkdir()
    for name in ("b.pdf", "A.txt", ".hidden.txt", "~$temp.docx", "tool.exe"):
        (folder / name).write_text("x", encoding="utf-8")
    (folder / "sub").mkdir()
    listed = _store(tmp_path).list_folder(str(folder))
    assert [os.path.basename(path) for path in listed] == ["A.txt", "b.pdf"]


def test_list_folder_of_a_missing_folder_is_none(tmp_path):
    assert _store(tmp_path).list_folder(str(tmp_path / "nowhere")) is None
