"""ResponseCache: AI replies saved on disk, so the same question is not paid for twice."""

import hashlib
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ResponseCache:
    """Saved AI replies.

    Two kinds are kept under one folder:
      - one file per question (get / put), named by a key made from the question itself,
        so the same question always finds the same saved answer;
      - one file per client holding the raw forecast replies (load_raw_replies /
        save_raw_replies), so a rerun is free and gives identical answers.
    A missing or damaged file is treated as "nothing saved"; it never stops the app.
    """

    RAW_KIND: str = "forecasting"
    CLIENT_FOLDER: str = "clients"

    def __init__(self, folder: str = "data/cache") -> None:
        self.__folder: str = folder if os.path.isabs(folder) else os.path.join(ROOT_DIR, folder)

    def key(self, kind: str, payload: dict, model: str, prompt_version: str = "") -> str:
        """The key a question is saved under."""
        return self.__key(kind, payload, model, prompt_version)

    def get(self, kind: str, payload: dict, model: str, prompt_version: str = "") -> dict | None:
        """The saved answer to this question, or None. "_cache_path" says which file it came from."""
        path = self.__path(kind, self.__key(kind, payload, model, prompt_version))
        data = self.__read(path)
        if isinstance(data, dict):
            data["_cache_path"] = path
            return data
        return None

    def put(self, kind: str, key: str, data: dict) -> None:
        """Save an answer under its key. Written to a temporary file first, then swapped in,
        so a crash half way cannot leave a damaged file."""
        path = self.__path(kind, key)
        temporary = path + ".tmp"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
            os.replace(temporary, path)
        except OSError as error:
            logger.warning("ResponseCache.put: could not write %s: %s", path, error)

    def path_for(self, kind: str, key: str) -> str:
        """The file an answer with this key is saved in."""
        return self.__path(kind, key)

    def load_raw_replies(self, ref: str) -> dict:
        """{piece name: raw reply text} saved for one client. {} if there are none."""
        data = self.__read(self.__path(ResponseCache.RAW_KIND, ref))
        return data if isinstance(data, dict) else {}

    def save_raw_replies(self, ref: str, replies: dict) -> int:
        """Add the raw text of each finished piece to the client's saved replies.
        replies is {piece name: {"raw": text, ...}}. Returns how many pieces were saved."""
        if not isinstance(replies, dict):
            return 0
        saved = self.load_raw_replies(ref)
        count = 0
        for name, result in replies.items():
            if isinstance(result, dict) and result.get("raw"):
                saved[name] = result["raw"]
                count += 1
        path = self.__path(ResponseCache.RAW_KIND, ref)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(saved, handle, indent=2, ensure_ascii=False)
        except OSError as error:
            logger.warning("ResponseCache.save_raw_replies: could not write %s: %s", path, error)
            return 0
        return count

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
        temporary = path + ".tmp"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump({"fingerprint": fingerprint, "replies": replies}, handle, indent=2, ensure_ascii=False)
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as error:
            logger.warning("ResponseCache.save_client_replies: could not write %s: %s", path, error)
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

    def __path(self, kind: str, name: str) -> str:
        return os.path.join(self.__folder, kind, f"{name}.json") if kind else os.path.join(self.__folder, f"{name}.json")

    def __read(self, path: str) -> object:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError) as error:
            logger.warning("ResponseCache: could not read %s: %s", path, error)
            return None

    def __key(self, kind: str, payload: dict, model: str, prompt_version: str = "") -> str:
        """SHA-256 of the question: its kind, model, payload and prompt version."""
        canonical = json.dumps({"kind": kind, "model": model, "payload": payload,
                                "prompt_version": prompt_version}, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
