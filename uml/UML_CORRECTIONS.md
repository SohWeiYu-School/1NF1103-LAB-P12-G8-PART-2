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

## Stage 3, batch A: AI Manager (2026-11-15): 27 corrections

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
| ResponseCache | `get`, `__key` | `+ prompt_version : str = ""` | **T**: the prompt version is part of the cache key, so a changed prompt correctly misses replies saved for the old prompt; without it, stale replies would be reused |
| ForecastAI, ResearchAI, TypologyAI, BenchmarkAI, DocumentAI | `__init__` | `ai_caller : Callable \| None`, `response_cache : ResponseCache \| None`, and `settings`/`vocabulary` for ForecastAI | **T**: the base class handles a missing caller or cache, App gives ForecastAI and DocumentAI no caller when there is no API key, and App passes ForecastAI its settings and vocabulary. The added defaults (`= ""`, `= 0.0`) are **B** (below review level) |
| ForecastAI | `read_declaration : Declaration` | `: Declaration \| None` | **T**: `None` when the AI gives no usable reading (the step then fails honestly) |
| ForecastAI | the 8 private step/check helpers | their real parameters, steps return `dict \| None` | **T**: they need these inputs; a step returns `None` at the first failure |

Layout: the AI service boxes grew, so the right-hand column was re-stacked and the AI Manager folder grew to fit
(the Application folder also grew by 15 px, harmlessly). Connector bends next to the moved boxes were re-levelled so
the lines keep their right angles (an independent review caught that they had gone diagonal), and three
multiplicity labels were moved back beside their lines.

## Stage 3, batch B: IO Manager and Application (2026-11-15): 45 corrections

Code changed to match the diagram:
- ConsoleUI is handed its `read`/`write` functions, and its helpers are private.
- `keep_money` keeps an empty amount as `None` (CLAUDE.md §9).
- `ask_money` refuses zero unless the caller allows it.
- ClientForm's helpers and CaseBuilder's four listed helpers are private (CaseBuilder's other `_` helpers are a stage 5 item).
- ReportView is handed its `width`, RateLimiter its cooldown, and WebApp its RateLimiter.
- App's case and documents screens are private, and `App.today` is static.
- `AssessmentRunner.run` names its parameter `files`.

Everything below is the diagram being corrected:

| Class | Member | Correction | Reason |
|---|---|---|---|
| ConsoleUI | `__init__(read, write)` | `Callable \| None = None` (the attributes fall back to `input`/`print`) | **T**: a default bound to `input` at class definition would ignore a swapped `builtins.input`, which App's console tests rely on |
| ConsoleUI | `ask_int`, `ask_year` | `minimum`/`maximum : int \| None`, `allow_blank`, returns `int \| None` | **T**: callers pass "no limit" and blank-for-current answers |
| ConsoleUI | `ask_choice`, `keep_text` | `+ allow_back`, `+ min_length` | **T**: the assessment list and the declaration edit pass them |
| ConsoleUI | `keep_money` | `current : float \| None) : float \| None` | **T/R**: an empty amount is `None` (CLAUDE.md §9); this is the correction stage 2 deferred |
| ConsoleUI | `money`, `money_range` | `value : float \| None`; `values : dict` (not `Band`) | **T**: forecast rows pass `None`; the range is given as a dict |
| ConsoleUI | `+keep_countries(...)` | added | **B**: replaces ClientForm reaching into ConsoleUI's private `__only` |
| ClientForm | `__init__` | `+ report_view` | **T**: App hands in the shared ReportView |
| ClientForm | `create_new_client`, `edit_existing_client` | `+ save_fn`, `+ upload_fn` (`edit_existing_client` takes only `upload_fn`) | **R**: ClientForm (IO Manager) may not import the Data Manager or App (§3), so App passes these functions in |
| ClientForm | `__edit_*_record(record)` | `record : dict` | **T**: they edit the answers dict, which is checked as a whole afterwards |
| ClientForm | `__ask_job` | `+ previous : bool = False` | **T**: a previous job must have an end year (the R1 data-loss fix) |
| CaseBuilder | `__init__` and its 4 helpers | real parameters (`case_schema`, year limits, `allow_zero`) | **T**: `validate_case` needs the schema; jobs and assets have different date limits |
| ReportView | `__init__`, `show_verdict_report`, `__format_crime_section` | real parameters (`width = REPORT_WIDTH`, `ask_for_evidence`, `crime_result`, `typologies`) | **T**: the crime cards need the crime result and typologies, which a Verdict doesn't hold |
| ReportView | `+MIN_WIDTH` | added | **B**: the lower limit checked for `width` |
| RateLimiter | `__init__` | `cooldown_seconds = DEFAULT_COOLDOWN_SECONDS, + enabled` | **T**: the policy can switch the limit off |
| WebApp | `__app`, `__limiter`, `__init__` | `\| None = None` | **T**: without a limiter WebApp uses the App's own |
| WebApp | `__jobs` | `dict[str, dict]` | **T**: it stores each job's status, not the thread |
| WebApp | `view_client`, `edit_client_autofill` | `: str \| Response` | **T**: they redirect when a record can't be loaded |
| App | `__ai_caller`, `__init__` | `Callable \| None`, `+ root`, `+ data_folder` | **T**: "no AI caller" is a real state; tests use a temporary data folder |
| App | `__assessments` | `AssessmentRepository` (not `Repository`) | **T**: App and WebApp call `query`/`for_client`, which the Repository interface doesn't have |
| App, AssessmentRunner | `CRITICAL_STEPS`, `STEPS` | `tuple[str, ...]` | **B**: immutable constants, shared safely by the web threads |
| App | `list_assessments : list[dict]` | `: None` | **T**: it is an interactive menu screen; the web reads `assessments()` |
| AssessmentRunner | `__init__` | the separate services, store and cache | **T**: it calls methods specific to each service; it also needs the DocumentStore and ResponseCache |
| AssessmentRunner | `run : Verdict` | `files … \| None = None`, `: dict \| None` | **T**: App saves the research, typologies and other results a Verdict doesn't hold, and the runner is shared by parallel threads, so it can't keep them |

Layout: the IO Manager boxes grew, so the right-hand column was re-stacked and `CaseBuilder` moved under
`RateLimiter` (left column) to stay inside its folder. `RateLimiter` was widened so its `__init__` line isn't cut
off, and multiplicity labels were moved out of grown boxes. **Not finished (found by the independent review):** some
connectors around the IO Manager and Application boxes now run through boxes, and three "1" labels are away from their
lines. This is follow-up #31, the first task of the next session.
