"""AIService: the generic way to ask an AI one kind of question."""

import copy
import hashlib
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Callable

import jsonschema

logger = logging.getLogger(__name__)

AI_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(AI_DIR)


class AIService(ABC):
    """One kind of question for an AI (research, typologies, benchmark, ...).

    The parent does everything the questions share: build the prompt, reuse a saved
    answer, ask, read the reply, check it against the schema, try again, save the answer.
    Each child only says what is different: what may be sent (_payload) and what to
    do with a good answer (_post_process).

    The AI brand is not chosen here. The service is handed an ai_caller function
    (see app/ai/ai_caller.py); it creates none.

    Saved answers belong to one client and travel with the run: source["saved_replies"] is a
    dict (or None) that the caller loaded for that client. The service reads its own step from
    it and writes a good answer back into it; the caller saves the dict to disk.
    """

    PROMPT_NAME: str = ""     # app/prompts/<PROMPT_NAME>.txt
    SCHEMA_NAME: str = ""     # app/schemas/<SCHEMA_NAME>.schema.json
    ATTEMPTS: int = 2         # how many times the question is asked before giving up

    def __init__(self, provider: str = "", ai_caller: Callable[[str, dict, dict], str | None] | None = None,
                 model: str = "", temperature: float = 0.0) -> None:
        self._provider: str = provider
        self._model: str = model
        self._temperature: float = temperature
        self._ai_caller: Callable[[str, dict, dict], str | None] | None = ai_caller
        self._warnings: list[str] = []

    def warnings(self) -> list[str]:
        """Things the officer should know about the last run (for example, a reply that was cut short)."""
        return list(self._warnings)

    def run(self, source: dict) -> dict | None:
        """Ask the question for this source. Returns the checked answer, or None if no usable
        answer came back (no connection, a reply that is not JSON, a reply that breaks the schema)."""
        self._warnings = []
        payload = self._payload(source)
        template = self._load_prompt(self.PROMPT_NAME)
        prompt = self._fill_prompt(template, source, payload)
        schema = self._schema(source)
        version = self._prompt_version(template)
        cache_payload = self._cache_payload(source, payload)

        saved = source.get("saved_replies")
        cached = self._cached(saved, cache_payload, version, schema)
        if cached is not None:
            return cached

        for attempt in range(1, self.ATTEMPTS + 1):
            self._warnings = []          # only the attempt that succeeds may leave warnings
            options = self._options(source)
            data = self._complete(prompt, schema, options)
            if data is None:
                logger.warning("%s: attempt %d gave no usable answer", type(self).__name__, attempt)
                continue
            data = self._post_process(data, options)
            answered_by = options.get("answered_by")
            if answered_by and self._model and answered_by != self._model:
                # A fallback model answered. Saving it under this model's name would make every
                # later run reuse the fallback's answer, even once the main model works again.
                logger.info("%s: answered by the fallback %s, so the answer is not saved for %s",
                            type(self).__name__, answered_by, self._model)
            else:
                self._save(saved, cache_payload, version, data)
            return data
        logger.error("%s: no usable answer after %d attempt(s)", type(self).__name__, self.ATTEMPTS)
        self._warnings = []
        return None

    # ----- what each child fills in ---------------------------------------------

    @abstractmethod
    def _payload(self, source: dict) -> dict:
        """The part of the source the AI may see. Nothing outside it is sent."""

    def _post_process(self, data: dict, options: dict | None = None) -> dict:
        """Finish a good answer before it is saved and returned. The parent changes nothing."""
        return data

    def _fill_prompt(self, template: str, source: dict, payload: dict) -> str:
        """Put the payload into the prompt text."""
        return template.replace("{payload_json}", json.dumps(payload, indent=2))

    def _schema(self, source: dict) -> dict:
        """The schema the answer must follow."""
        return self._load_schema(self.SCHEMA_NAME)

    def _cache_payload(self, source: dict, payload: dict) -> dict:
        """What makes two questions "the same question" for the saved answers."""
        return payload

    def _options(self, source: dict) -> dict:
        """Extra instructions for the AI caller (web search, attached documents, ...)."""
        return {}

    def _reply_as_asked(self, data: dict) -> dict:
        """A saved reply as the AI wrote it: without the fields _post_process added, which the schema
        does not allow. Used to check a saved reply against the schema again. The parent changes nothing."""
        return data

    def _prepare(self, data: dict) -> dict:
        """A change made to the reply before it is checked against the schema (for example,
        cutting an over-long list so the rest can still be used). The parent changes nothing."""
        return data

    # ----- what every child shares ------------------------------------------------

    def _complete(self, prompt: str, schema: dict, options: dict | None = None) -> dict | None:
        """Ask once. Returns the reply as a checked dict, or None if the call failed, the reply
        was not JSON, or it did not follow the schema."""
        if self._ai_caller is None:
            logger.warning("%s: no AI caller was given", type(self).__name__)
            return None
        options = options if options is not None else {}
        if self._model:
            options.setdefault("model", self._model)
        try:
            raw = self._ai_caller(prompt, schema, options)
        except Exception as error:   # a caller should return None on failure; this is the safety net
            logger.warning("%s: the AI caller raised %s", type(self).__name__, repr(error))
            return None
        data = self.__parse_reply(raw)
        if data is None:
            return None
        data = self._prepare(data)
        return data if self.__validate_reply(data, schema) else None

    def _build_prompt(self, instructions: str, user_text: str, schema: dict | None = None) -> str:
        """One prompt: the rules, the schema the answer must follow, then the data."""
        schema = schema or {}
        keys = list(schema.get("required") or schema.get("properties", {}).keys())
        return (instructions
                + "\n\nYour answer must be ONE JSON object whose top-level keys are "
                + ", ".join(f'"{key}"' for key in keys)
                + ", filled in with your answer. It must follow the JSON schema below. "
                  "Do NOT repeat or return the schema itself.\nSchema:\n"
                + json.dumps(schema, separators=(",", ":"))
                + "\n\nDATA:\n" + user_text + "\n\nAnswer with ONE JSON object.")

    def _redact_names(self, text: str, names: list[str], honorifics: list[str] | None = None) -> str:
        """Replace the client's name, including 'Mr Tan' style references, with 'the client'."""
        titles = r"(?:" + "|".join(re.escape(title) for title in honorifics or []) + r")\.?"
        words = {word for name in names for word in re.split(r"\s+", name or "") if len(word) > 1}
        # Longest words first, so a short name cannot break up a longer one
        for word in sorted(words, key=len, reverse=True):
            pattern = re.escape(word)
            if honorifics:
                text = re.sub(rf"\b{titles}\s+{pattern}\b", "the client", text, flags=re.IGNORECASE)
            text = re.sub(rf"\b{pattern}\b", "the client", text, flags=re.IGNORECASE)
        return text

    def _load_prompt(self, name: str) -> str:
        with open(os.path.join(APP_DIR, "prompts", f"{name}.txt"), encoding="utf-8") as handle:
            return handle.read()

    def _load_schema(self, name: str) -> dict:
        with open(os.path.join(APP_DIR, "schemas", f"{name}.schema.json"), encoding="utf-8") as handle:
            return json.load(handle)

    def _prompt_version(self, prompt_text: str) -> str:
        """The value of the first '# prompt_version: ...' line, or 'unknown'."""
        for line in prompt_text.splitlines():
            if line.strip().startswith("# prompt_version:"):
                return line.split(":", 1)[1].strip()
        return "unknown"

    def _without_notes(self, template: str) -> str:
        """The prompt text without its '#' note lines, which are for people and are not sent."""
        return "\n".join(line for line in template.splitlines() if not line.startswith("#")).strip()

    def _cached(self, saved: dict | None, cache_payload: dict, version: str, schema: dict) -> dict | None:
        """The reply saved for this step, if it answers this same question and still follows the schema.
        A copy is returned, so the caller cannot change what is saved."""
        if not isinstance(saved, dict):
            return None
        entry = saved.get(self.PROMPT_NAME)
        if not isinstance(entry, dict) or not isinstance(entry.get("reply"), dict):
            return None
        if entry.get("question") != self.__question_print(cache_payload, version):
            logger.info("%s: the saved reply answers a different question, so the AI is asked again",
                        type(self).__name__)
            return None
        reply = copy.deepcopy(entry["reply"])
        if not self.__validate_reply(self._reply_as_asked(copy.deepcopy(reply)), schema):
            logger.warning("%s: the saved reply no longer follows the schema, so the AI is asked again",
                           type(self).__name__)
            return None
        return reply

    def _save(self, saved: dict | None, cache_payload: dict, version: str, data: dict) -> None:
        """Keep a good answer in the client's saved replies (when the run has them)."""
        if not isinstance(saved, dict):
            return
        saved[self.PROMPT_NAME] = {"question": self.__question_print(cache_payload, version),
                                   "reply": copy.deepcopy(data)}

    def __question_print(self, cache_payload: dict, version: str) -> str:
        """SHA-256 of the question: its kind, model, payload and prompt version."""
        canonical = json.dumps({"kind": self.PROMPT_NAME, "model": self._model, "payload": cache_payload,
                                "prompt_version": version}, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def __parse_reply(self, raw: str | None) -> dict | None:
        """The JSON object inside the reply (it may be wrapped in a ``` block), or None."""
        if not raw or not str(raw).strip():
            logger.warning("%s: empty reply", type(self).__name__)
            return None
        text = str(raw).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1]).strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            logger.warning("%s: the reply is not JSON: %s", type(self).__name__, repr(error))
            return None
        return data if isinstance(data, dict) else None

    def __validate_reply(self, data: dict, schema: dict) -> bool:
        """True if the reply follows the schema."""
        try:
            jsonschema.validate(instance=data, schema=schema)
            return True
        except jsonschema.ValidationError as error:
            logger.warning("%s: the reply does not follow the schema: %s", type(self).__name__, error.message)
            return False
        except Exception as error:   # a broken schema file
            logger.warning("%s: the schema could not be used: %s", type(self).__name__, repr(error))
            return False
