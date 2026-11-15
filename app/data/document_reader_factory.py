"""DocumentReaderFactory: picks the right reader for a file."""

import os

from app.data.document_reader import (DocumentReader, ExcelReader, ImageReader, PdfReader, TextReader,
                                      WordReader)


class DocumentReaderFactory:
    """Creates the DocumentReader for a file, chosen by the file's type.

    To support a new kind of file, write a new reader and add its file types here.
    Nothing else has to change.
    """

    READER_TYPES: dict[str, type[DocumentReader]] = {
        ".pdf": PdfReader, ".docx": WordReader, ".xlsx": ExcelReader, ".xlsm": ExcelReader,
        **{extension: ImageReader for extension in ImageReader.IMAGE_TYPES},
        **{extension: TextReader for extension in TextReader.TEXT_TYPES}}

    def __init__(self, max_chars: int = 40_000) -> None:
        self.__max_chars: int = max_chars

    def create(self, file_name: str) -> DocumentReader | None:
        """A reader for this file, or None if the file type cannot be read."""
        extension = os.path.splitext(file_name or "")[1].lower()
        reader = DocumentReaderFactory.READER_TYPES.get(extension)
        return reader(self.__max_chars) if reader else None

    def supported_types(self) -> list[str]:
        """Every file type a reader exists for, e.g. ['.csv', '.docx', ...]."""
        return sorted(DocumentReaderFactory.READER_TYPES)
