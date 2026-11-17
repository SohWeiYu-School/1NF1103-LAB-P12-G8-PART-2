"""DocumentAI: reads the client's documents into the details the form needs."""

import hashlib
import logging
from typing import Callable

from app.ai.ai_service import AIService

logger = logging.getLogger(__name__)


class DocumentAI(AIService):
    """Pulls client details out of uploaded documents (text, images and scanned PDFs).

    Nothing is decided here: the officer reviews every pre-filled value before it is saved.
    source is {"documents": [what the document readers returned]}. The same documents
    always give the same reading, because the saved answer is keyed on their contents.
    """

    PROMPT_NAME: str = "document_extract"
    SCHEMA_NAME: str = "document_extract"
    MAX_DOCUMENTS: int = 10       # most documents sent in one go (each is a separate message part)
    READABLE_KINDS: tuple[str, ...] = ("text", "image", "pdf")

    def __init__(self, provider: str = "", ai_caller: Callable | None = None, model: str = "", temperature: float = 0.0,
                 max_chars: int = 40_000) -> None:
        super().__init__(provider, ai_caller, model, temperature)
        self.__max_chars: int = max_chars

    def run(self, source: dict) -> dict | None:
        """Read the documents. Returns the details, or None if none could be read or the AI
        gave no usable answer. warnings() lists the files that could not be read."""
        documents = source.get("documents") or []
        notes = [document["error"] for document in documents if document.get("kind") == "error"]
        readable = [document for document in documents if document.get("kind") in DocumentAI.READABLE_KINDS]
        if len(readable) > DocumentAI.MAX_DOCUMENTS:
            notes.append(f"Only the first {DocumentAI.MAX_DOCUMENTS} documents were read.")
        data = None
        if readable:
            data = super().run({"documents": readable[:DocumentAI.MAX_DOCUMENTS],
                                "saved_replies": source.get("saved_replies")})
        else:
            logger.warning("DocumentAI: none of the uploaded files could be read")
        self._warnings = notes
        return data

    def _payload(self, source: dict) -> dict:
        """The documents as message parts. Text goes between <document> markers so the AI
        treats it as data, not as instructions."""
        parts: list[dict] = []
        for document in source["documents"]:
            name = document.get("file_name", "document")
            kind = document.get("kind")
            if kind == "text":
                text = (document.get("text") or "")[:self.__max_chars]
                open_tag, close_tag = f'<document name="{name}">', "</document>"
                cleaned = text.replace(open_tag, "").replace(close_tag, "")
                parts.append({"type": "text", "text": f"{open_tag}\n{cleaned.strip()}\n{close_tag}"})
            elif kind == "image":
                parts.append({"type": "text", "text": f'<document name="{name}"> (image below)'})
                parts.append({"type": "image_url", "image_url": {
                    "url": f"data:{document['mime']};base64,{document['data_b64']}"}})
            elif kind == "pdf":
                parts.append({"type": "text", "text": f'<document name="{name}"> (scanned PDF below)'})
                parts.append({"type": "file", "file": {
                    "filename": name, "file_data": f"data:application/pdf;base64,{document['data_b64']}"}})
        return {"parts": parts}

    def _fill_prompt(self, template: str, source: dict, payload: dict) -> str:
        return template      # the instructions go as they are; the documents travel as message parts

    def _options(self, source: dict) -> dict:
        return {"parts": self._payload(source)["parts"], "schema_name": self.SCHEMA_NAME}

    def _cache_payload(self, source: dict, payload: dict) -> dict:
        """[file name, SHA-256 of its content] for each document, in order."""
        prints = []
        for document in source["documents"]:
            content = document.get("text") or document.get("data_b64") or ""
            prints.append([document.get("file_name", ""), hashlib.sha256(content.encode("utf-8")).hexdigest()])
        return {"documents": prints}
