# CLAUDE.md — AI Coding Assistant Conventions

This file tells AI coding assistants how to behave in this repo.
Follow these rules to keep the codebase consistent and assessable.

Part 2 of the project is an object-oriented refactor. The target design is the
UML class diagram (v4). Code is being moved into classes one piece at a time, so
for a while the old manager files (`app/*_manager.py`) and the new folders exist
side by side.

---

## 1. Object-Oriented Code (Graded)

**New code goes into classes that match the UML class diagram.**
No procedural-style code should be left by the end of the refactor.

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
| `app/interface/` | IO Manager | `ConsoleUI`, `ReportView`, `ClientForm`, `CaseBuilder`, `WebApp`, `RateLimiter` |
| `app/ai/` | AI Manager | `AIService` and its children, `ResponseCache`, the AI caller functions |
| `app/logic/` | Logic Manager | `VerdictEngine`, `Feature` and its children, `Indicator` and its children, the forecast classes |
| `app/data/` | Data Manager | The repositories, `CloudSync`, `DocumentStore`, the document readers, `ConfigReader` |
| `app/model/` | Domain Model | Shared data objects (`ClientRecord`, `Verdict`, `Check`, `Band`, `Config`, ...) |

---

## 3. Managers Never Import Each Other (Graded)

The four managers (`app/interface`, `app/ai`, `app/logic`, `app/data`) must never
import from each other, and must never import from `app/application`.
All coordination happens in `app/application`.

- Any group may import from `app/model`.
- The one exception is `WebApp`, which calls `App`.

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

When a piece of code moves into a class, its tests move with it in the same commit.

---

## 8. Commits and Branches

- Never push straight to `main`. Work on a branch (`refactor/...`, `chore/...`,
  `test/...`, `docs/...`) and merge it.
- Keep commits small: one class (or one small family of classes) per commit.
- The tests must pass on every commit.
