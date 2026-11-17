"""ResponseCache: AI replies saved on disk, so the same question is not paid for twice."""

import hashlib
import json
import logging
import os
import re
import tempfile

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ResponseCache:
    """Saved AI replies, one file per client: <folder>/clients/<client_ref>.json.

    The file holds a fingerprint of the client (see fingerprint) and the replies saved for that
    client. The replies are used only while the client is unchanged; any change means a different
    fingerprint, and every AI step asks again. The class only makes the fingerprint and reads and
    writes the file; the steps that read and write the replies are in the AI services.
    A missing or damaged file is treated as "nothing saved"; it never stops the app.
    """

    CLIENT_FOLDER: str = "clients"

    def __init__(self, folder: str = "data/cache") -> None:
        self.__folder: str = folder if os.path.isabs(folder) else os.path.join(ROOT_DIR, folder)

    def fingerprint(self, case: dict, documents: list[dict]) -> str:
        """A SHA-256 that says "this is the same client as last time". It covers the case (without
        "current_date", which is only the day the run is made) and what each document contains.
        documents is what DocumentStore.read_all gives: [{"file_name", "kind", "text" / "data_b64" / "error"}]."""
        case_part = {key: value for key, value in (case or {}).items() if key != "current_date"}
        document_part = []
        for document in documents or []:
            content = document.get("text") or document.get("data_b64") or document.get("error") or ""
            document_part.append([document.get("file_name"), document.get("kind"),
                                  hashlib.sha256(str(content).encode("utf-8")).hexdigest()])
        canonical = json.dumps({"case": case_part, "documents": document_part},
                               sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def load_client_replies(self, client_ref: str, fingerprint: str) -> dict:
        """The replies saved for this client, or {} if there are none, the file is damaged, or it was
        saved for a client that has since changed (a different fingerprint). Raises ValueError for a
        client_ref that is not safe to use as a file name."""
        path = self.__client_path(client_ref)
        data = self.__read(path)
        if data is None:
            return {}
        if (not isinstance(data, dict) or not isinstance(data.get("fingerprint"), str)
                or not isinstance(data.get("replies"), dict)):
            logger.warning("ResponseCache: %s does not have the saved-replies layout, so it is ignored", path)
            return {}
        if data["fingerprint"] != fingerprint:
            logger.info("ResponseCache: %s was saved for an earlier version of the client, so every step "
                        "asks the AI again", path)
            return {}
        return data["replies"]

    def save_client_replies(self, client_ref: str, fingerprint: str, replies: dict) -> bool:
        """Save the client's replies with their fingerprint, replacing the earlier file. Written to a
        temporary file first, then swapped in, so a crash half way cannot leave a damaged file.
        False (and a warning in the log) if it could not be written. Raises ValueError for a bad client_ref."""
        path = self.__client_path(client_ref)
        temporary = None
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # A temporary file of its own for every save, so two saves of the same client cannot meet
            handle, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump({"fingerprint": fingerprint, "replies": replies}, stream, indent=2, ensure_ascii=False)
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as error:
            logger.warning("ResponseCache.save_client_replies: could not write %s: %s", path, error)
            if temporary is not None:
                try:
                    os.remove(temporary)
                except OSError:
                    pass
            return False
        return True

    def __client_path(self, client_ref: str) -> str:
        if not isinstance(client_ref, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", client_ref):
            raise ValueError(f"client_ref {client_ref!r} is not allowed: use letters, digits, '-' and '_' only")
        return os.path.join(self.__folder, ResponseCache.CLIENT_FOLDER, f"{client_ref}.json")

    def __read(self, path: str) -> object:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError) as error:
            logger.warning("ResponseCache: could not read %s: %s", path, error)
            return None
