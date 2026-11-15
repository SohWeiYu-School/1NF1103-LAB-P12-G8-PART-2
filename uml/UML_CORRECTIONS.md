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

## Layout fix after stage 3 batch B (follow-up #31)

No member text changed. Connectors that ran through boxes after earlier stages now take right-angled routes through
the gaps between columns. A new automatic check (`layout_check.py`) finds lines through boxes, overlaps, cut-off text and
labels inside boxes, and reports 0. Its fixes:
- WebApp↔App, App→ConsoleUI and CaseBuilder→ConsoleUI use the gap between the two IO columns.
- CaseBuilder→ClientRecord and ReportView→Verdict drop below the boxes first.
- App→Config and App→ResponseCache leave App below AssessmentRunner.
- `CaseFiles` moved 100 px right, off the DocumentReaderFactory→DocumentReader line.
- The Indicator→Declaration bend moved below CaseReader.
- The original WebApp→ClientRecord diagonal is replaced by a route over the top and down the right.
- `VerdictEngine` was widened so its `__init__` fits.
- The App→CaseBuilder line is vertical.
- Three "1" labels sit beside their lines again.

## Stage 3, batches C+D: Logic Manager, Data Manager and Domain Model (2026-11-15): 84 corrections

The count is the changed member lines in `class_diagram_v4.puml`.

Code changed to match the diagram:
- Each class's diagram helpers are private (`__x`): Benchmark, CrimeScan (including its country table), DocumentRecordBuilder, Forecast, OnboardingAssessor, CaseReader (`__PRESENT_WORDS`) and VerdictEngine (`__agreement`, `__type_patterns`, `__evidence`).
- `CaseReader.read_year` is static.
- The untyped private helpers the renames exposed now have types: Benchmark's six rule helpers, `DocumentRecordBuilder.__age_from_birth`, and CrimeScan's `__to_iso` and `__categorise_match` (lists of strings, as the diagram had them).

Everything below is the diagram being corrected:

| Class | Member | Correction | Reason |
|---|---|---|---|
| 16 classes: the 6 Indicator classes, RiskAnalysis, CrimeScan, DocumentEvidence, Benchmark, Forecast, MarketModel, CareerSavings, Check, Declaration, Verdict | `__init__(policy : dict = {})` and similar | `dict \| None = None` / `list \| None = None` | **T**: a `{}` or `[]` default is one object shared by every instance in Python. The code creates a new one in `__init__` |
| Check, Claims, Job, Investment, ClaimedSource, Typology, ResearchReport, MatchResult, Verdict, Config | `__init__` | every parameter has a default; `+ extra : dict \| None` where the class keeps unknown keys | **T**: `from_dict` builds partly filled objects from saved files and documents, and `to_dict` must give back the keys it was given (R1–R5 round-trip tests) |
| ClaimedSource, Typology, ResearchReport | `__init__` | the fields merged in R4/R5 (`source_id`, `quote`, `crime_category`, `source_quotes`, `organisation`, ...) | **T**: the two declaration shapes and the AI's typology/report replies carry these, and the report shows them |
| Job, Investment | `__start_year`, `__year_acquired`, `__current_declared_value`, `__income_produced` | `int \| None` / `float \| None` | **R**: an unknown year or amount is `None`, not a fake `0` (CLAUDE.md §9). The starting values are `None` too, as in the code |
| ClientRecord, CloudSync | `__claims`, `__local`, `__remote` | `\| None` | **T**: each can really be absent (no declaration yet; no database configured) |
| CloudSync, ConfigReader, DocumentStore, JsonRepository | folder/path parameters and `DATA_DIR` | paths built from `ROOT_DIR`; DocumentStore `+ root` | **T**: a relative path depends on the folder the app is started from. Tests pass a temporary root |
| UnvaluedSource | `NAME` | `"unvalued_source_present"` | **T**: the saved name that the policy and saved checks use |
| DocumentStore | `read_for_extraction` | `+ file_name` | **T**: uploads are saved under a random name; the reader needs the original extension |
| DocumentReaderFactory | `supported_types` | `: list[str]` | **T**: shown to the user in a fixed order |
| DocumentRecordBuilder | `__init__`, `build`, `missing_fields`, `summarise` | `config`/`today` in, `client_ref` per build, real return types | **R**: one builder is shared by web threads, so a per-client value can't be kept on it (CLAUDE.md §5: same inputs, same output) |
| AssetPath, CareerSavings, FuturePaths, MarketModel, OnboardingAssessor, PayCalibrator, Forecast | method parameters | the rows, paths and scenario each method is handed (`savings_rows`, `paths`, `scale`, `shocks`, ...) | **R**: these were drawn as values kept on the object. The forecast classes are pure and shared, so they receive them as inputs (CLAUDE.md §5; the concurrency fixes #19 and #25) |
| OnboardingAssessor, Forecast, FuturePaths, PayCalibrator, RiskAnalysis | return types | the real ones (`tuple[str, bool]`, `list[dict]`, `tuple[float \| None, int \| None]`, ...) | **T**: callers unpack and read these shapes |
| CaseReader | `forecasting_case` | `: tuple[dict \| None, list[str]]` | **T**: `None` when the record can't be forecast; the list holds the reasons |
| CrimeScan | `__domain_is_trusted`, `__to_iso` | `+ trusted_domains`; `value : str \| None, + warnings : list[str]`, `: str \| None` | **T**: the trusted list comes from the policy; an unknown country is reported as a warning |
| VerdictEngine | `__init__`, `describe_piece`, `__agreement`, `__type_patterns`, `__evidence` | `\| None` defaults; the real inputs and `list[dict]` returns | **T** for the `\| None` types and `list[dict]` returns: any step result may be missing (not run), and the report builds its cards from these lists. **B** for the private helpers taking the separate step results instead of one `results` dict: a design choice below review level |
| Benchmark | six rule helpers | real return types (`float`, `list[dict]`, a tuple, `list[str]`); parameters `client_data`/`ai_data` | **T** for the return types: the diagram's `: dict` was wrong for all six. **B** for the parameter names on private helpers; the code's types were added to match |

Layout: the Logic Manager boxes grew. `FuturePaths` was widened, `AssetPath` and `CareerSavings` moved down 40 px, and the lines out of FuturePaths, Benchmark→Config and ForecastAI→Declaration were re-routed around the grown boxes. `UnvaluedSource` and `JsonRepository` were widened, and two multiplicity labels (CrimeScan→Indicator, Verdict→Check) sit next to their target box again. `layout_check` reports 0.

## Stage 4: in the diagram, missing in the code (2026-11-15): 26 diagram edits

Code changed to match the diagram (24 of the 36 items):
- Renamed to the diagram's names: `App.__limiter`, `__syncs`, `__maybe_assess`; `AssessmentRunner.__verdict_engine`; `RateLimiter.__last_run`; `WebApp.start`, `__run_in_background`; `CaseBuilder.build` (was `case_from_client_record`); `ForecastAI.__check_markets`, `__check_pay` (were `_check_markets_list`, `_check_future_pay`).
- New constants: `ConfigReader.FILE_NAMES`, `DocumentReaderFactory.READER_TYPES`.
- New thin methods on App, each with a test: `client_assessments`, `find_assessment`, `upload_document`, `download_document`. WebApp and ClientForm now call them.
- Code extracted into the diagram's methods: `VerdictEngine.__build_context`, `__collect_checks`; `ClientForm.pick_client`.
- Moved to the class the diagram names: `CaseBuilder.show_case_problems` and `ClientForm.ask_document_folder` (from ConsoleUI), and `ReportView.show_client_list`, `show_ai_progress` and `__display_section` (from ConsoleUI).

Everything below is the diagram being corrected:

| Class | Member | Correction | Reason |
|---|---|---|---|
| App | `-__case_reader` | removed | **T**: a CaseReader holds the assessment date. A stored one would keep yesterday's date in the long-running web server, so App makes one per case |
| CaseBuilder, DocumentRecordBuilder | `-__today`, `-__client_ref` | removed | **R**: the date and the client are per call. These objects are shared by web threads (CLAUDE.md §5; stage 3 C+D) |
| AssessmentRunner | `-__ai : dict[str, AIService]`, `-__features : list[RiskAnalysis]` | removed | **T**: the runner calls methods that only exist on each service and analysis, so it keeps them as separate typed attributes (stage 3 batch B) |
| AssessmentRunner | `-__run_ai_steps(case)` | removed | **T**: the AI calls are interleaved with the logic steps under the crime-scan and forecast locks, and share the step and failure callbacks. One block would change the order or the callbacks |
| ForecastAI | `-__repair(data, errors)` | removed | **T**: there is no single repair step. Each of the four repairs takes its own inputs and runs before its check, not from an error list |
| ForecastAI | `__check_markets`, `__check_pay` | `+ forecast_years : list[int]` | **T**: the checks compare the reply's years with the forecast years |
| App | `+autofill_from_documents(paths)` | removed | **T**: reading the documents is interleaved with the officer's choices (type it in when the AI is down, retry with a blank record, fill missing fields), so there is no non-interactive part to extract. The work is in `__new_client_from_documents`, `read_documents` and `record_builder` |
| App | `upload_document` | `(file_path : str) : str \| None` | **T**: the document is kept before the record exists (new-client form), and the caller stores the returned document id |
| CaseBuilder | `build` | `(record : ClientRecord)`, without `missing` | **T**: App shows the missing fields before it calls `build`; they are not an input to building the case |
| CaseBuilder | `show_case_problems` | `problems : list[str]` | **B**: element type |
| ClientForm | `pick_client` | `(find_fn : Callable[[str], ClientRecord \| None] \| None = None)` | **R**: it asks for a reference and looks it up. ClientForm can't import the Data Manager (§3), so App passes the lookup in |
| ClientForm, ConsoleUI | `PAYMENT_METHODS`, `PEP_OPTIONS` | moved to ClientForm | **B**: ConsoleUI never uses them. ClientForm asks with them, CaseBuilder reads `ClientForm.PAYMENT_METHODS`, and WebApp's form reads `ClientForm.PEP_OPTIONS` |
| ClientForm → ReportView | `SOURCE_TAGS` | moved to ReportView | **T**: only ReportView uses it, and ReportView can't import ClientForm (ClientForm already imports ReportView) |
| VerdictEngine → CrimeScan | `MATCH_LABELS` | moved to CrimeScan | **T**: CrimeScan uses it itself, and VerdictEngine already imports CrimeScan, so CrimeScan can't import VerdictEngine |
| VerdictEngine | `__collect_checks` | `: dict[str, list[Check]]` | **T**: `combine()` needs the benchmark, forecast, crime and document checks as separate groups |
| DocumentReaderFactory | `READER_TYPES` | `dict[str, type[DocumentReader]]` | **B**: exact type |
| WebApp | `start` | `host = "127.0.0.1"`, `+ debug : bool = False` | **R**: `"0.0.0.0"` would open the server to the whole network (§9 security); `debug` is passed to Flask for local runs |
| WebApp | `__run_in_background` | `+ case : dict` | **T**: the case is built (and checked) in the request before the thread starts, so problems are shown to the user straight away |

Layout: `Indicator` moved down 40 px under the grown CrimeScan box. The CrimeScan→Declaration and CaseBuilder→ClientRecord lines were re-routed, and the "5" label was moved. `layout_check` reports 0.
