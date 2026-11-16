"""DocumentEvidence: what the client's own documents show."""

from app.logic.case_reader import CaseReader
from app.logic.risk_analysis import RiskAnalysis
from app.model.check import Check


class DocumentEvidence(RiskAnalysis):
    """The documents feature. It cleans the AI's reading of the submitted documents into
    documented pay (which later corrects the forecast) and findings (income, payments and
    names the documents show), and turns the findings into Checks.

    It uses a CaseReader to read amounts and years the same way the rest of the app does.
    """

    NAME: str = "documents"

    def __init__(self, policy: dict | None = None) -> None:
        super().__init__(policy)
        self.__reader: CaseReader = CaseReader()

    def run(self, case: dict, ai_data: dict) -> dict:
        """The cleaned evidence. ai_data is {"extracted": the AI's reading or None, "files": [names]}."""
        results = self._read(ai_data.get("extracted"), ai_data.get("files"))
        self._results = results
        return results          # the local value: another run may replace self._results meanwhile

    def checks(self, context: dict) -> list[Check]:
        """The documents' findings. context holds evidence (default: the last run) and types."""
        evidence = context.get("evidence", self._results or None)
        return self._document_checks(evidence, context.get("types") or [])

    def _read(self, extracted: dict | None, files: list[str] | None = None) -> dict:
        """The AI's reading of every submitted document, cleaned into the documents layer:
        {"files", "documented_pay": [{year, amount, source_file}], "findings": [...], "notes": [...]}.
        Anything the reading left out is just empty, so older readings still work."""
        policy = self._policy
        kinds = policy["verdict"]["document_evidence"]
        evidence = (extracted or {}).get("evidence") or {}
        pay = []
        for row in evidence.get("documented_pay") or []:
            year, amount = self.__reader.read_year(row.get("year")), CaseReader.read_amount(row.get("employment_income_sgd"))
            if year and amount and amount > 0 and year not in [p["year"] for p in pay]:
                pay.append({"year": year, "amount": amount, "source_file": row.get("source_file")})
        findings = []
        for row in evidence.get("findings") or []:
            kind = row.get("kind") if row.get("kind") in kinds else "other"
            summary = str(row.get("summary") or "").strip()
            if not summary:
                continue
            findings.append({"kind": kind, "summary": summary, "amount_sgd": CaseReader.read_amount(row.get("amount_sgd")),
                             "per": row.get("per"), "counterparty": row.get("counterparty"),
                             "country": row.get("country"), "source_files": list(row.get("source_files") or [])})
        order = list(kinds)
        findings.sort(key=lambda f: (not kinds[f["kind"]]["serious"], order.index(f["kind"])))
        return {"files": list(files or []), "read": extracted is not None,
                "documented_pay": sorted(pay, key=lambda p: p["year"]), "findings": findings,
                "notes": [str(n) for n in (extracted or {}).get("notes") or []]}

    def _document_checks(self, evidence: dict | None, types: list[dict]) -> list[Check]:
        """The documents layer as findings in the shared shape: each fact the declaration leaves out
        or contradicts, and which crime stories it supports."""
        policy = self._policy
        if not evidence or not evidence.get("files"):
            return [self._check("NO_DOCUMENTS", "Supporting documents", "pattern", "info",
                                "No supporting documents were submitted, so nothing was checked against them.")]
        if not evidence.get("read"):
            return [self._check("DOCUMENTS_UNREAD", "Supporting documents", "pattern", "skipped",
                                f"{len(evidence['files'])} document(s) couldn't be read.")]
        kinds = policy["verdict"]["document_evidence"]
        checks = []
        for finding in evidence["findings"]:
            setting = kinds[finding["kind"]]
            stories = [t for t in types if t["category"] in setting["supports"]]
            checks.append(self._check(
                finding["kind"].upper(), setting["label"], setting["theme"],
                "failed" if setting["serious"] else "weak", finding["summary"],
                ("Supports " + "; ".join(f"{t['type_id']} {t['name']}" for t in stories) + ".") if stories else "",
                group="Documents", sources=finding["source_files"], supports=setting["supports"]))
        if not checks:
            checks.append(self._check("DOCUMENTS_AGREE", "Supporting documents", "pattern", "passed",
                                      f"The {len(evidence['files'])} document(s) agree with his declaration.",
                                      group="Documents"))
        return checks
