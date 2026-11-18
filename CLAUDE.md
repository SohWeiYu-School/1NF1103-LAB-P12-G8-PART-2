# CLAUDE.md — AI Coding Assistant Conventions

This file tells AI coding assistants how to behave in this repo.
Follow these rules to keep the codebase consistent and assessable.

Part 2 of the project is object-oriented. The design is the UML class diagram (v4).
The old procedural manager files are gone; `tests/test_manager_boundaries.py` fails
if one comes back or if a manager imports another.

---

## 1. Object-Oriented Code (Graded)

**All code goes into classes that match the UML class diagram.**
The only module-level functions are the AI caller functions in `app/ai/ai_caller.py`.

- Every class has an `__init__`. Every attribute has a type and a default value.
- A child class calls `super().__init__` with all of the parent's inputs plus its own.
- The class that owns an attribute validates it (in `__init__` or its setter).
  There is no separate checker class.
- Private attributes and methods use two leading underscores (`__name`).
  Protected ones (shared with children) use one (`_name`).
- A class with no attributes that only runs functions is a leftover: move the work
  to the class that owns the inputs. `Formatter` (a utility) is the only exception.

---

## 2. Folder Layout

| Folder | Group | What lives there |
|---|---|---|
| `main.py` | Entry point | Picks the AI brand and starts `App`. Nothing else. |
| `app/application/` | Application | `App`, `AssessmentRunner`. The only place that coordinates the managers. |
| `app/interface/` | IO Manager | `ConsoleUI`, `ReportView`, `ClientForm`, `CaseBuilder`, `TerminalApp`, `WebApp` (and its page templates in `web_templates.py`), `RateLimiter` |
| `app/ai/` | AI Manager | `AIService` and its children, `ResponseCache`, the AI caller functions |
| `app/logic/` | Logic Manager | `VerdictEngine`, `RiskAnalysis` and its children, `Indicator` and its children, the forecast classes, `CaseReader`, `DocumentRecordBuilder`, `CaseTimeline`, `Formatter` |
| `app/data/` | Data Manager | The repositories, `CloudSync`, `DocumentStore`, the document readers, `ConfigReader`, `CaseFiles` |
| `app/model/` | Domain Model | Shared data objects (`ClientRecord`, `Verdict`, `Check`, `Band`, `Config`, ...) |

---

## 3. Managers Never Import Each Other (Graded)

The four managers (`app/interface`, `app/ai`, `app/logic`, `app/data`) must never
import from each other, and must never import from `app/application`.
All coordination happens in `app/application`.

- Any group may import from `app/model`.
- The exceptions are `WebApp` and `TerminalApp`, the two front ends, which call `App`.

```python
# app/application/app.py — correct
from app.ai.research_ai import ResearchAI
from app.data.client_repository import ClientRepository

# app/ai/research_ai.py — WRONG, do not do this
from app.data.client_repository import ClientRepository
```

---

## 4. Print/Input Rule (Graded)

**All `print()` and `input()` calls must live in the IO Manager (`ConsoleUI`).**

Other classes return values — never print directly.

---

## 5. The Logic Manager is Pure

Classes in `app/logic` do no file access, no network calls and no printing.
The same inputs always produce the same output.

---

## 6. AI Allowlist

The benchmark AI call must never include the client's declared figures.
Only these fields may be sent:

```python
ALLOWED_FIELDS = ["occupation", "industry", "age", "career_start_year", "country"]
```

Do not add to this list without team agreement.

---

## 7. Tests

Use pytest plain functions only — no `unittest.TestCase`.
Tests use hard-coded sample AI replies; they never call a real AI service.

```python
def test_something():
    assert result == expected
```

Each class has its own test file, `tests/test_<group>_<class>.py`, changed in the same
commit as the class. To stand in for the AI, give the class a made-up caller
(`tests/fake_ai.caller`) or made-up services (`tests/fake_services.py`); do not patch
module functions.

---

## 8. Commits and Branches

- Never push straight to `main`. Work on a branch (`refactor/...`, `chore/...`,
  `test/...`, `docs/...`) and merge it.
- Keep commits small: one class (or one small family of classes) per commit.
- The tests must pass on every commit.

---

## 9. Validation and Error Handling (Graded)

Validation and honest error handling are graded priorities in this module.

### Validate every input

- **Every input must be validated:** user input, uploaded files, saved data being
  loaded, config, and every AI reply (checked against its JSON schema before use).
- When touching existing code, **check that its validation is correct:** the right
  limits, the right fields, and nothing missing. New code must validate the data it accepts.
- Reject impossible values with a clear message saying what is wrong and what is allowed.
- Setters reject only *impossible* values (e.g. age 18–120, price > 0, values ≥ 0,
  `payment_method` in the allowed set, shares 0–1). *Consistency* rules go in the
  `problems()` / `warnings()` lists on `Job`, `Claims` and `ClientRecord`, so auto-fill
  from documents still works.

### Never crash, never hide an error

**The app must never crash on an error, but it must never act as if there was no error.**

| Situation | Wrong | Right |
|---|---|---|
| The JSON file or database can't be read | Return an empty list, so the user sees "no clients" | Raise or return an error, and tell the user "We can't load the client database right now. Please try again later." |
| An AI step fails (no key, timeout, bad reply) | Skip it and still show PASSED | Mark the step as **not run**. The verdict can't be PASSED, and the user sees "The AI service is not available right now." |
| Saving fails | Carry on as if it saved | Tell the user it was **not saved** |
| Any other logic error | Return a default value that looks like a real result | Report that the step failed |

- **Empty and broken are different things.** An empty database means "no records yet".
  A database error means "something is wrong". Code and user messages must keep them
  separate. Never use an empty result as an error fallback.
- Every caught exception is **logged with the real details** (for developers) **and**
  reported upward, so the orchestrator (`App`) decides what to do. `AssessmentRunner`
  reports through its `on_failure` callback; `App` checks `CRITICAL_STEPS` and decides.

### What the user sees

- **Be honest that there is a problem, but hide the technical details.**

| Don't show | Do show |
|---|---|
| `OPENAI_API_KEY is not set`, or a stack trace | "The AI service is not available right now. Please try again later." |
| `connection refused: mongodb+srv://...` | "The database has a problem right now. Please come back later." |

- The message must describe the **real kind of problem** (database, AI, file, save).
  Never say something misleading like "no data found" when the real cause is an error.
- The real technical error goes to the **log**, not the screen.
