"""DocumentReader and its five children: one reader per kind of file."""

import base64
from abc import ABC, abstractmethod


class DocumentReader(ABC):
    """Reads one uploaded file so the AI can pull client details out of it.

    read() returns {"file_name", "kind", ...}:
        kind "text"   -> "text": the document's text
        kind "image"  -> "mime", "data_b64": a photo or scan
        kind "pdf"    -> "data_b64": a scanned PDF with no readable text
        kind "error"  -> "error": why it could not be read
    A damaged file raises; DocumentStore turns that into a kind "error" result.
    """

    def __init__(self, max_chars: int = 40_000) -> None:
        # Longest text kept from one document, so one huge file cannot crowd out the others.
        self._max_chars: int = max_chars

    @abstractmethod
    def read(self, file_path: str, file_name: str) -> dict:
        """Read the file at file_path, known to the officer as file_name."""

    def _base64_file(self, file_path: str) -> str:
        with open(file_path, "rb") as handle:
            return base64.b64encode(handle.read()).decode("ascii")

    def _text_result(self, file_name: str, text: str) -> dict:
        """The result for a document read as text, cut to the longest length kept."""
        if not text.strip():
            return {"file_name": file_name, "kind": "error", "error": f"{file_name}: no text was found in it."}
        return {"file_name": file_name, "kind": "text", "text": text[:self._max_chars]}


class PdfReader(DocumentReader):
    """PDF files. A PDF with almost no text is a scan, so it is passed on as a file."""

    MIN_TEXT_CHARS: int = 80

    def __init__(self, max_chars: int = 40_000) -> None:
        super().__init__(max_chars)

    def read(self, file_path: str, file_name: str) -> dict:
        text = self.__pdf_text(file_path)
        readable = "".join(line for line in text.splitlines() if not line.startswith("[Page "))
        if len(readable.strip()) < PdfReader.MIN_TEXT_CHARS:
            return {"file_name": file_name, "kind": "pdf", "data_b64": self._base64_file(file_path)}
        return self._text_result(file_name, text)

    def __pdf_text(self, file_path: str) -> str:
        from pypdf import PdfReader as PypdfReader
        pages = [f"[Page {number}]\n{page.extract_text() or ''}"
                 for number, page in enumerate(PypdfReader(file_path).pages, start=1)]
        return "\n\n".join(pages)


class WordReader(DocumentReader):
    """Word (.docx) files: the paragraphs, then the tables (tables often hold the figures)."""

    def __init__(self, max_chars: int = 40_000) -> None:
        super().__init__(max_chars)

    def read(self, file_path: str, file_name: str) -> dict:
        return self._text_result(file_name, self.__docx_text(file_path))

    def __docx_text(self, file_path: str) -> str:
        from docx import Document
        document = Document(file_path)
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(parts)


class ExcelReader(DocumentReader):
    """Excel (.xlsx, .xlsm) files: every sheet, one line per row."""

    def __init__(self, max_chars: int = 40_000) -> None:
        super().__init__(max_chars)

    def read(self, file_path: str, file_name: str) -> dict:
        return self._text_result(file_name, self.__xlsx_text(file_path))

    def __xlsx_text(self, file_path: str) -> str:
        from openpyxl import load_workbook
        workbook = load_workbook(file_path, read_only=True, data_only=True)
        parts = []
        for sheet in workbook.worksheets:
            parts.append(f"[Sheet {sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                cells = ["" if cell is None else str(cell) for cell in row]
                if any(cells):
                    parts.append(" | ".join(cells))
        workbook.close()
        return "\n".join(parts)


class ImageReader(DocumentReader):
    """Photos and scans. They have no text to read, so the picture itself is passed on."""

    IMAGE_TYPES: dict = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                         ".webp": "image/webp", ".gif": "image/gif"}

    def __init__(self, max_chars: int = 40_000) -> None:
        super().__init__(max_chars)

    def read(self, file_path: str, file_name: str) -> dict:
        extension = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        return {"file_name": file_name, "kind": "image",
                "mime": ImageReader.IMAGE_TYPES.get(extension, "image/png"),
                "data_b64": self._base64_file(file_path)}


class TextReader(DocumentReader):
    """Plain text files (.txt, .csv, .md, .json)."""

    TEXT_TYPES: tuple[str, ...] = (".txt", ".csv", ".md", ".json")

    def __init__(self, max_chars: int = 40_000) -> None:
        super().__init__(max_chars)

    def read(self, file_path: str, file_name: str) -> dict:
        with open(file_path, encoding="utf-8", errors="replace") as handle:
            return self._text_result(file_name, handle.read())
