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
| App | `-__case_reader` | removed | **T**: a CaseReader holds the assessment date. A stored one would keep yesterday's date in the long-running web server, so App makes one per case. The `App *-- CaseReader` line still shows ownership; it becomes a dependency in stage 7 (relationships) |
| CaseBuilder, DocumentRecordBuilder | `-__today`, `-__client_ref` | removed | **R**: the date and the client are per call. These objects are shared by web threads (CLAUDE.md §5; stage 3 C+D) |
| AssessmentRunner | `-__ai : dict[str, AIService]`, `-__features : list[RiskAnalysis]` | removed | **T**: the runner calls methods that only exist on each analysis (`verify_research`, `read_typologies`, `calibrate_pay`, `economy_brief`, ...), so the analyses are separate typed attributes. The AI services only need `run()`, but each takes a different input at a fixed point in the steps, so they are separate typed attributes too (stage 3 batch B) |
| AssessmentRunner | `-__run_ai_steps(case)` | removed | **T**: the AI calls are interleaved with the logic steps under the crime-scan and forecast locks, and share the step and failure callbacks. One block would change the order or the callbacks |
| ForecastAI | `-__repair(data, errors)` | removed | **T**: there is no single repair step. Each of the four repairs takes its own inputs and runs before its check, not from an error list |
| ForecastAI | `__check_markets`, `__check_pay` | `+ forecast_years : list[int]` | **T**: the checks compare the reply's years with the forecast years |
| App | `+autofill_from_documents(paths)` | removed | **T**: the callers need more than `(ClientRecord, list[str])`. The CLI needs the AI's raw reading for its notes, and must tell "AI unavailable" apart from "the reading is not a possible record" to offer typing it in. The web form fills form fields from the raw reading, not a ClientRecord. The work is done by `read_documents` and `record_builder().build` |
| App | `upload_document` | `(file_path : str) : str \| None` | **T**: the document is kept before the record exists (new-client form), and the caller stores the returned document id |
| CaseBuilder | `build` | `(record : ClientRecord)`, without `missing` | **T**: App shows the missing fields before it calls `build`; they are not an input to building the case |
| CaseBuilder | `show_case_problems` | `problems : list[str]` | **B**: element type |
| ClientForm | `pick_client` | `(find_fn : Callable[[str], ClientRecord \| None] \| None = None)` | **T**: the officer types a client reference; there is no pick-from-a-list screen. Loading every record to choose one would change what the user sees. App passes the lookup in (ClientForm can't import the Data Manager, §3) |
| ClientForm, ConsoleUI | `PAYMENT_METHODS`, `PEP_OPTIONS` | moved to ClientForm | **B**: ConsoleUI never uses them. ClientForm asks with them, CaseBuilder reads `ClientForm.PAYMENT_METHODS`, and WebApp's form reads `ClientForm.PEP_OPTIONS` |
| ClientForm → ReportView | `SOURCE_TAGS` | moved to ReportView, `dict[str, str]` | **T**: only ReportView uses it, and ReportView can't import ClientForm (ClientForm already imports ReportView) |
| VerdictEngine → CrimeScan | `MATCH_LABELS` | moved to CrimeScan, `dict[str, str]` | **T**: CrimeScan uses it itself, and VerdictEngine already imports CrimeScan, so CrimeScan can't import VerdictEngine |
| VerdictEngine | `__collect_checks` | `: dict[str, list[Check]]` | **T**: `combine()` needs the benchmark, forecast, crime and document checks as separate groups |
| DocumentReaderFactory | `READER_TYPES` | `dict[str, type[DocumentReader]]` | **B**: exact type |
| WebApp | `start` | `host = "127.0.0.1"`, `+ debug : bool = False` | **T**: `"0.0.0.0"` is an unsafe default that opens the server to the whole network; the container sets its host explicitly. `debug` is passed to Flask for local runs |
| WebApp | `__run_in_background` | `+ case : dict` | **T**: the case is built (and checked) in the request before the thread starts, so problems are shown to the user straight away |

After the review: DocumentReaderFactory reads `READER_TYPES` directly (it kept an unchanged copy), `SOURCE_TAGS` and `MATCH_LABELS` are typed, and the `show_ai_progress` tests moved to ReportView's test file.

Layout: `Indicator` moved down 40 px under the grown CrimeScan box. The CrimeScan→Declaration and CaseBuilder→ClientRecord lines were re-routed, and the "5" label was moved. `layout_check` reports 0.

## Stage 6: default and starting values (2026-11-15): 53 diagram edits

No code changed in this stage. The code's values are the right ones in every case, so the diagram was corrected.

13 of the 75 items were checker false alarms. The checker can't work out a starting value that the code computes (for example a value passed through a checking helper, or a module constant such as `REPORT_WIDTH`). The scan now also builds each class with no arguments and reads its real starting values (`runtime_starts.py` in the check tools). A diagram value counts as correct when it matches that real value. Examples: `ResearchReport.__url = ""`, `RateLimiter.__cooldown_seconds = 60`, `ReportView.__width = 96`.

After the review, the checker also verifies abbreviated values: `X(...)` must name the class the code builds (directly or through a private helper returning it), and `".../folder"` must be the code's folder. Before, any value containing `...` was skipped.

| Class | Member | Correction | Reason |
|---|---|---|---|
| 15 classes: App, AssessmentRunner, AssetPath, Benchmark, CaseBuilder, ClientForm, ClientRecord, DocumentStore, Forecast, FuturePaths, MatchResult, OnboardingAssessor, PayCalibrator, ReportView, VerdictEngine | parts that `__init__` creates | `= None` → what is created, e.g. `= Config()`, `= ConsoleUI()`, `= ClientRepository(...)`, `= [CloudSync(...), CloudSync(...)]` | **T**: the part always exists once the object is built. `None` suggested it could be missing. `(...)` means it is built with arguments; `()` with none |
| ConfigReader, DocumentStore, ResponseCache | `__folder` | `".../config"`, `".../data/documents"`, `".../data/cache"` | **T**: the folder is made absolute from the project folder, so the app works from any start folder (as `JsonRepository.DATA_DIR`, stage 3) |
| JsonRepository, DatabaseRepository | `_key_field` | `""` | **T**: the base classes don't know their key; `ClientRepository` and `AssessmentRepository` pass `"client_ref"` / `"assessment_id"` |
| JsonRepository, DatabaseRepository, MongoRepository, ClientProfile, ClientRecord | `__init__` | parameter defaults shown (`= ""`) | **B**: every parameter has a default so an object can be built empty and filled from saved data (every attribute then has a default, CLAUDE.md §1) |
| ConsoleUI | `show`, `show_ai_unavailable` | `text : str = ""`, `feature : str = "Assessment"` | **B**: defaults below review level |
| ConsoleUI | `__read`, `__write` | `lambda question: input(...)`, `lambda text: print(...)` | **T**: `input`/`print` are looked up when called, so a swapped `builtins.input` (the console tests) still works (stage 3 batch B) |
| Claims | `__pep_status` | `""` (not `"no"`) | **T**: the code's default is `""`. Note: a blank status means "not answered" and is treated as a PEP; `""` was taken out of `Claims.NO_PEP_VALUES` (follow-up #41) |
| Verdict | `__outcome` | `"MANUAL_REVIEW"` (not `""`) | **T**: `""` is impossible (the outcome check rejects it). The safe default for an unfinished verdict is a person checking it |
| CrimeScan | `__indicators` | `[GiftOrInheritanceUnnamed(...), ...]` | **T**: CrimeScan builds its five indicators in `__init__` |
| WebApp | `__flask` | `Flask(...)` | **B**: `Flask(__name__)` was not wrong; the checker flagged it because the code builds it in a local variable first. `(...)` matches the convention above |

Layout: CrimeScan, Forecast, FuturePaths and DocumentStore were widened so the longer lines fit. The App→DocumentStore line ends beside the wider box, and the IO Manager folder was trimmed so it no longer overlaps the Application folder. `layout_check` reports 0.

## Stage 7: relationships (2026-11-15): 27 arrow edits and the main.py note

No code changed in this stage.

**Drawing rule (Marcus's decision).** An arrow is drawn when a class **stores** another class, **creates** one, or **works with one directly**: it is handed one as a parameter, calls its methods, or calls its static helpers. Two kinds of link are **not drawn**:
- objects reached only through another object's method (e.g. ReportView reads `record.jobs()`, so ReportView → Job is implied by `ClientRecord *-- Job`);
- reads of another class's constant (e.g. `CaseTimeline.FORECAST_YEARS`).

This keeps the reviewed diagram readable. The scan applies the same rule and lists the 32 links it finds and leaves out in `UML_DIFFERENCES.md` ("Not drawn, by the drawing rule"). A few more links are not in that list: the scan counts a line to the parent class as covering them (for example `CloudSync → JsonRepository`, covered by `CloudSync -- Repository`), or it cannot see them because the class name is never written in the code (for example `App → ReviewStatus`). Its known blind spots are follow-up #44.

| Arrow | Correction | Reason |
|---|---|---|
| `App *-- "1" CaseReader` | → `App ..> CaseReader : creates` | **T**: App makes a CaseReader per case (stage 4) |
| `App ..> ConfigReader : creates` | → `App *-- "1" ConfigReader` | **T**: App keeps it and asks it for `problems()` at start-up |
| `FuturePaths ..> MarketModel : uses` | → `FuturePaths -- MarketModel : projects with` | **T**: FuturePaths keeps the MarketModel it is handed (or makes a default one) |
| `App *-- "0..*" CloudSync` | → `"2"` | **T**: App always keeps exactly two, one for clients and one for assessments |
| `ClientRecord *-- "1" Claims` | → `"0..1"` | **T**: a new record has no declaration yet (`__claims : Claims \| None`) |
| `ConsoleUI ..> Band : uses` | removed | **T**: ConsoleUI formats a range from a dict and never touches Band (stage 3 batch B) |
| `RiskAnalysis ..> Formatter : uses` | removed; added `Benchmark ..> Formatter`, `Forecast ..> Formatter`, `VerdictEngine ..> Formatter` | **T**: RiskAnalysis itself never uses Formatter; these three do |
| `AssessmentRunner *-- "1" CaseReader`, `DocumentEvidence *-- "1" CaseReader` | added | **T**: each creates and keeps its own |
| `AssessmentRunner -- DocumentStore : reads documents from`, `AssessmentRunner -- ResponseCache : caches in` | added | **T**: it keeps the ones App hands in |
| `DocumentRecordBuilder -- Config : reads policy`, `ClientForm -- ReportView : shows via` | added | **T**: each keeps the one it is handed (as other classes keep `Config` and `ConsoleUI`) |
| `AssetPath`, `Benchmark`, `OnboardingAssessor`, `PayCalibrator ..> CaseTimeline : creates` | added | **T**: each builds a CaseTimeline in a method |
| `App ..> Declaration`, `Benchmark ..> Declaration`, `ReportView ..> Typology`, `VerdictEngine ..> Typology`, `WebApp ..> Typology` | added (`uses`) | **T**: each is handed these model objects and reads them (since the dict → model refactor) |
| `ForecastAI ..> ClaimedSource : checks` | added | **T**: its person-type check and repair take the declared sources |
| `VerdictEngine ..> Forecast : calls` | added | **T**: the engine calls `honest_numbers()`, which only Forecast has, through its feature list. This is a design smell (the engine should treat every RiskAnalysis alike); the arrow shows it honestly |
| `DocumentReaderFactory ..> DocumentReader : creates` | kept | The verb was right: the factory builds the reader from `READER_TYPES`. The checker missed it after stage 4 moved the table to a class constant; the checker is fixed |
| `Typology -- "1..*" ResearchReport : cites` | kept, without code evidence | A Typology keeps the *ids* of the reports it cites (`source_ids`), not the objects. The link is real in the data, so the reviewed diagram keeps it (listed in the scan as "kept by decision") |
| note on `App` | now quotes `main.py` exactly | **T**: `main.py` runs `sys.exit(App(with_fallback(openai_caller(), gemini_caller())).start(sys.argv[1:]))`; there is no `caller` variable and the callers take no arguments |

Not drawn under the rule, from the earlier list: `App → CaseTimeline`, `App → ReviewStatus`, `VerdictEngine → CrimeScan / Benchmark / FuturePaths` (constants), `PayCalibrator → MarketModel`, `OnboardingAssessor → Verdict`, `CaseBuilder → ClientForm`, `WebApp → ClientForm`, `CloudSync → JsonRepository`, `DocumentRecordBuilder → CaseReader` (constants), and links reached through another object such as `Forecast → AssetPath / CareerSavings`, `Indicator → ClaimedSource` and WebApp's repositories (follow-up #39). `App ..> Check : creates` no longer applies: App no longer builds Check objects.

### Stage 7 review fixes (independent review, 2026-11-15)

The review found no arrow that states something false about the code. It found these smaller problems, fixed in the diagram:

| Arrow | Change | Reason |
|---|---|---|
| `App *-- "1" ConfigReader` | multiplicity "1" added | **B**: the log already said "1" but the line had no label; every other `App *--` line shows "1" (`app.py:74`) |
| `AssessmentRunner o-- "0..1" DocumentStore : reads documents from` | was `--` with no multiplicity | **T**: the runner is given the store (it may be `None`) and never creates it, which is aggregation, as its `o-- "1..*" AIService` line already shows (`assessment_runner.py:63, 70`) |
| `AssessmentRunner o-- "0..1" ResponseCache : caches in` | was `--` with no multiplicity | **T**: same reason (`assessment_runner.py:63, 71`) |
| `CrimeScan ..> Declaration : creates` | verb was `reads` | **T**: CrimeScan builds Declarations (`crime_scan.py:308, 477, 516`) |
| `VerdictEngine ..> MatchResult : uses` | added | **T**: the engine reads `typology` and `category` and calls `fired()` on the match results (`verdict_engine.py:82, 102-103`). The scan cannot see this link (no type hint), so it is listed as checked by hand |
| Lines into `CaseReader`, `Forecast` and `Formatter` | re-routed | **B**: two "1" labels sat on the same spot over an arrowhead, and two arrows shared one end point on Forecast. The router now keeps arrow ends at least 25 px apart and avoids running along other lines more strongly |

### Follow-up #43 settled: Marcus chose option A (2026-11-15)

The drawing rule now reads: draw an arrow when a class stores, creates or directly works with another class, **including calling methods on an object it gets back from another call**. A class that only passes an object on, without calling anything on it, gets no arrow. All 25 links the scan had marked "reached through another object" were checked by hand against the code:

| Arrow | Change | Evidence |
|---|---|---|
| `AssessmentRunner ..> Typology : uses` | added | calls `typology.to_dict()` on the typologies CrimeScan returns (`assessment_runner.py:166`) |
| `Benchmark ..> ClaimedSource : uses` | added | reads `counterparty` and the linked indexes of each declared source (`benchmark.py:436-442`) |
| `CrimeScan ..> ClaimedSource : uses` | added | calls `source.to_scan_dict()` and reads `source.country` (`crime_scan.py:478-499`) |
| `Forecast ..> CareerSavings : uses` | added | calls `.rows()` on `future_paths.career_savings()` (`forecast.py:145, 270`) |
| `Forecast ..> AssetPath : uses` | added | calls `.build()` on `future_paths.asset_path()` (`forecast.py:146, 270`) |
| `OnboardingAssessor ..> AssetPath : uses` | added | calls `.income_up_to()` on `future_paths.asset_path()` (`onboarding_assessor.py:78`) |
| `OnboardingAssessor ..> ClaimedSource : uses` | added | reads `source.country` and `source.amount` (`onboarding_assessor.py:90, 106`) |
| `GiftOrInheritanceUnnamed`, `SourceContradictsOccupation`, `UnvaluedSource`, `RelatedPartyTransaction ..> ClaimedSource : checks` | 4 added | each `fires()` calls methods or reads fields on every declared source (`indicator.py:32, 57, 70, 88`) |
| `CaseBuilder ..> Job`, `CaseBuilder ..> Investment : uses` | 2 added | calls `.to_dict()` on `record.jobs()` / `record.investments()` (`case_builder.py:87, 133`) |
| `ReportView ..> Job`, `ReportView ..> Investment : uses` | 2 added | the same (`report_view.py:226, 235`) |
| `WebApp ..> DocumentRecordBuilder : uses` | added | calls `.build()` on `app.record_builder()` (`web_app.py:408, 523`) |
| `WebApp ..> DocumentStore : uses` | added | calls `.owns()` and `.read_for_extraction()` on `app.documents()` (`web_app.py:471, 491`) |
| `WebApp ..> Repository : loads from` | added | calls `.load()` on `app.clients()` and `app.assessments()` (`web_app.py:639, 891`); one line covers both repositories |
| `AssessmentRunner ..> Verdict : uses` | **removed** (was in the reviewed diagram) | **T** under the agreed rule: the runner gets the Verdict from `combine()` and only puts it into its result dict, without calling anything on it (`assessment_runner.py:229-242`) |

Not drawn after checking (listed with their reasons in `UML_DIFFERENCES.md`): `AssessmentRunner → Declaration / ResearchReport / Verdict` and `Forecast / FuturePaths → ClientRecord` only pass the object on. `ClientForm → DocumentStore` and `ReportView → DocumentStore` were false matches by the scan: `record.documents()` returns a list of document entries, not the DocumentStore.

Reason code for the 18 added arrows: **T** (the class really works with the other class). Several of these links only appeared after the dict → model refactor, so the original diagram was not wrong when it was reviewed; the code changed after the review.

Checker: `relcheck.py` now reads the hand-checked "only passed on" links from `not_drawn_checked.json`. Any new link of this kind that nobody has checked is reported as **missing**, so it gets looked at instead of being hidden.

Tools: the new arrows are routed automatically (`uml_arrows.py`: right-angled paths that never cross a class box), and `layout_check` reports 0.

## Clean-up pass and §9 fixes (2026-11-16): 4 diagram edits

The code changed first (follow-ups #32, #37, #38, #41, #42, approved by Marcus); the diagram follows it.

| Class | Change | Reason |
|---|---|---|
| `DatabaseRepository`, `MongoRepository` | `__init__(collection_name : str, key_field : str, uri : str = "")`: the `""` defaults are gone | **R**: an empty key field made `find` query `{"": ref}` (§9 validation). Both values are now required and an empty one is rejected with a clear message, so a `""` default would always fail |
| `WebApp` | `view_assessment(...) : str \| Response` | **T**: it now redirects home when the saved assessments cannot be read (§9) |
| `ReportView` | `show_ai_progress(results)` removed | **T**: nothing but its own test ever called it (dead code, follow-up #38) |

The renames to private (`CaseBuilder.__payment_method` and three more helpers, `ConsoleUI.__words_error`, `ForecastAI.__check_market_series` / `__check_position_pay`) and the removal of `WebApp.PAYMENT_OPTIONS` touch members that are not in the diagram yet, so they need no correction here; stage 5 adds the members as they now are.

## Stage 5: every code member added (2026-11-16): 450 additions, plus types, values and a new layout

Marcus chose to show **every** member, so the diagram shows the code exactly; the scan is now 0 in every stage.
Reason codes (counted from the `.puml` before and after):

| Added | Count | Reason |
|---|---|---|
| Public methods (`+name(...)`) | 135 | **T**: they are part of the classes' real public interface, which the reviewed diagram left out, so it was incomplete |
| Protected (`#`) and private (`-`) methods | 165 | **B**: helpers below the level the professor reviewed |
| Attributes (67 private, 1 protected), constants (75) and the computed property (1) | 144 | **B**: private state and fixed values |

The professor's reviewed members were not changed.

| Kind | Added |
|---|---|
| Methods | 300 |
| Attributes (with `{get}` / `{get, set}` when a property exposes them) | 68 |
| Constants (`«const»`) | 75 |
| Computed properties (`«property»`), and `{get}` added to an attribute already shown | 7 |

Per class (most first):

| Class | Methods | Attributes | Constants | Properties |
|---|---|---|---|---|
| `ForecastAI` | 48 | 3 | 5 | 0 |
| `App` | 30 | 3 | 7 | 1 |
| `WebApp` | 31 | 0 | 9 | 0 |
| `ClaimedSource` | 8 | 10 | 3 | 0 |
| `Typology` | 9 | 8 | 1 | 0 |
| `AssessmentRunner` | 2 | 14 | 1 | 0 |
| `ConsoleUI` | 15 | 1 | 1 | 0 |
| `CrimeScan` | 10 | 1 | 5 | 0 |
| `DocumentRecordBuilder` | 14 | 1 | 1 | 0 |
| `ClientForm` | 14 | 1 | 0 | 0 |
| `AIService` | 12 | 1 | 1 | 0 |
| `ClientRecord` | 5 | 2 | 4 | 2 |
| `ReportView` | 7 | 0 | 4 | 0 |
| `VerdictEngine` | 8 | 1 | 2 | 0 |
| `ResearchReport` | 6 | 5 | 0 | 0 |
| `Benchmark` | 6 | 0 | 4 | 0 |
| `FuturePaths` | 4 | 3 | 1 | 0 |
| `Band` | 8 | 0 | 0 | 0 |
| `Forecast` | 6 | 0 | 1 | 0 |
| `ResearchAI` | 5 | 0 | 2 | 0 |
| `Verdict` | 1 | 1 | 3 | 2 |
| `CaseReader` | 5 | 0 | 1 | 0 |
| `Check` | 3 | 2 | 1 | 0 |
| `DocumentAI` | 4 | 0 | 2 | 0 |
| `MatchResult` | 3 | 2 | 1 | 0 |
| `CaseBuilder` | 5 | 1 | 0 | 0 |
| `ResponseCache` | 4 | 0 | 1 | 0 |
| `TypologyAI` | 3 | 0 | 2 | 0 |
| `Claims` | 1 | 1 | 2 | 0 |
| `DocumentEvidence` | 2 | 1 | 1 | 0 |
| `ClientProfile` | 1 | 0 | 2 | 0 |
| `RateLimiter` | 1 | 1 | 1 | 0 |
| `DatabaseRepository` | 1 | 0 | 0 | 2 |
| `Declaration` | 3 | 0 | 0 | 0 |
| `OnboardingAssessor` | 3 | 0 | 0 | 0 |
| `ConfigReader` | 0 | 1 | 1 | 0 |
| `Job` | 0 | 1 | 1 | 0 |
| `MarketModel` | 0 | 0 | 2 | 0 |
| `MongoRepository` | 1 | 0 | 1 | 0 |
| `AssetPath` | 1 | 1 | 0 | 0 |
| `DocumentStore` | 1 | 1 | 0 | 0 |
| `Investment` | 1 | 1 | 0 | 0 |
| `BenchmarkAI` | 2 | 0 | 0 | 0 |
| `TextReader` | 0 | 0 | 1 | 0 |
| `AssessmentRepository` | 1 | 0 | 0 | 0 |
| `ClientRepository` | 1 | 0 | 0 | 0 |
| `Config` | 1 | 0 | 0 | 0 |
| `DocumentReader` | 1 | 0 | 0 | 0 |
| `Repository` | 1 | 0 | 0 | 0 |
| `RiskAnalysis` | 1 | 0 | 0 | 0 |

Also in this stage:
- **Code first:** 23 constants and 36 methods had no type hints (CLAUDE.md §1). They were typed in the code (annotations only, proved byte-identical by the harnesses) before they were drawn, so the diagram shows real types, not `object`.
- 10 constants already in the diagram now show the exact types the code declares (`dict` -> `dict[str, str]`, `list` -> `list[dict[str, str]]` ...). **B**.
- Starting values are written the diagram's short way: `X(...)`, `[...]`, `{...}`, `(...)`, `".../folder"`, or the text cut with `...`.
- **Layout:** the boxes grew a lot, so the diagram was re-packed (`relayout.py`): inside each folder boxes keep their place and order and are only pushed down far enough to clear the box above; folders grow to fit and move down so none overlap. Nine boxes were widened so no line is cut off. Every line was then re-routed (`uml_arrows.py` reroute_all): right-angled paths that never cross a box, arrow ends kept apart, inheritance lines into one parent sharing a trunk. `layout_check` reports 0.

### Stage 5 review fixes (independent Opus review, 2026-11-16)

The review found every added member and every line faithful to the code. Its fixes:
- Two starting values now match the code: `App.__config_reader = ConfigReader(...)` and DatabaseRepository's
  `#_collection_name : str` / `#_key_field : str {get}` (no `""` default since the §9 fix).
- In each box, fields come before constants again (122 lines moved, no text changed).
- Line labels: the verb labels (90) sit on a clear stretch of their own line, and 6 multiplicity labels moved off box borders (`place_labels.py`).
- The main.py note is drawn above the lines that pass under it, so its text is readable.
- The Indicator family is a single clean tree: each child joins one trunk on its left, which leads up to Indicator.
  The DocumentEvidence → CaseReader composition now goes straight down, so it no longer seems to merge with that trunk.
- `Repository` stays `«interface»` (Marcus, follow-up #53): it stores nothing and only lists `save`/`load`/`find`; its
  empty `__init__` is there only for CLAUDE.md §1. No diagram change.

## Group 1 validation fixes (2026-11-16): code changed, the diagram follows it

No reviewed member was corrected: the code changed (follow-ups #5, #21, #27, #29, #47, #48, #51, #55), and the
diagram was updated to show the new and changed members, so the scan stays at 0. Reason code for these diagram edits:
**T** for public signatures (they are the real interface), **B** for the new private helpers.
- Changed: `JsonRepository.__init__(path : str, key_field : str)` (no `""` defaults); `DocumentRecordBuilder.build`
  returns a third item, the dropped fields; `ClientForm.generate_client_id(is_taken_fn)` and `create_new_client(..., is_taken_fn)`;
  `ConsoleUI.keep_money(..., allow_zero)`, `ask_money(..., allow_blank)`, `ask_countries(..., allow_blank)`; `CaseReader.is_iso_date`
  is public and static (it was a private helper) because `DocumentRecordBuilder` uses it too.
- Added: `App.client_ref_taken`, `ClientForm.MAX_ID_TRIES`, `ClientForm.ask_optional_field`, `ConsoleUI.show_dropped_fields`,
  `ConsoleUI.show_optional_intro`, `WebApp.values_from_reading`, and private helpers in AssessmentRunner, DocumentRecordBuilder,
  MarketModel, ClaimedSource and Claims.
- New arrow: `DocumentRecordBuilder ..> CaseReader : uses` (it calls `CaseReader.is_iso_date`).
- Layout: ConsoleUI grew into ReportView, so `ClientForm` moved to the left IO column under `CaseBuilder`; the lines
  around it were re-routed. layout_check 0.

## Group 2 graded-rule fixes (2026-11-16): code changed, the diagram follows it

No reviewed member was corrected; the code changed (follow-ups #10, #23, #50, #52, #54, #56) and the diagram shows it.
- `VerdictEngine`: `#_feature`, `#_feature_checks`, `#_check` -> `-__feature`, `-__feature_checks`, `-__check` (no children; CLAUDE.md §1).
- `CrimeScan`: `#_prepare_case`, `#_safe_int` and `-__to_iso` removed (dead code: the old matching never read `_prepare_case`'s output; Marcus decided to delete it). **R/B**.
- `ClientForm.find_existing_client`: the unused `load_fn` parameter removed.
- Added `AssessmentRunner.RESEARCH_STEP` (the failed-research step's name) and `App.typologies_checked(report)` (static), so both front ends can mark typologies that were not checked against research.
- Layout: `AssessmentRunner` was widened to 480 and moved up beside `App` (it had grown into App's bottom edge); every App and AssessmentRunner line was re-routed. The long constant value is shortened with `...`. layout_check 0.
- Known limit (accepted): `App.typologies_checked` reads the report's "Could not run" section, so an assessment saved
  before #56 with failed research would show no badge. None exist: the database is being reset (Marcus, #4).

## #39 WebApp only talks to App (2026-11-16): code changed, the diagram follows it

No reviewed member was corrected; the code changed (follow-up #39, option A from Marcus) and the diagram shows it.
- Removed arrows: `WebApp ..> DocumentStore`, `WebApp ..> Repository`, `WebApp ..> DocumentRecordBuilder`. WebApp now
  asks App instead of taking App's objects and working them itself. Its arrows are App, RateLimiter, ClientRecord and Typology.
- Added to `App` (**T**, public interface): `owns_document(file_id)`, `read_document_for_extraction(path, name)`,
  `all_clients()`, `all_assessments()`, `record_from_reading(extracted, today)`, `reading_problems(record, today)`.
- Checker note: `WebApp -> DocumentStore` is listed as a false match in `not_drawn_checked.json`; the only
  `documents()` call left in WebApp is `ClientRecord.documents()`, the record's own list.
- Review fixes: App's comment and docstring corrected, and tests added (saved assessments are listed; autofill fills nothing
  and says why when the reading cannot be a record; WebApp never calls App's manager getters). Scan 0, layout_check 0.

## Small follow-ups (2026-11-16): code changed, the diagram follows it

No reviewed member was corrected; the code changed (follow-ups #7, #8, #16, #22, #33, #35, #40, #49; Marcus took the
fix/leave recommendation for each) and the diagram shows the new signatures.
- `ClientForm.pick_client(find_fn)` and `find_existing_client(find_fn, ...)`: `find_fn` is required (no `None` default). **T**.
- Added `ClientRecord.why_unreadable(error)` (static, **T**): the one safe reason shown when a saved or typed record cannot
  be read. App, ClientForm and WebApp all use it, so the technical text of a TypeError/AttributeError never reaches the screen.
- `VerdictEngine`: `#_is_pep` -> `-__is_pep` (no child; CLAUDE.md §1).
- Not a diagram change: `config/policy.json` no longer has `verdict.no_pep_values`; `Claims.NO_PEP_VALUES` is the one list.
  `ConfigReader` no longer applies a cooldown default; `RateLimiter.DEFAULT_COOLDOWN_SECONDS` is the one default.
- Layout: ClientRecord grew one line; 9 lines re-routed. layout_check 0.

## Separate OpenAI research model (2026-11-16): code changed, the diagram follows it

Marcus asked for a separate model for web searches, as Gemini already has (`GEMINI_SEARCH_MODEL`). `OPENAI_RESEARCH_MODEL`
was dropped in Part 1 (6dc338b, "one AI model for every call"); it is read again. The AI caller functions gained
`search_model` / `search_model_name()`. They are module functions, not drawn in the class diagram.
- Added `App.-__ai_search_model() : str` (**B**): the model ResearchAI is given. layout_check 0.

## Demo mode removed (2026-11-16): code changed, the diagram follows it

Marcus: the app runs in normal mode only (no cache yet means the live AI is asked; its answers are then cached).
`--demo` never worked: the recorded replies it loaded (`tests/golden/*/ai_responses.json`) were never committed, so it
quietly used the live AI. Removed `App.+use_recorded_replies() : int`. `run.sh` (never committed) deleted. layout_check 0.

## PR #20 review fixes (2026-11-16): code changed, the diagram follows it

- Added `WebApp.ASSESSMENT_FAILED` and `WebApp.ASSESSMENT_STOPPED` (**T**): the plain messages a failed web assessment shows;
  the real error goes to the log only (CLAUDE.md §9).
- Not a diagram change: `AssessmentRunner` reports a failed verdict as "the verdict could not be worked out"; the Flask
  secret key comes from `SECRET_KEY` in `.env`, or is random at each start (no hard-coded key).
- Layout: WebApp grew two lines, so RateLimiter, CaseBuilder and ClientForm moved down; every line was re-routed. layout_check 0.

## Assessment snapshot and archive/restore (2026-11-16): code changed, the diagram follows it

Adrian's PR #19, rebuilt on the new `main` so WebApp only talks to App. Nothing is deleted: archive and restore each add
one line to an assessment's `archive_log`, and the last line decides whether it is hidden.
- `AssessmentRepository` (**T**): added the states `ACTIVE` / `ARCHIVED` / `UNREADABLE`, the results `CHANGED` / `NOT_FOUND` /
  `NO_CHANGE` / `NOT_SAVED`, `MAX_REASON_LENGTH`, `-__ACTIONS`, `-__lock` (shared by `save()` and archive/restore, so
  neither overwrites the other's change), `archive()`, `restore()`, `archive_state()`, `is_archived()`, `-__visible()`,
  `-__record_action()`; `for_client()` and `query()` gained `include_archived`.
- `App` (**T**): added the `ARCHIVE_*` constants (the repository's values, so WebApp need not import app/data),
  `archive_assessment()`, `restore_assessment()`, `archive_state()`; `client_assessments()` and `all_assessments()` gained
  `include_archived`. Not a diagram change: `save_assessment` saves a copy of the case under `"case"`.
- `WebApp` (**T**): added `archive_assessment()`, `restore_assessment()`, `-__change_archive()`; `show_report()` gained
  `archive` and `archive_state`.
- `ReportView` (**T**): added `ARCHIVE_MARKS`; `format_assessment_list()` and `show_assessment_list()` gained `states`
  (`list[str] | None`, one state per record in the same order: old records may share a missing id, so a dict keyed by
  id would mark the wrong rows; Opus review).
- `AssessmentRepository` (**B**): added `-__good_entry()` (Opus review: an archive line whose time or reason is not text
  now counts as damaged, instead of breaking the assessment page).
- Optional archive reason (Marcus, PR #19 review point 5): `AssessmentRepository.+reason_problem()` (**T**, the plain
  reason a reason is refused); `App.archive_assessment()` gained `reason`, and App gained `ARCHIVE_BAD_REASON`,
  `MAX_ARCHIVE_REASON` and `archive_reason_problem()` (**T**), so a bad reason is reported as such, never as
  "can't load the saved assessments". The web page has an optional reason box next to Archive. layout_check 0.
- Layout: WebApp and AssessmentRepository grew, so RateLimiter, CaseBuilder, ClientForm, DocumentReaderFactory and
  CaseFiles moved down; every line was re-routed. layout_check 0.

## Audit trail, Phase 1 (2026-11-16): code changed, the diagram follows it

The boxes were drawn from the built code at the end of the phase, not first. Reason: the members settled while the
feature was being built, and the checker compares the diagram with the code. (The usual order, UML first, applies to
Phase 2.)

**6 classes added** (the checker's stage 1; their members came from the scan's stage 5):
- `Account` (app/model): one officer or admin sign-in (email, name, role), validated in its own setter.
- `AuditEvent` (app/model): one line of the audit log, sealed with a hash of the line before it.
- `AuditFilter` (app/model): the audit-log page's filters and paging, checked by itself (`problems()`).
- `AuditRepository` (app/data, child of `JsonRepository`): stores the audit lines; adds only `save()` and `for_client()`.
- `RecordDiff` (app/logic): the fields that changed between a client record before and after a save.
- `AuditChain` (app/logic): walks the saved lines and reports whether the hash chain is intact.

**Members changed on existing classes**
- `App`: new `__audit`, `__audit_note` and the `AUDIT_*` / `OUTCOME_NOT_UPDATED` / `MAX_REFUSED_TEXT` / `TERMINAL` /
  `UNEXPECTED_ERROR_STEP` constants; new methods `account()`, `accounts()`, `sign_in()`, `sign_out()`, `refused()`,
  `audit_log()`, `audit_trail()`, `verify_audit_log()`, `audit_write_failed()`, `client_outcome_failed()` and the private
  helpers. Eight methods gained an `actor` parameter (and `client_ref` / `new_client` where a record or document is
  involved): `save_client`, `upload_document`, `download_document`, `sync_to_cloud`, `assess`, `read_documents`,
  `save_assessment`, `archive_assessment`, `restore_assessment`.
- `WebApp`: new sign-in/sign-out, `gate()`, `audit_log_view()`, `audit_verify()`, `singapore_time()` and helpers, plus
  the audit constants; the upload, autofill, save and background methods gained `actor`, `client_ref` or `new_client`.
- `Config`: new `__accounts`, `accounts` property and `account()`; `__init__` takes `accounts`.
- `ConfigReader`: `FILE_NAMES` now includes `"accounts"`; new `-__account_problems()`.
- `AssessmentRepository`: `MAX_BY_LENGTH`, `-__checked_by()`; `archive()`, `restore()` and `-__record_action()` take `by`.
- After the review fixes: `AuditChain` gained `-__broken_ids` and `broken_ids()`; `WebApp` gained `shown_value()` and
  `-__show_audit_log()`, and `audit_verify()` now returns `str | Response`. The IO column was re-stacked (WebApp grew).

**Arrows added** (16; all confirmed by the checker): `AuditRepository --|> JsonRepository`; `App *-- "1" AuditRepository`;
`Config o-- "0..*" Account`; `AuditChain *-- "0..*" AuditEvent`; and `uses` arrows `App` to `Account`, `AuditChain`,
`AuditEvent`, `AuditFilter`, `RecordDiff`; `AuditFilter`, `AuditRepository` to `AuditEvent`; `ConfigReader` to `Account`;
`WebApp` to `Account`, `AuditChain`, `AuditEvent`, `AuditFilter`.
- The checker disagreed with two first drafts, and the diagram follows it: `AuditChain ..> AuditEvent` became a
  composition (the chain stores the events it builds from the rows), and `AuditRepository` to `JsonRepository` is
  inheritance, not a plain line. The checker also wants `WebApp` linked to `Account`, `AuditChain` and `AuditEvent`,
  not only `AuditFilter` (it gets them from `App`), so those three were added.
- Starting values that change on every run are written as the call (`datetime.now(...)`, `str(uuid.uuid4())`).

**Layout:** the new boxes sit in their manager's folder; `App` and `WebApp` grew, so the Logic and Domain Model areas
moved down 330 px, the IO column (WebApp, RateLimiter, CaseBuilder, ClientForm) was re-stacked, and every line was
re-routed. Scan 77 differences before, 0 after; round-trip PROBLEMS: 0; layout_check 0.

**Review fixes after the build (audit key, unreadable counts, `for_client` removed)**
- `App` gained `-__audit_key`, `AUDIT_KEY_MISSING`, `MIN_AUDIT_KEY` and `audit_key_ok()`; `AuditEvent.compute_hash()`,
  `hash_matches()` and `seal()` take a `key`; `AuditChain` and `AuditRepository` take and keep a `-__key`. Why: the hash
  chain is now signed with a secret `AUDIT_KEY` (HMAC), so someone who edits the file cannot re-hash the log without it.
- `App.audit_log()` now returns `tuple[list[AuditEvent], int, int]`, `audit_trail()` and `__audit_events()` return
  `tuple[list[AuditEvent], int]`. Why: rows that cannot be read are counted and reported, not silently hidden (CLAUDE.md
  section 9).
- `AuditRepository.for_client()` was removed (code commit `024ca6d`): `App` no longer used it, so the diagram drops it too.
- Layout: the Application folder grew 40 px and 8 arrows from `App` were re-routed. Scan 15 differences before, 0 after;
  round-trip PROBLEMS: 0; layout_check 0.

**Process note:** commit `ace48ab` changed `app/application/app.py` without changing `tests/test_application_app.py` in
the same commit (CLAUDE.md section 7). Later commits added the tests. The history was not rewritten.
