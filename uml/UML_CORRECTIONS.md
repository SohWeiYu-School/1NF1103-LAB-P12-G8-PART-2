# UML corrections log

The UML class diagram (v4) was reviewed by the professor and is the **source of truth**. When the code
and the diagram differ, the code is changed to match the diagram.

The diagram itself is changed only in three cases, and every such change is listed here with its reason:

| Reason code | Meaning |
|---|---|
| **T** | **Technically wrong**: the diagram states something the language or framework makes impossible (e.g. a Flask redirect cannot be a `str`). |
| **B** | **Below review level**: a detail the design review did not cover (private helpers, constants, defaults). It is added so the diagram shows the real code. |
| **R** | **Rule**: following the diagram would break a graded CLAUDE.md rule. |

## Stage 2: type hints (2026-11-15): 10 corrections

| Class | Member | Was | Now | Reason |
|---|---|---|---|---|
| WebApp | `find()` | `: str` | `: Response` | **T**: it only ever returns `redirect(...)`, which is a werkzeug `Response` object |
| WebApp | `upload_documents(client_ref)` | `: str` | `: Response` | **T**: always `redirect(...)` |
| WebApp | `sync_to_cloud()` | `: str` | `: Response` | **T**: always `redirect(...)` |
| WebApp | `assess_client(client_ref)` | `: str` | `: Response` | **T**: always `redirect(...)` |
| WebApp | `download_document(client_ref, file_id)` | `: None` | `: Response` | **T**: returns `send_file(...)` or `redirect(...)`; a Flask view must return a response |
| WebApp | `new_client()` | `: str` | `: str \| Response` | **T**: shows the form (HTML text) or redirects after saving |
| WebApp | `edit_client(client_ref)` | `: str` | `: str \| Response` | **T**: shows the form (HTML text) or redirects after saving |
| WebApp | `assess_result(job_id)` | `: str` | `: str \| Response` | **T**: shows the report (HTML text) or redirects while the job is running or missing |
| CaseReader | `read_amount(text)` | `text : str` | `text : str \| int \| float \| None` | **T**: saved records and form answers hold amounts as text **or** numbers, and its tests pass `30`, `None` and `True` |
| CaseReader | `read_year(text)` | `text : str` | `text : str \| int \| float \| None` | **T**: same as `read_amount`, which it calls |

Kept as the diagram says, because the code was changed to match instead:
- `WebApp.assess_poll(job_id) : dict`: Flask sends a dict returned from a page as JSON, so the code now
  returns a dict instead of `jsonify(...)`. (An independent review caught that this one was not technically wrong.)

Kept as the diagram says, because the code will be changed to match in a later step:
- `ClientForm.create_new_client : ClientRecord | None` and `edit_existing_client : ClientRecord`: the dict → model refactor (R1) makes the code return a `ClientRecord`. Until then, the code is typed with what it really returns (`dict | None`, `None`).
- `ConsoleUI.keep_money(current : float) : float`: stage 3 replaces `""` with `None` for an empty value (CLAUDE.md §9). The diagram is then corrected once, to the final type.

## Stage 3, batch A: AI Manager (2026-11-16): 27 corrections

Code changed to match the diagram: ForecastAI's 8 step/check helpers became private (`__forecast_markets`,
`__check_declaration`, …), and `read_declaration` lost its unused `cache` parameter.

Everything below is the diagram being corrected, because the code is technically right:

| Class | Member | Correction | Reason |
|---|---|---|---|
| AIService | `_ai_caller`, `_response_cache`, `__init__` | `… \| None = None` | **T**: "no AI caller" / "no cache" are real states (no API key, tests); the code checks for `None` |
| AIService, ResearchAI, TypologyAI, ForecastAI | `_post_process(data)` | `+ options : dict \| None = None` | **T/R**: the caller's options (`raw_response`, `answered_by`) are passed in; keeping them on `self` would be shared state across parallel web threads |
| AIService | `_complete(…, options : dict = {})` | `options : dict \| None = None` | **T**: a shared `{}` default would leak values from one call into the next |
| AIService | `_build_prompt`, `_redact_names` | `+ schema`, `+ honorifics` parameters | **T**: ForecastAI passes them; the prompt text depends on them |
| AIService | `__parse_reply(raw : str)` | `raw : str \| None` | **T**: an AI caller returns `None` on failure |
| ResponseCache | `get`, `__key` | `+ prompt_version : str = ""` | **T**: the prompt version is part of the cache key; without it every saved reply would be missed |
| ForecastAI, ResearchAI, TypologyAI, BenchmarkAI, DocumentAI | `__init__` | real parameters and defaults (`settings`, `vocabulary` for ForecastAI) | **T**: App passes them, and `None` caller/cache when there is no API key |
| ForecastAI | `read_declaration : Declaration` | `: Declaration \| None` | **T**: `None` when the AI gives no usable reading (the step then fails honestly) |
| ForecastAI | the 8 private step/check helpers | their real parameters, steps return `dict \| None` | **T**: they need these inputs; a step returns `None` at the first failure |

Layout: the AI service boxes grew, so the right-hand column was re-stacked, the AI Manager folder grew to fit,
and two multiplicity labels were moved out of the grown boxes.
