"""DocumentEvidence: the documents feature."""

from app.logic.document_evidence import DocumentEvidence
from app.logic.feature import Feature
from app.model.check import Check
from tests.logic_fixtures import POLICY

KIND = next(iter(POLICY["verdict"]["document_evidence"]))
READING = {"evidence": {
    "documented_pay": [{"year": "2025", "employment_income_sgd": "480,000", "source_file": "tax_2025.pdf"},
                       {"year": 2025, "employment_income_sgd": 1, "source_file": "duplicate.pdf"},
                       {"year": "unknown", "employment_income_sgd": 5}],
    "findings": [{"kind": KIND, "summary": "A payment the declaration does not mention.", "amount_sgd": "250k",
                  "source_files": ["bank.pdf"]},
                 {"kind": "made_up_kind", "summary": "Something else."},
                 {"kind": KIND, "summary": "   "}]},
    "notes": ["Page 2 was blurred."]}
FILES = ["tax_2025.pdf", "bank.pdf"]


def _run(reading=READING, files=FILES):
    feature = DocumentEvidence(POLICY)
    return feature, feature.run({}, {"extracted": reading, "files": files})


def test_document_evidence_is_a_feature():
    assert isinstance(DocumentEvidence(POLICY), Feature)
    assert DocumentEvidence.NAME == "documents"


def test_documented_pay_is_read_once_per_year_and_bad_rows_are_dropped():
    _, evidence = _run()
    assert evidence["documented_pay"] == [{"year": 2025, "amount": 480000.0, "source_file": "tax_2025.pdf"}]


def test_findings_keep_their_kind_and_an_unknown_kind_becomes_other():
    _, evidence = _run()
    assert sorted(finding["kind"] for finding in evidence["findings"]) == sorted([KIND, "other"])
    assert next(f for f in evidence["findings"] if f["kind"] == KIND)["amount_sgd"] == 250000.0


def test_a_reading_that_failed_is_marked_unread():
    feature, evidence = _run(reading=None)
    assert evidence["read"] is False
    assert [check.check for check in feature.checks({})] == ["DOCUMENTS_UNREAD"]


def test_no_documents_gives_an_information_check():
    feature, _ = _run(reading=None, files=[])
    checks = feature.checks({})
    assert [(check.check, check.status) for check in checks] == [("NO_DOCUMENTS", "info")]


def test_each_finding_becomes_a_check_that_names_its_source_files():
    feature, _ = _run()
    checks = feature.checks({"types": []})
    assert all(isinstance(check, Check) and check.feature == "documents" for check in checks)
    first = next(check for check in checks if check.check == KIND.upper())
    assert first.sources == ["bank.pdf"]
    assert first.status == ("failed" if POLICY["verdict"]["document_evidence"][KIND]["serious"] else "weak")


def test_documents_that_show_nothing_new_pass():
    feature, _ = _run(reading={"evidence": {"documented_pay": [], "findings": []}})
    assert [check.check for check in feature.checks({})] == ["DOCUMENTS_AGREE"]
