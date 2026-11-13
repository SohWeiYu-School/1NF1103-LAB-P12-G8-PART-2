"""ResponseCache: AI replies saved on disk, so the same question is not paid for twice."""

import hashlib
import json
import logging
import os

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
