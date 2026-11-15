# UML v4 vs code: differences, staged

Checked code at commit `9ded4e4` against `uml/class_diagram_v4.puml`, which is converted from `uml/class_diagram_v4.drawio` and was independently verified as faithful. Every class, attribute, property, constant and method signature was compared by script, so nothing was sampled.

**How to use this file:** work through one stage at a time, and tick `[x]` when an item is fixed. Then re-export the draw.io file, regenerate the `.puml` and re-run the check.

## How this was checked

| Link | How | Result |
|---|---|---|
| draw.io → PlantUML | A round-trip script plus an independent agent with its own parser | **Faithful**: 69 classes, 224 attributes, 393 methods, 114 relationships, 35 multiplicities and the main.py note all identical |
| PlantUML → code: members | Script reads every class with Python's `ast` | Stages 1–6 below |
| PlantUML → code: relationships | Script (static analysis) **and** an independent agent reading the code by hand; every disagreement was settled by re-reading the code | Stage 7 below |

**What was compared:** class presence, kind, package and parent; attribute name, visibility, type and starting value; `{get}` / `{get, set}` properties; «const» name, type and value; method name, visibility, parameters (names, order, types, defaults), return type, «static», abstract; every relationship's kind, direction, verb and multiplicity; class-to-class links in the code that have no UML line; module-level functions (only `app/ai/ai_caller.py`: ✅); the main.py note.

**Not checked (can't be, statically):** method behaviour; 18 values the UML shortens with `...` (listed at the end).

**Area** is the feature area of the class, to help split the work. It is a best guess, so confirm it with the team. Don't change a teammate's files without asking them.

## Overview

| Stage | What | Items | Mostly fixed in |
|---|---|---|---|
| 1 | Structure: classes and inheritance | 0 | Code + UML |
| 2 | Graded code rules: types and `__init__` | 0 | Code |
| 3 | Same member, different details | 180 | Decide per item |
| 4 | In UML, missing in code | 38 | Decide per item |
| 5 | In code, missing from UML | 485 | UML |
| 6 | Minor: default and starting values | 90 | UML |
| 7 | Relationships (arrows, verbs, multiplicities) and the main.py note | 43 | Mostly UML |
| | **Total** | **836** | |

Pairs where only the underscores differ (`__x` in UML, `_x` in code) are merged into one item in stage 3, so the total is lower than the raw count of differences.

## Stage 1: Structure: classes and inheritance (0)

Fix first, because every later stage depends on the class names being right.

How to fix: **Code:** rename `Feature` to `RiskAnalysis` (file, class, imports, tests). **UML:** change `list[Feature]` to `list[RiskAnalysis]` in `AssessmentRunner` and `VerdictEngine`, and add `CaseFiles` and `CaseTimeline`, which exist in code.

**Done.** Nothing left in this stage.

## Stage 2: Graded code rules: types and `__init__` (0)

CLAUDE.md §1 says every attribute has a type and is created in `__init__`. These are code fixes; the UML is already right.

How to fix: **Code:** add the missing type hints, and create every attribute in `__init__` with a default.

**Done.** Nothing left in this stage.

## Stage 3: Same member, different details (180)

Both sides have it, but the signature, type, visibility, static or abstract marker, or constant value differs.

How to fix: Decide per item. If the code is the better design, update the UML. If the code breaks the design, fix the code.

### Benchmark (10)

**`Benchmark`**

- [ ] `__is_pep` (UML) is `is_pep` in code: visibility (underscores) differs. UML: `-__is_pep(case : dict) : bool` · code: app/logic/benchmark.py:223
- [ ] `__total_wealth` (UML) is `_total_wealth` in code: visibility (underscores) differs. UML: `-__total_wealth(client : dict, ai : dict) : dict` · code: app/logic/benchmark.py:73
- [ ] `__liquidity` (UML) is `_liquidity` in code: visibility (underscores) differs. UML: `-__liquidity(client : dict, ai : dict) : dict` · code: app/logic/benchmark.py:82
- [ ] `__composition` (UML) is `_composition` in code: visibility (underscores) differs. UML: `-__composition(client : dict, ai : dict) : dict` · code: app/logic/benchmark.py:91
- [ ] `__velocity` (UML) is `_velocity` in code: visibility (underscores) differs. UML: `-__velocity(client : dict, ai : dict) : dict` · code: app/logic/benchmark.py:101
- [ ] `__counterparties` (UML) is `_counterparties` in code: visibility (underscores) differs. UML: `-__counterparties(declared : dict, expected : dict) : dict` · code: app/logic/benchmark.py:110
- [ ] `__jurisdiction` (UML) is `_jurisdiction` in code: visibility (underscores) differs. UML: `-__jurisdiction(declared : dict, expected : dict) : dict` · code: app/logic/benchmark.py:133
- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/benchmark.py:51)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/benchmark.py:51)
- [ ] `__init__` parameter `config` type differs. UML: `Config` · code: `Config | None` (app/logic/benchmark.py:51)

### Crime Scan (22)

**`CounterpartyUnnamed`**

- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/indicator.py:40)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/indicator.py:40)

**`CrimeScan`**

- [ ] `__COUNTRY_TO_ISO` (UML) is `_COUNTRY_TO_ISO` in code: visibility (underscores) differs. UML: `-__COUNTRY_TO_ISO : dict = {...} «const»` · code: app/logic/crime_scan.py:17
- [ ] `__categorise_match` (UML) is `_categorise_match` in code: visibility (underscores) differs. UML: `-__categorise_match(core_fired : list[str], core : list[str], supporting_fired : list[str]) : str` · code: app/logic/crime_scan.py:316
- [ ] `__domain_is_trusted` (UML) is `_domain_is_trusted` in code: visibility (underscores) differs. UML: `-__domain_is_trusted(url : str) : bool` · code: app/logic/crime_scan.py:284
- [ ] `__to_iso` (UML) is `_to_iso` in code: visibility (underscores) differs. UML: `-__to_iso(value : str) : str` · code: app/logic/crime_scan.py:350
- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/crime_scan.py:102)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/crime_scan.py:102)

**`GiftOrInheritanceUnnamed`**

- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/indicator.py:27)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/indicator.py:27)

**`Indicator`**

- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/indicator.py:14)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/indicator.py:14)

**`MatchResult`**

- [ ] `__init__` parameters differ. UML: `+__init__(typology : Typology, core_fired : list[str])` · code: `(typology, core_fired, supporting_fired, category)` (app/model/match_result.py:16)

**`RelatedPartyTransaction`**

- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/indicator.py:84)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/indicator.py:84)

**`ResearchReport`**

- [ ] `__init__` parameters differ. UML: `+__init__(report_id : str, url : str, excerpts : list[str])` · code: `(report_id, url, excerpts, organisation, title, year, summary, retrieved_at)` (app/model/research_report.py:14)

**`SourceContradictsOccupation`**

- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/indicator.py:53)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/indicator.py:53)

**`Typology`**

- [ ] `__init__` parameters differ. UML: `+__init__(typology_id : str, name : str, indicators : list[dict])` · code: `(typology_id, name, indicators, source_ids, crime_category, description, source_quotes, typical_documents)` (app/model/typology.py:14)

**`UnvaluedSource`**

- [ ] constant `NAME` value differs. UML: `"unvalued_source"` · code: `'unvalued_source_present'` (app/logic/indicator.py:60)
- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/indicator.py:66)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/indicator.py:66)

### Data (6)

**`CloudSync`**

- [ ] `__local` type differs. UML: `Repository` · code: `Repository | None` (app/data/cloud_sync.py:24)
- [ ] `__remote` type differs. UML: `DatabaseRepository` · code: `DatabaseRepository | None` (app/data/cloud_sync.py:25)
- [ ] `__init__` parameter `local` type differs. UML: `Repository` · code: `Repository | None` (app/data/cloud_sync.py:22)
- [ ] `__init__` parameter `remote` type differs. UML: `DatabaseRepository` · code: `DatabaseRepository | None` (app/data/cloud_sync.py:22)

**`ConfigReader`**

- [ ] `__init__` parameter `folder` default differs. UML: `"config"` · code: `os.path.join(ROOT_DIR, 'config')` (app/data/config_reader.py:20)

**`JsonRepository`**

- [ ] constant `DATA_DIR` value differs. UML: `"data/local database"` · code: `os.path.join(ROOT_DIR, 'data', 'local database')` (app/data/json_repository.py:15)

### Document Evidence (11)

**`DocumentEvidence`**

- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/document_evidence.py:18)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/document_evidence.py:18)

**`DocumentReaderFactory`**

- [ ] `supported_types` return type differs. UML: `set[str]` · code: `list[str]` (app/data/document_reader_factory.py:31)

**`DocumentRecordBuilder`**

- [ ] `__age_from_birth` (UML) is `_age_from_birth` in code: visibility (underscores) differs. UML: `-__age_from_birth(date_of_birth : str) : int | None` · code: app/logic/document_record_builder.py:30
- [ ] `__init__` parameters differ. UML: `+__init__(client_ref : str, today : str, policy : dict)` · code: `(config, today)` (app/logic/document_record_builder.py:25)
- [ ] `build` parameters differ. UML: `+build(extracted : dict) : tuple[ClientRecord, list]` · code: `(extracted, client_ref)` (app/logic/document_record_builder.py:44)
- [ ] `build` return type differs. UML: `tuple[ClientRecord, list]` · code: `tuple[ClientRecord, list[str]]` (app/logic/document_record_builder.py:44)
- [ ] `missing_fields` return type differs. UML: `list[str]` · code: `list[dict]` (app/logic/document_record_builder.py:201)
- [ ] `summarise` parameters differ. UML: `+summarise(record : ClientRecord) : list[dict]` · code: `(client, doc_client)` (app/logic/document_record_builder.py:296)

**`DocumentStore`**

- [ ] `__init__` parameters differ. UML: `+__init__(folder : str = "data/documents")` · code: `(folder, root)` (app/data/document_store.py:22)
- [ ] `read_for_extraction` parameters differ. UML: `+read_for_extraction(file_path : str) : dict` · code: `(file_path, file_name)` (app/data/document_store.py:84)

### Forecast (40)

**`AssetPath`**

- [ ] `__init__` parameters differ. UML: `+__init__(market_model : MarketModel)` · code: `(market_model, asset_models)` (app/logic/asset_path.py:16)
- [ ] `build` parameters differ. UML: `+build(record : dict, last_year : int) : list[dict]` · code: `(record, last_year, scenario, shocks)` (app/logic/asset_path.py:21)
- [ ] `income_up_to` parameters differ. UML: `+income_up_to(year : int) : dict` · code: `(path, year)` (app/logic/asset_path.py:30)

**`CareerSavings`**

- [ ] `__init__` parameter `pay` type differs. UML: `dict` · code: `dict | None` (app/logic/career_savings.py:18)
- [ ] `__init__` parameter `pay` default differs. UML: `{}` · code: `None` (app/logic/career_savings.py:18)
- [ ] `pay_total` parameters differ. UML: `+pay_total(level : str) : float` · code: `(pay, level)` (app/logic/career_savings.py:55)

**`Forecast`**

- [ ] `__honest_numbers` (UML) is `_honest_numbers` in code: visibility (underscores) differs. UML: `-__honest_numbers(case : dict) : dict` · code: app/logic/forecast.py:264
- [ ] `__rank_documents` (UML) is `_rank_documents` in code: visibility (underscores) differs. UML: `-__rank_documents(candidates : list[str]) : list[str]` · code: app/logic/forecast.py:85
- [ ] `__data_quality` (UML) is `_data_quality` in code: visibility (underscores) differs. UML: `-__data_quality() : dict` · code: app/logic/forecast.py:126
- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/forecast.py:27)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/forecast.py:27)
- [ ] `__init__` parameter `config` type differs. UML: `Config` · code: `Config | None` (app/logic/forecast.py:27)
- [ ] `economy_brief` parameters differ. UML: `+economy_brief() : dict` · code: `(markets)` (app/logic/forecast.py:250)
- [ ] `economy_brief` return type differs. UML: `dict` · code: `dict | None` (app/logic/forecast.py:250)
- [ ] `document_request` parameters differ. UML: `+document_request(failures : list[Check]) : dict` · code: `(failures, candidates)` (app/logic/forecast.py:99)
- [ ] `document_request` return type differs. UML: `dict` · code: `list[dict]` (app/logic/forecast.py:99)

**`FuturePaths`**

- [ ] `__init__` parameters differ. UML: `+__init__(market_model : MarketModel)` · code: `(market_model, forecast, policy)` (app/logic/future_paths.py:20)
- [ ] `expected_paths` parameters differ. UML: `+expected_paths(record : dict) : dict` · code: `(record, savings_rows)` (app/logic/future_paths.py:100)
- [ ] `event_impacts` parameters differ. UML: `+event_impacts(record : dict) : list` · code: `(record, savings_rows)` (app/logic/future_paths.py:114)
- [ ] `event_impacts` return type differs. UML: `list` · code: `list[dict]` (app/logic/future_paths.py:114)
- [ ] `divergence_years` parameters differ. UML: `+divergence_years() : dict` · code: `(paths)` (app/logic/future_paths.py:136)
- [ ] `divergence_years` return type differs. UML: `dict` · code: `list[dict]` (app/logic/future_paths.py:136)
- [ ] `honest_wealth` parameters differ. UML: `+honest_wealth(record : dict, year : int) : dict` · code: `(record, savings_rows, paths, year)` (app/logic/future_paths.py:44)

**`MarketModel`**

- [ ] `__init__` parameter `forecast` type differs. UML: `dict` · code: `dict | None` (app/logic/market_model.py:15)
- [ ] `__init__` parameter `forecast` default differs. UML: `{}` · code: `None` (app/logic/market_model.py:15)
- [ ] `change` parameters differ. UML: `+change(market_id : str, year : int, scenario : str) : float` · code: `(market_id, year, scenario, level, shocks)` (app/logic/market_model.py:40)

**`OnboardingAssessor`**

- [ ] `__check_asset_values` (UML) is `_check_asset_values` in code: visibility (underscores) differs. UML: `-__check_asset_values(record : dict) : list` · code: app/logic/onboarding_assessor.py:26
- [ ] `__check_affordability` (UML) is `_check_affordability` in code: visibility (underscores) differs. UML: `-__check_affordability(record : dict) : list` · code: app/logic/onboarding_assessor.py:61
- [ ] `__check_jurisdictions` (UML) is `_check_jurisdictions` in code: visibility (underscores) differs. UML: `-__check_jurisdictions(record : dict) : list` · code: app/logic/onboarding_assessor.py:86
- [ ] `__decide_onboarding` (UML) is `_decide_onboarding` in code: visibility (underscores) differs. UML: `-__decide_onboarding(fits : dict) : str` · code: app/logic/onboarding_assessor.py:142
- [ ] `__init__` parameter `future_paths` type differs. UML: `FuturePaths` · code: `FuturePaths | None` (app/logic/onboarding_assessor.py:20)
- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/onboarding_assessor.py:20)
- [ ] `__init__` parameter `config` type differs. UML: `Config` · code: `Config | None` (app/logic/onboarding_assessor.py:20)
- [ ] `evaluate` parameters differ. UML: `+evaluate(record : dict, forecast : dict) : dict` · code: `(record, forecast, savings_rows, paths, scale)` (app/logic/onboarding_assessor.py:164)
- [ ] `stable_outcome` parameters differ. UML: `+stable_outcome(outcome : str, shifted : list) : str` · code: `(outcome, outcomes_when_shifted)` (app/logic/onboarding_assessor.py:156)
- [ ] `stable_outcome` return type differs. UML: `str` · code: `tuple[str, bool]` (app/logic/onboarding_assessor.py:156)

**`PayCalibrator`**

- [ ] `__init__` parameter `career_savings` type differs. UML: `CareerSavings` · code: `CareerSavings | None` (app/logic/pay_calibrator.py:17)
- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/pay_calibrator.py:17)
- [ ] `calibrate` parameters differ. UML: `+calibrate(case : dict, documented_pay : dict) : list` · code: `(case, forecast, documented_pay)` (app/logic/pay_calibrator.py:21)
- [ ] `calibrate` return type differs. UML: `list` · code: `tuple[dict, list[dict]]` (app/logic/pay_calibrator.py:21)

### Shared core (91)

**`App`**

- [ ] `__new_client_from_documents` (UML) is `new_client_from_documents` in code: visibility (underscores) differs. UML: `-__new_client_from_documents() : ClientRecord | None` · code: app/application/app.py:400
- [ ] `__prepare_case` (UML) is `prepare_case` in code: visibility (underscores) differs. UML: `-__prepare_case(record : ClientRecord) : dict | None` · code: app/application/app.py:238
- [ ] `__ai_caller` type differs. UML: `Callable` · code: `Callable | None` (app/application/app.py:93)
- [ ] `__clients` type differs. UML: `Repository` · code: `ClientRepository` (app/application/app.py:78)
- [ ] `__assessments` type differs. UML: `Repository` · code: `AssessmentRepository` (app/application/app.py:79)
- [ ] constant `CRITICAL_STEPS` type differs. UML: `list[str]` · code: `tuple[str, ...]` (app/application/app.py:43)
- [ ] `__init__` parameters differ. UML: `+__init__(ai_caller : Callable)` · code: `(ai_caller, root, data_folder)` (app/application/app.py:65)
- [ ] `list_assessments` return type differs. UML: `list[dict]` · code: `None` (app/application/app.py:499)
- [ ] `today` static in one, not the other. UML: `static` · code: `instance` (app/application/app.py:119)
- [ ] `__handle_failure` parameters differ. UML: `-__handle_failure(step : str, error : str) : bool` · code: `(step, reason)` (app/application/app.py:583)

**`AssessmentRunner`**

- [ ] constant `STEPS` type differs. UML: `list[str]` · code: `tuple[str, ...]` (app/application/assessment_runner.py:27)
- [ ] `__init__` parameters differ. UML: `+__init__(ai : dict[str, AIService], config : Config)` · code: `(config, research_ai, typology_ai, benchmark_ai, document_ai, forecast_ai, document_store, response_cache)` (app/application/assessment_runner.py:61)
- [ ] `run` parameters differ. UML: `+run(case : dict, files : list[dict], on_step : Callable = None, on_failure : Callable = None) : Verdict` · code: `(case, supporting_documents, on_step, on_failure)` (app/application/assessment_runner.py:90)
- [ ] `run` return type differs. UML: `Verdict` · code: `dict | None` (app/application/assessment_runner.py:90)

**`CaseBuilder`**

- [ ] `__jobs_from_record` (UML) is `_jobs_from_record` in code: visibility (underscores) differs. UML: `-__jobs_from_record(record : ClientRecord) : list[dict]` · code: app/interface/case_builder.py:83
- [ ] `__assets_from_record` (UML) is `_assets_from_record` in code: visibility (underscores) differs. UML: `-__assets_from_record(record : ClientRecord) : list[dict]` · code: app/interface/case_builder.py:130
- [ ] `__number_or_ask` (UML) is `_number_or_ask` in code: visibility (underscores) differs. UML: `-__number_or_ask(value : float | None, question : str) : float` · code: app/interface/case_builder.py:64
- [ ] `__year_or_ask` (UML) is `_year_or_ask` in code: visibility (underscores) differs. UML: `-__year_or_ask(value : int | None, question : str) : int` · code: app/interface/case_builder.py:72
- [ ] `__init__` parameters differ. UML: `+__init__(ui : ConsoleUI, today : str = "")` · code: `(ui, case_schema)` (app/interface/case_builder.py:18)

**`CaseReader`**

- [ ] `__PRESENT_WORDS` (UML) is `_PRESENT_WORDS` in code: visibility (underscores) differs. UML: `-__PRESENT_WORDS : tuple = (...) «const»` · code: app/logic/case_reader.py:4
- [ ] `forecasting_case` return type differs. UML: `tuple[dict, list]` · code: `tuple[dict | None, list[str]]` (app/logic/case_reader.py:53)
- [ ] `read_year` static in one, not the other. UML: `static` · code: `instance` (app/logic/case_reader.py:38)

**`Check`**

- [ ] `__init__` parameters differ. UML: `+__init__(feature : str, check : str, label : str, theme : str, status : str = "passed", detail : str = "", explanation : str = "", group : str = "", sources : …` · code: `(feature, check, label, theme, status, detail, explanation, group, sources, supports, extra)` (app/model/check.py:16)

**`ClaimedSource`**

- [ ] `__init__` parameters differ. UML: `+__init__(source_type : str, counterparty : str | None, amount : float | None, occupation_mismatch : bool)` · code: `(source_type, counterparty, amount, occupation_mismatch, amount_explained, source_id, description, start_year, end_year, country, quote, linked_position_index, …` (app/model/claimed_source.py:21)

**`Claims`**

- [ ] `__init__` parameters differ. UML: `+__init__(declared_net_worth : float | None, expected_aum : float | None, pep_status : str, asset_composition : dict, wealth_countries : list[str], declared_cou…` · code: `(declared_net_worth, expected_aum, pep_status, asset_composition, wealth_countries, declared_counterparties, biggest_wealth_jump, wealth_jump_years, extra)` (app/model/claims.py:11)

**`ClientForm`**

- [ ] `__ask_job` (UML) is `_ask_job` in code: visibility (underscores) differs. UML: `-__ask_job() : dict` · code: app/interface/client_form.py:68
- [ ] `__ask_asset` (UML) is `_ask_asset` in code: visibility (underscores) differs. UML: `-__ask_asset() : dict` · code: app/interface/client_form.py:96
- [ ] `__get_claims` (UML) is `get_claims` in code: visibility (underscores) differs. UML: `-__get_claims() : dict` · code: app/interface/client_form.py:128
- [ ] `__edit_career_record` (UML) is `edit_career_record` in code: visibility (underscores) differs. UML: `-__edit_career_record(record : ClientRecord) : None` · code: app/interface/client_form.py:384
- [ ] `__edit_asset_record` (UML) is `edit_asset_record` in code: visibility (underscores) differs. UML: `-__edit_asset_record(record : ClientRecord) : None` · code: app/interface/client_form.py:427
- [ ] `__edit_sow_declaration` (UML) is `edit_sow_declaration` in code: visibility (underscores) differs. UML: `-__edit_sow_declaration(record : ClientRecord) : None` · code: app/interface/client_form.py:512
- [ ] `__init__` parameters differ. UML: `+__init__(ui : ConsoleUI)` · code: `(ui, report_view)` (app/interface/client_form.py:36)
- [ ] `create_new_client` parameters differ. UML: `+create_new_client() : ClientRecord | None` · code: `(save_fn, upload_fn)` (app/interface/client_form.py:224)
- [ ] `edit_existing_client` parameters differ. UML: `+edit_existing_client(record : ClientRecord) : ClientRecord` · code: `(client, upload_fn)` (app/interface/client_form.py:538)

**`ClientRecord`**

- [ ] `__claims` type differs. UML: `Claims` · code: `Claims | None` (app/model/client_record.py:36)

**`Config`**

- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/model/config.py:11)
- [ ] `__init__` parameter `vocabulary` type differs. UML: `dict` · code: `dict | None` (app/model/config.py:11)

**`ConsoleUI`**

- [ ] `__only` (UML) is `_only` in code: visibility (underscores) differs. UML: `-__only(text : str, allowed : str) : bool` · code: app/interface/console_ui.py:307
- [ ] `__parse_count` (UML) is `_parse_count` in code: visibility (underscores) differs. UML: `-__parse_count(text : str) : int | None` · code: app/interface/console_ui.py:339
- [ ] `__read` type differs. UML: `Callable` · code: `Callable[[str], str]` (app/interface/console_ui.py:36)
- [ ] `__write` type differs. UML: `Callable` · code: `Callable[[str], None]` (app/interface/console_ui.py:37)
- [ ] `__init__` parameter `read` type differs. UML: `Callable` · code: `Callable[[str], str] | None` (app/interface/console_ui.py:27)
- [ ] `__init__` parameter `read` default differs. UML: `input` · code: `None` (app/interface/console_ui.py:27)
- [ ] `__init__` parameter `write` type differs. UML: `Callable` · code: `Callable[[str], None] | None` (app/interface/console_ui.py:27)
- [ ] `__init__` parameter `write` default differs. UML: `print` · code: `None` (app/interface/console_ui.py:27)
- [ ] `ask_int` parameters differ. UML: `+ask_int(question : str, minimum : int = 0) : int` · code: `(question, minimum, maximum, allow_blank)` (app/interface/console_ui.py:179)
- [ ] `ask_int` return type differs. UML: `int` · code: `int | None` (app/interface/console_ui.py:179)
- [ ] `ask_money` parameter `allow_zero` default differs. UML: `False` · code: `True` (app/interface/console_ui.py:197)
- [ ] `ask_year` parameters differ. UML: `+ask_year(question : str, minimum : int, maximum : int) : int` · code: `(question, minimum, maximum, allow_blank)` (app/interface/console_ui.py:229)
- [ ] `ask_year` return type differs. UML: `int` · code: `int | None` (app/interface/console_ui.py:229)
- [ ] `ask_choice` parameters differ. UML: `+ask_choice(question : str, options : list) : int | None` · code: `(question, options, allow_back)` (app/interface/console_ui.py:210)
- [ ] `keep_text` parameters differ. UML: `+keep_text(label : str, current : str) : str` · code: `(label, current, min_length)` (app/interface/console_ui.py:270)
- [ ] `keep_money` parameter `current` type differs. UML: `float` · code: `float | str` (app/interface/console_ui.py:293)
- [ ] `keep_money` return type differs. UML: `float` · code: `float | str` (app/interface/console_ui.py:293)
- [ ] `money` parameter `value` type differs. UML: `float` · code: `float | None` (app/interface/console_ui.py:162)
- [ ] `money_range` parameters differ. UML: `+money_range(band : Band) : str` · code: `(values)` (app/interface/console_ui.py:165)

**`Declaration`**

- [ ] `__init__` parameter `sources` type differs. UML: `list[dict]` · code: `list[dict] | None` (app/model/declaration.py:14)
- [ ] `__init__` parameter `sources` default differs. UML: `[]` · code: `None` (app/model/declaration.py:14)

**`Investment`**

- [ ] `__year_acquired` type differs. UML: `int` · code: `int | None` (app/model/investment.py:17)
- [ ] `__current_declared_value` type differs. UML: `float` · code: `float | None` (app/model/investment.py:19)
- [ ] `__income_produced` type differs. UML: `float` · code: `float | None` (app/model/investment.py:20)
- [ ] `__init__` parameters differ. UML: `+__init__(asset_type : str, country : str, year_acquired : int, price_paid : float | None, current_declared_value : float, payment_method : str | None, income_p…` · code: `(asset_type, country, year_acquired, price_paid, current_declared_value, payment_method, income_produced, extra)` (app/model/investment.py:7)

**`Job`**

- [ ] `__start_year` type differs. UML: `int` · code: `int | None` (app/model/job.py:14)
- [ ] `__init__` parameters differ. UML: `+__init__(start_year : int, end_year : int | None, occupation : str, seniority : str, industry : str, employer_name : str, employer_size : str, country : str)` · code: `(start_year, end_year, occupation, seniority, industry, employer_name, employer_size, country, extra)` (app/model/job.py:10)
- [ ] `__check_years` parameter `start_year` type differs. UML: `int` · code: `int | None` (app/model/job.py:89)

**`RateLimiter`**

- [ ] `__init__` parameters differ. UML: `+__init__(cooldown_seconds : int = 60)` · code: `(policy)` (app/interface/rate_limiter.py:15)

**`ReportView`**

- [ ] `__format_crime_section` (UML) is `_format_crime_section` in code: visibility (underscores) differs. UML: `-__format_crime_section(crime : dict) : list[str]` · code: app/interface/report_view.py:48
- [ ] `__init__` parameters differ. UML: `+__init__(ui : ConsoleUI, width : int = 96)` · code: `(ui)` (app/interface/report_view.py:45)
- [ ] `show_verdict_report` parameters differ. UML: `+show_verdict_report(verdict : Verdict) : None` · code: `(verdict, ask_for_evidence, crime_result, typologies)` (app/interface/report_view.py:142)

**`RiskAnalysis`**

- [ ] `__init__` parameter `policy` type differs. UML: `dict` · code: `dict | None` (app/logic/risk_analysis.py:20)
- [ ] `__init__` parameter `policy` default differs. UML: `{}` · code: `None` (app/logic/risk_analysis.py:20)
- [ ] `_check` parameter `sources` type differs. UML: `list[str]` · code: `list[str] | None` (app/logic/risk_analysis.py:32)
- [ ] `_check` parameter `sources` default differs. UML: `[]` · code: `None` (app/logic/risk_analysis.py:32)
- [ ] `_check` parameter `supports` type differs. UML: `list[str]` · code: `list[str] | None` (app/logic/risk_analysis.py:32)
- [ ] `_check` parameter `supports` default differs. UML: `[]` · code: `None` (app/logic/risk_analysis.py:32)
- [ ] `_jump_years` return type differs. UML: `list[int]` · code: `tuple[float | None, int | None]` (app/logic/risk_analysis.py:39)

**`Verdict`**

- [ ] `__init__` parameter `notes` type differs. UML: `list[str]` · code: `list[str] | None` (app/model/verdict.py:28)
- [ ] `__init__` parameter `notes` default differs. UML: `[]` · code: `None` (app/model/verdict.py:28)
- [ ] `__init__` parameter `not_run` type differs. UML: `list[str]` · code: `list[str] | None` (app/model/verdict.py:28)
- [ ] `__init__` parameter `not_run` default differs. UML: `[]` · code: `None` (app/model/verdict.py:28)

**`VerdictEngine`**

- [ ] `__agreement` (UML) is `_agreement` in code: visibility (underscores) differs. UML: `-__agreement(checks : list[Check]) : dict` · code: app/logic/verdict_engine.py:133
- [ ] `__type_patterns` (UML) is `_type_patterns` in code: visibility (underscores) differs. UML: `-__type_patterns(results : dict) : list` · code: app/logic/verdict_engine.py:76
- [ ] `__evidence` (UML) is `_evidence` in code: visibility (underscores) differs. UML: `-__evidence(case : dict, results : dict) : dict` · code: app/logic/verdict_engine.py:401
- [ ] `__init__` parameter `features` type differs. UML: `list[RiskAnalysis]` · code: `list[RiskAnalysis] | None` (app/logic/verdict_engine.py:49)
- [ ] `__init__` parameter `config` type differs. UML: `Config` · code: `Config | None` (app/logic/verdict_engine.py:49)
- [ ] `describe_piece` parameter `piece` type differs. UML: `str` · code: `str | None` (app/logic/verdict_engine.py:110)

**`WebApp`**

- [ ] `__app` type differs. UML: `App` · code: `App | None` (app/interface/web_app.py:94)
- [ ] `__jobs` type differs. UML: `dict[str, Thread]` · code: `dict[str, dict]` (app/interface/web_app.py:95)
- [ ] `__init__` parameters differ. UML: `+__init__(app : App, limiter : RateLimiter)` · code: `(app)` (app/interface/web_app.py:93)
- [ ] `view_client` return type differs. UML: `str` · code: `str | Response` (app/interface/web_app.py:675)
- [ ] `edit_client_autofill` return type differs. UML: `str` · code: `str | Response` (app/interface/web_app.py:729)

## Stage 4: In UML, missing in code (38)

The diagram promises something the code doesn't have.

How to fix: Either the work was done under another name (then update the UML), or it was dropped (then remove it from the UML or build it).

### Data (1)

**`ConfigReader`**

- [ ] constant `FILE_NAMES` missing in code. UML: `+FILE_NAMES : tuple[str, ...] = ("policy", "vocabulary") «const»` · code: `—` (app/data/config_reader.py:12)

### Document Evidence (2)

**`DocumentReaderFactory`**

- [ ] constant `READER_TYPES` missing in code. UML: `+READER_TYPES : dict[str, type] = {".pdf": PdfReader, ...} «const»` · code: `—` (app/data/document_reader_factory.py:9)

**`DocumentRecordBuilder`**

- [ ] `__client_ref` missing in code (__init__). UML: `-__client_ref : str = ""` · code: `—` (app/logic/document_record_builder.py:11)

### Forecast (3)

**`ForecastAI`**

- [ ] `__check_markets()` missing in code. UML: `-__check_markets(data : dict) : list[str]` · code: `—` (app/ai/forecast_ai.py:19)
- [ ] `__check_pay()` missing in code. UML: `-__check_pay(data : dict) : list[str]` · code: `—` (app/ai/forecast_ai.py:19)
- [ ] `__repair()` missing in code. UML: `-__repair(data : dict, errors : list[str]) : dict` · code: `—` (app/ai/forecast_ai.py:19)

### Shared core (32)

**`App`**

- [ ] `__case_reader` missing in code (__init__). UML: `-__case_reader : CaseReader = None` · code: `—` (app/application/app.py:43)
- [ ] `__limiter` missing in code (__init__). UML: `-__limiter : RateLimiter = None` · code: `—` (app/application/app.py:43)
- [ ] `__syncs` missing in code (__init__). UML: `-__syncs : list[CloudSync] = []` · code: `—` (app/application/app.py:43)
- [ ] `client_assessments()` missing in code. UML: `+client_assessments(client_ref : str) : list[dict]` · code: `—` (app/application/app.py:43)
- [ ] `find_assessment()` missing in code. UML: `+find_assessment(assessment_id : str) : dict | None` · code: `—` (app/application/app.py:43)
- [ ] `upload_document()` missing in code. UML: `+upload_document(record : ClientRecord, file_path : str) : dict | None` · code: `—` (app/application/app.py:43)
- [ ] `download_document()` missing in code. UML: `+download_document(file_id : str, output_path : str) : bool` · code: `—` (app/application/app.py:43)
- [ ] `autofill_from_documents()` missing in code. UML: `+autofill_from_documents(paths : list[str]) : tuple[ClientRecord, list[str]]` · code: `—` (app/application/app.py:43)
- [ ] `__maybe_assess()` missing in code. UML: `-__maybe_assess(record : ClientRecord) : None` · code: `—` (app/application/app.py:43)

**`AssessmentRunner`**

- [ ] `__ai` missing in code (__init__). UML: `-__ai : dict[str, AIService] = {}` · code: `—` (app/application/assessment_runner.py:27)
- [ ] `__features` missing in code (__init__). UML: `-__features : list[RiskAnalysis] = []` · code: `—` (app/application/assessment_runner.py:27)
- [ ] `__verdict_engine` missing in code (__init__). UML: `-__verdict_engine : VerdictEngine = None` · code: `—` (app/application/assessment_runner.py:27)
- [ ] `__run_ai_steps()` missing in code. UML: `-__run_ai_steps(case : dict) : dict` · code: `—` (app/application/assessment_runner.py:27)

**`CaseBuilder`**

- [ ] `__today` missing in code (__init__). UML: `-__today : str = ""` · code: `—` (app/interface/case_builder.py:12)
- [ ] `build()` missing in code. UML: `+build(record : ClientRecord, missing : list[str]) : dict | None` · code: `—` (app/interface/case_builder.py:12)
- [ ] `show_case_problems()` missing in code. UML: `+show_case_problems(where : str, problems : list) : None` · code: `—` (app/interface/case_builder.py:12)

**`ClientForm`**

- [ ] constant `SOURCE_TAGS` missing in code. UML: `+SOURCE_TAGS : dict = {...} «const»` · code: `—` (app/interface/client_form.py:21)
- [ ] `pick_client()` missing in code. UML: `+pick_client(records : list[dict]) : ClientRecord | None` · code: `—` (app/interface/client_form.py:21)
- [ ] `ask_document_folder()` missing in code. UML: `+ask_document_folder() : str | None` · code: `—` (app/interface/client_form.py:21)

**`ConsoleUI`**

- [ ] constant `PAYMENT_METHODS` missing in code. UML: `+PAYMENT_METHODS : list[str] = [...] «const»` · code: `—` (app/interface/console_ui.py:13)
- [ ] constant `PEP_OPTIONS` missing in code. UML: `+PEP_OPTIONS : list[str] = [...] «const»` · code: `—` (app/interface/console_ui.py:13)

**`RateLimiter`**

- [ ] `__last_run` missing in code (__init__). UML: `-__last_run : dict[str, float] = {}` · code: `—` (app/interface/rate_limiter.py:6)

**`ReportView`**

- [ ] `__width` missing in code (__init__). UML: `-__width : int = 96` · code: `—` (app/interface/report_view.py:12)
- [ ] `show_client_list()` missing in code. UML: `+show_client_list(records : list[dict]) : None` · code: `—` (app/interface/report_view.py:12)
- [ ] `show_ai_progress()` missing in code. UML: `+show_ai_progress(results : dict) : None` · code: `—` (app/interface/report_view.py:12)
- [ ] `__display_section()` missing in code. UML: `-__display_section(title : str) : None` · code: `—` (app/interface/report_view.py:12)

**`VerdictEngine`**

- [ ] constant `MATCH_LABELS` missing in code. UML: `+MATCH_LABELS : dict = {...} «const»` · code: `—` (app/logic/verdict_engine.py:15)
- [ ] `__build_context()` missing in code. UML: `-__build_context(case : dict, results : dict) : dict` · code: `—` (app/logic/verdict_engine.py:15)
- [ ] `__collect_checks()` missing in code. UML: `-__collect_checks(context : dict) : list[Check]` · code: `—` (app/logic/verdict_engine.py:15)

**`WebApp`**

- [ ] `__limiter` missing in code (__init__). UML: `-__limiter : RateLimiter = None` · code: `—` (app/interface/web_app.py:27)
- [ ] `start()` missing in code. UML: `+start(host : str = "0.0.0.0", port : int = 5000) : None` · code: `—` (app/interface/web_app.py:27)
- [ ] `__run_in_background()` missing in code. UML: `-__run_in_background(job_id : str, record : ClientRecord) : None` · code: `—` (app/interface/web_app.py:27)

## Stage 5: In code, missing from UML (485)

The code grew past the diagram, mostly helper methods and constants.

How to fix: **UML:** add them to the draw.io boxes. If a class gets too big (professor: more than ~10 attributes is a worry), think about splitting it before adding everything.

### Benchmark (12)

**`Benchmark`**

- [ ] class-level `FORECAST_DERIVED` exists in code but not in UML. UML: `—` · code: `('UNEXPLAINED_GAP', 'PEP_STATUS', 'PEER_BENCHMARK')` (app/logic/benchmark.py:14)
- [ ] class-level `LIMITS` exists in code but not in UML. UML: `—` · code: `{'total_wealth': 3, 'liquidity': 2, 'composition': 40, 'velocity': 2, 'counterparties': 1, 'jurisdiction': 1}` (app/logic/benchmark.py:14)
- [ ] class-level `NAME` exists in code but not in UML. UML: `—` · code: `str = 'benchmark'` (app/logic/benchmark.py:14)
- [ ] class-level `_COMPOSITION_PARTS` exists in code but not in UML. UML: `—` · code: `[('COMPOSITION_PROPERTY', 'property', 'expected_property', 'Property'), ('COMPOSITION_EQUITIES', 'listed_equities', 'expected_listed_equities', 'Listed equities…` (app/logic/benchmark.py:14)
- [ ] `_benchmark_checks()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:228` (app/logic/benchmark.py:228)
- [ ] `_best_market_stretch()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:202` (app/logic/benchmark.py:202)
- [ ] `_clean_country()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:119` (app/logic/benchmark.py:119)
- [ ] `_market_growth()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:195` (app/logic/benchmark.py:195)
- [ ] `_market_history()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:70` (app/logic/benchmark.py:70)
- [ ] `_run_rules()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:144` (app/logic/benchmark.py:144)

**`BenchmarkAI`**

- [ ] `_cache_payload()` exists in code but not in UML. UML: `—` · code: `app/ai/benchmark_ai.py:36` (app/ai/benchmark_ai.py:36)
- [ ] `_fill_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/benchmark_ai.py:30` (app/ai/benchmark_ai.py:30)

### Crime Scan (78)

**`CrimeScan`**

- [ ] `__warnings` exists in code but not in UML. UML: `—` · code: `list[str] = []` (app/logic/crime_scan.py:108)
- [ ] class-level `FULL_MATCH` exists in code but not in UML. UML: `—` · code: `('critical', 'high', 'medium')` (app/logic/crime_scan.py:17)
- [ ] class-level `MATCH_LABELS` exists in code but not in UML. UML: `—` · code: `{'critical': 'CRITICAL', 'high': 'HIGH', 'medium': 'MEDIUM', 'partial': 'PARTIAL', 'weak_signal': 'WEAK', 'no_match': 'NO MATCH'}` (app/logic/crime_scan.py:17)
- [ ] class-level `NAME` exists in code but not in UML. UML: `—` · code: `str = 'crime'` (app/logic/crime_scan.py:17)
- [ ] class-level `SIGN_LABELS` exists in code but not in UML. UML: `—` · code: `{'gift_or_inheritance_unnamed': 'gift or inheritance from someone unnamed', 'counterparty_unnamed': 'money from unnamed people', 'related_party_transaction': 'm…` (app/logic/crime_scan.py:17)
- [ ] class-level `SIGN_THEMES` exists in code but not in UML. UML: `—` · code: `{'gift_or_inheritance_unnamed': 'people', 'counterparty_unnamed': 'people', 'related_party_transaction': 'people', 'source_contradicts_occupation': 'sources', '…` (app/logic/crime_scan.py:17)
- [ ] class-level `WEAK_MATCH` exists in code but not in UML. UML: `—` · code: `('partial', 'weak_signal')` (app/logic/crime_scan.py:17)
- [ ] `__read_typology()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:275` (app/logic/crime_scan.py:275)
- [ ] `_assess()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:297` (app/logic/crime_scan.py:297)
- [ ] `_crime_checks()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:542` (app/logic/crime_scan.py:542)
- [ ] `_prepare_case()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:389` (app/logic/crime_scan.py:389)
- [ ] `_safe_int()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:374` (app/logic/crime_scan.py:374)
- [ ] `_split_org_names()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:292` (app/logic/crime_scan.py:292)
- [ ] `crime_declaration()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:502` (app/logic/crime_scan.py:502)
- [ ] `normalise_jurisdictions()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:464` (app/logic/crime_scan.py:464)
- [ ] `read_typologies()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:263` (app/logic/crime_scan.py:263)
- [ ] `warnings()` exists in code but not in UML. UML: `—` · code: `app/logic/crime_scan.py:133` (app/logic/crime_scan.py:133)

**`MatchResult`**

- [ ] `__category` exists in code but not in UML. UML: `—` · code: `str = category` (app/model/match_result.py:27)
- [ ] `__supporting_fired` exists in code but not in UML. UML: `—` · code: `list[str] = MatchResult.__signs('supporting', supporting_fired, self.__typology.supporting_indicators())` (app/model/match_result.py:23)
- [ ] class-level `CATEGORIES` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('critical', 'high', 'medium', 'partial', 'weak_signal', 'no_match')` (app/model/match_result.py:6)
- [ ] @property `category` in code is not shown in UML. UML: `—` · code: `getter` (app/model/match_result.py:6)
- [ ] @property `supporting_fired` in code is not shown in UML. UML: `—` · code: `getter` (app/model/match_result.py:6)
- [ ] `__signs()` exists in code but not in UML. UML: `—` · code: `app/model/match_result.py:66` (app/model/match_result.py:66)
- [ ] `fired()` exists in code but not in UML. UML: `—` · code: `app/model/match_result.py:51` (app/model/match_result.py:51)
- [ ] `to_dict()` exists in code but not in UML. UML: `—` · code: `app/model/match_result.py:55` (app/model/match_result.py:55)

**`ResearchAI`**

- [ ] class-level `ALLOWED_FIELDS` exists in code but not in UML. UML: `—` · code: `list[str] = ['industry', 'country']` (app/ai/research_ai.py:14)
- [ ] class-level `ATTEMPTS` exists in code but not in UML. UML: `—` · code: `int = 1` (app/ai/research_ai.py:14)
- [ ] `__api_sources()` exists in code but not in UML. UML: `—` · code: `app/ai/research_ai.py:110` (app/ai/research_ai.py:110)
- [ ] `__strip_excerpts()` exists in code but not in UML. UML: `—` · code: `app/ai/research_ai.py:103` (app/ai/research_ai.py:103)
- [ ] `_fill_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/research_ai.py:41` (app/ai/research_ai.py:41)
- [ ] `_options()` exists in code but not in UML. UML: `—` · code: `app/ai/research_ai.py:47` (app/ai/research_ai.py:47)
- [ ] `_prepare()` exists in code but not in UML. UML: `—` · code: `app/ai/research_ai.py:50` (app/ai/research_ai.py:50)

**`ResearchReport`**

- [ ] `__organisation` exists in code but not in UML. UML: `—` · code: `str = ResearchReport.__text('organisation', organisation or '')` (app/model/research_report.py:20)
- [ ] `__retrieved_at` exists in code but not in UML. UML: `—` · code: `str = ResearchReport.__text('retrieved_at', retrieved_at or '')` (app/model/research_report.py:27)
- [ ] `__summary` exists in code but not in UML. UML: `—` · code: `list[str] = [str(line) for line in ResearchReport.__list('summary', summary)]` (app/model/research_report.py:26)
- [ ] `__title` exists in code but not in UML. UML: `—` · code: `str = ResearchReport.__text('title', title or '')` (app/model/research_report.py:21)
- [ ] `__year` exists in code but not in UML. UML: `—` · code: `int | None = year if isinstance(year, int) else None` (app/model/research_report.py:23)
- [ ] @property `organisation` in code is not shown in UML. UML: `—` · code: `getter` (app/model/research_report.py:7)
- [ ] @property `retrieved_at` in code is not shown in UML. UML: `—` · code: `getter` (app/model/research_report.py:7)
- [ ] @property `summary` in code is not shown in UML. UML: `—` · code: `getter` (app/model/research_report.py:7)
- [ ] @property `title` in code is not shown in UML. UML: `—` · code: `getter` (app/model/research_report.py:7)
- [ ] @property `year` in code is not shown in UML. UML: `—` · code: `getter` (app/model/research_report.py:7)
- [ ] `__list()` exists in code but not in UML. UML: `—` · code: `app/model/research_report.py:99` (app/model/research_report.py:99)
- [ ] `__normalise()` exists in code but not in UML. UML: `—` · code: `app/model/research_report.py:107` (app/model/research_report.py:107)
- [ ] `__text()` exists in code but not in UML. UML: `—` · code: `app/model/research_report.py:93` (app/model/research_report.py:93)
- [ ] `from_dict()` exists in code but not in UML. UML: `—` · code: `app/model/research_report.py:30` (app/model/research_report.py:30)
- [ ] `retrieved_year()` exists in code but not in UML. UML: `—` · code: `app/model/research_report.py:70` (app/model/research_report.py:70)
- [ ] `to_dict()` exists in code but not in UML. UML: `—` · code: `app/model/research_report.py:86` (app/model/research_report.py:86)

**`Typology`**

- [ ] `__corroborated` exists in code but not in UML. UML: `—` · code: `bool = False` (app/model/typology.py:30)
- [ ] `__crime_category` exists in code but not in UML. UML: `—` · code: `str = Typology.__text('crime_category', crime_category)` (app/model/typology.py:23)
- [ ] `__description` exists in code but not in UML. UML: `—` · code: `str = Typology.__text('description', description)` (app/model/typology.py:24)
- [ ] `__outdated_source_ids` exists in code but not in UML. UML: `—` · code: `list[str] = []` (app/model/typology.py:31)
- [ ] `__source_ids` exists in code but not in UML. UML: `—` · code: `list[str] = [Typology.__text('source id', source_id) for source_id in Typology.__list('source_ids', source_ids)]` (app/model/typology.py:21)
- [ ] `__source_quotes` exists in code but not in UML. UML: `—` · code: `list[dict] = [Typology.__quote(quote) for quote in Typology.__list('source_quotes', source_quotes)]` (app/model/typology.py:25)
- [ ] `__typical_documents` exists in code but not in UML. UML: `—` · code: `list[str] = [Typology.__text('typical document', document) for document in Typology.__list('typical_documents', typical_documents)]` (app/model/typology.py:27)
- [ ] `__verified` exists in code but not in UML. UML: `—` · code: `bool = False` (app/model/typology.py:29)
- [ ] class-level `WEIGHTS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('core', 'supporting')` (app/model/typology.py:4)
- [ ] @property `corroborated` in code is not shown in UML. UML: `—` · code: `getter` (app/model/typology.py:4)
- [ ] @property `crime_category` in code is not shown in UML. UML: `—` · code: `getter` (app/model/typology.py:4)
- [ ] @property `description` in code is not shown in UML. UML: `—` · code: `getter` (app/model/typology.py:4)
- [ ] @property `outdated_source_ids` in code is not shown in UML. UML: `—` · code: `getter` (app/model/typology.py:4)
- [ ] @property `source_quotes` in code is not shown in UML. UML: `—` · code: `getter` (app/model/typology.py:4)
- [ ] @property `typical_documents` in code is not shown in UML. UML: `—` · code: `getter` (app/model/typology.py:4)
- [ ] @property `verified` in code is not shown in UML. UML: `—` · code: `getter` (app/model/typology.py:4)
- [ ] `__by_weight()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:127` (app/model/typology.py:127)
- [ ] `__indicator()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:131` (app/model/typology.py:131)
- [ ] `__list()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:152` (app/model/typology.py:152)
- [ ] `__quote()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:140` (app/model/typology.py:140)
- [ ] `__text()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:146` (app/model/typology.py:146)
- [ ] `from_dict()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:34` (app/model/typology.py:34)
- [ ] `supporting_indicators()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:93` (app/model/typology.py:93)
- [ ] `to_dict()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:116` (app/model/typology.py:116)
- [ ] `with_verified_sources()` exists in code but not in UML. UML: `—` · code: `app/model/typology.py:99` (app/model/typology.py:99)

**`TypologyAI`**

- [ ] class-level `ALLOWED_FIELDS` exists in code but not in UML. UML: `—` · code: `list[str] = ['occupation', 'industry', 'age', 'career_start_year', 'country']` (app/ai/typology_ai.py:13)
- [ ] class-level `REPORT_FIELDS` exists in code but not in UML. UML: `—` · code: `list[str] = ['report_id', 'organisation', 'title', 'year', 'summary', 'excerpts']` (app/ai/typology_ai.py:13)
- [ ] `_fill_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/typology_ai.py:41` (app/ai/typology_ai.py:41)
- [ ] `_prepare()` exists in code but not in UML. UML: `—` · code: `app/ai/typology_ai.py:59` (app/ai/typology_ai.py:59)
- [ ] `_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/typology_ai.py:50` (app/ai/typology_ai.py:50)

### Data (8)

**`ClientRepository`**

- [ ] `load()` exists in code but not in UML. UML: `—` · code: `app/data/client_repository.py:32` (app/data/client_repository.py:32)

**`ConfigReader`**

- [ ] `__files` exists in code but not in UML. UML: `—` · code: `dict[str, dict] = {}` (app/data/config_reader.py:22)
- [ ] class-level `REQUIRED` exists in code but not in UML. UML: `—` · code: `dict[str, tuple[str, ...]] = {'vocabulary': ('signal_codes', 'document_codes', 'source_types', 'crime_categories'), 'policy': ('policy_version', 'tolerance', 'f…` (app/data/config_reader.py:12)

**`DatabaseRepository`**

- [ ] @property `key_field` in code is not shown in UML. UML: `—` · code: `getter` (app/data/database_repository.py:13)
- [ ] @property `name` in code is not shown in UML. UML: `—` · code: `getter` (app/data/database_repository.py:13)

**`MongoRepository`**

- [ ] class-level `TIMEOUT_MS` exists in code but not in UML. UML: `—` · code: `int = 2000` (app/data/mongo_repository.py:15)
- [ ] `__collection()` exists in code but not in UML. UML: `—` · code: `app/data/mongo_repository.py:67` (app/data/mongo_repository.py:67)

**`Repository`**

- [ ] `__init__()` exists in code but not in UML. UML: `—` · code: `app/data/repository.py:10` (app/data/repository.py:10)

### Document Evidence (31)

**`DocumentAI`**

- [ ] class-level `MAX_DOCUMENTS` exists in code but not in UML. UML: `—` · code: `int = 10` (app/ai/document_ai.py:13)
- [ ] class-level `READABLE_KINDS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('text', 'image', 'pdf')` (app/ai/document_ai.py:13)
- [ ] `_cache_payload()` exists in code but not in UML. UML: `—` · code: `app/ai/document_ai.py:77` (app/ai/document_ai.py:77)
- [ ] `_fill_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/document_ai.py:71` (app/ai/document_ai.py:71)
- [ ] `_options()` exists in code but not in UML. UML: `—` · code: `app/ai/document_ai.py:74` (app/ai/document_ai.py:74)
- [ ] `run()` exists in code but not in UML. UML: `—` · code: `app/ai/document_ai.py:31` (app/ai/document_ai.py:31)

**`DocumentEvidence`**

- [ ] `__reader` exists in code but not in UML. UML: `—` · code: `CaseReader = CaseReader()` (app/logic/document_evidence.py:20)
- [ ] class-level `NAME` exists in code but not in UML. UML: `—` · code: `str = 'documents'` (app/logic/document_evidence.py:8)
- [ ] `_document_checks()` exists in code but not in UML. UML: `—` · code: `app/logic/document_evidence.py:60` (app/logic/document_evidence.py:60)
- [ ] `_read()` exists in code but not in UML. UML: `—` · code: `app/logic/document_evidence.py:33` (app/logic/document_evidence.py:33)

**`DocumentReader`**

- [ ] `_text_result()` exists in code but not in UML. UML: `—` · code: `app/data/document_reader.py:30` (app/data/document_reader.py:30)

**`DocumentReaderFactory`**

- [ ] `__readers` exists in code but not in UML. UML: `—` · code: `dict[str, type[DocumentReader]] = {'.pdf': PdfReader, '.docx': WordReader, '.xlsx': ExcelReader, '.xlsm': ExcelReader}` (app/data/document_reader_factory.py:18)

**`DocumentRecordBuilder`**

- [ ] `__config` exists in code but not in UML. UML: `—` · code: `Config = config or Config({}, {})` (app/logic/document_record_builder.py:26)
- [ ] class-level `SUMMARY_SECTIONS` exists in code but not in UML. UML: `—` · code: `{'name': 'Client', 'nationality': 'Client', 'career': 'Client', 'career_history': 'Career history', 'investments': 'Assets', 'claims': 'Financial claims', 'sow_…` (app/logic/document_record_builder.py:11)
- [ ] `__finish_layout()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:211` (app/logic/document_record_builder.py:211)
- [ ] `__is_number()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:325` (app/logic/document_record_builder.py:325)
- [ ] `_asset_group()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:140` (app/logic/document_record_builder.py:140)
- [ ] `_blank()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:41` (app/logic/document_record_builder.py:41)
- [ ] `_field()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:131` (app/logic/document_record_builder.py:131)
- [ ] `_job_group()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:136` (app/logic/document_record_builder.py:136)
- [ ] `_missing()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:186` (app/logic/document_record_builder.py:186)
- [ ] `_optional_fields()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:286` (app/logic/document_record_builder.py:286)
- [ ] `_required_fields()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:143` (app/logic/document_record_builder.py:143)
- [ ] `_split_against_assets()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:258` (app/logic/document_record_builder.py:258)
- [ ] `check()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:224` (app/logic/document_record_builder.py:224)
- [ ] `finish()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:206` (app/logic/document_record_builder.py:206)
- [ ] `get_path()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:109` (app/logic/document_record_builder.py:109)
- [ ] `set_path()` exists in code but not in UML. UML: `—` · code: `app/logic/document_record_builder.py:121` (app/logic/document_record_builder.py:121)

**`DocumentStore`**

- [ ] `__root` exists in code but not in UML. UML: `—` · code: `str = root` (app/data/document_store.py:23)
- [ ] `owns()` exists in code but not in UML. UML: `—` · code: `app/data/document_store.py:40` (app/data/document_store.py:40)

**`TextReader`**

- [ ] class-level `TEXT_TYPES` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('.txt', '.csv', '.md', '.json')` (app/data/document_reader.py:117)

### Forecast (80)

**`AssetPath`**

- [ ] `__asset_models` exists in code but not in UML. UML: `—` · code: `list[dict] = sorted(asset_models or [], key=lambda model: model['asset_index'])` (app/logic/asset_path.py:18)
- [ ] `__one_path()` exists in code but not in UML. UML: `—` · code: `app/logic/asset_path.py:38` (app/logic/asset_path.py:38)

**`Forecast`**

- [ ] class-level `NAME` exists in code but not in UML. UML: `—` · code: `str = 'forecast'` (app/logic/forecast.py:15)
- [ ] `__use()` exists in code but not in UML. UML: `—` · code: `app/logic/forecast.py:58` (app/logic/forecast.py:58)
- [ ] `_assess()` exists in code but not in UML. UML: `—` · code: `app/logic/forecast.py:139` (app/logic/forecast.py:139)
- [ ] `_enabled_by_text()` exists in code but not in UML. UML: `—` · code: `app/logic/forecast.py:66` (app/logic/forecast.py:66)
- [ ] `_forecast_checks()` exists in code but not in UML. UML: `—` · code: `app/logic/forecast.py:291` (app/logic/forecast.py:291)
- [ ] `calibrate_pay()` exists in code but not in UML. UML: `—` · code: `app/logic/forecast.py:54` (app/logic/forecast.py:54)
- [ ] `honest_numbers()` exists in code but not in UML. UML: `—` · code: `app/logic/forecast.py:49` (app/logic/forecast.py:49)

**`ForecastAI`**

- [ ] `__schemas` exists in code but not in UML. UML: `—` · code: `dict = {}` (app/ai/forecast_ai.py:48)
- [ ] `__settings` exists in code but not in UML. UML: `—` · code: `dict = settings or {}` (app/ai/forecast_ai.py:46)
- [ ] `__vocabulary` exists in code but not in UML. UML: `—` · code: `dict = vocabulary or {}` (app/ai/forecast_ai.py:47)
- [ ] class-level `BASELINE_TYPE` exists in code but not in UML. UML: `—` · code: `str = 'T1'` (app/ai/forecast_ai.py:19)
- [ ] class-level `RANGE_KEYS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('low', 'typical', 'high')` (app/ai/forecast_ai.py:19)
- [ ] class-level `REPORTING_CURRENCY` exists in code but not in UML. UML: `—` · code: `str = 'SGD'` (app/ai/forecast_ai.py:19)
- [ ] class-level `SCENARIOS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('steady', 'boom', 'downturn')` (app/ai/forecast_ai.py:19)
- [ ] class-level `STAGES` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('step0_declaration', 'call1_markets', 'call2_earnings', 'call3_types', 'call4_events')` (app/ai/forecast_ai.py:19)
- [ ] `_add_vocabulary()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:141` (app/ai/forecast_ai.py:141)
- [ ] `_ask()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:734` (app/ai/forecast_ai.py:734)
- [ ] `_build_instructions()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:128` (app/ai/forecast_ai.py:128)
- [ ] `_can_ask()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:80` (app/ai/forecast_ai.py:80)
- [ ] `_career_positions()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:84` (app/ai/forecast_ai.py:84)
- [ ] `_career_years()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:96` (app/ai/forecast_ai.py:96)
- [ ] `_check_future_pay()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:384` (app/ai/forecast_ai.py:384)
- [ ] `_check_market_series()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:357` (app/ai/forecast_ai.py:357)
- [ ] `_check_markets_list()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:338` (app/ai/forecast_ai.py:338)
- [ ] `_check_position_pay()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:377` (app/ai/forecast_ai.py:377)
- [ ] `_check_type_behaviour()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:668` (app/ai/forecast_ai.py:668)
- [ ] `_check_type_reactions()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:717` (app/ai/forecast_ai.py:717)
- [ ] `_client_facts()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:196` (app/ai/forecast_ai.py:196)
- [ ] `_crime_categories()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:836` (app/ai/forecast_ai.py:836)
- [ ] `_current_year()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:92` (app/ai/forecast_ai.py:92)
- [ ] `_empty_result()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:728` (app/ai/forecast_ai.py:728)
- [ ] `_extract_json()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:167` (app/ai/forecast_ai.py:167)
- [ ] `_fallback_asset_model()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:437` (app/ai/forecast_ai.py:437)
- [ ] `_fill_placeholders()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:119` (app/ai/forecast_ai.py:119)
- [ ] `_follows_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:157` (app/ai/forecast_ai.py:157)
- [ ] `_future_years()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:107` (app/ai/forecast_ai.py:107)
- [ ] `_link_typologies()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:449` (app/ai/forecast_ai.py:449)
- [ ] `_load_forecast_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:114` (app/ai/forecast_ai.py:114)
- [ ] `_load_forecast_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:151` (app/ai/forecast_ai.py:151)
- [ ] `_looks_like_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:268` (app/ai/forecast_ai.py:268)
- [ ] `_market_changes()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:820` (app/ai/forecast_ai.py:820)
- [ ] `_market_outlooks()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:826` (app/ai/forecast_ai.py:826)
- [ ] `_markets_brief()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:815` (app/ai/forecast_ai.py:815)
- [ ] `_parse_reply()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:253` (app/ai/forecast_ai.py:253)
- [ ] `_position_end()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:103` (app/ai/forecast_ai.py:103)
- [ ] `_range_errors()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:219` (app/ai/forecast_ai.py:219)
- [ ] `_read_declaration()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:846` (app/ai/forecast_ai.py:846)
- [ ] `_repair_asset_model()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:413` (app/ai/forecast_ai.py:413)
- [ ] `_repair_person_types()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:486` (app/ai/forecast_ai.py:486)
- [ ] `_repair_type_behaviour()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:628` (app/ai/forecast_ai.py:628)
- [ ] `_repair_type_reactions()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:655` (app/ai/forecast_ai.py:655)
- [ ] `_run_forecast()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:1099` (app/ai/forecast_ai.py:1099)
- [ ] `_settings()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:74` (app/ai/forecast_ai.py:74)
- [ ] `_sort_ranges()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:235` (app/ai/forecast_ai.py:235)
- [ ] `_stopped()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:1087` (app/ai/forecast_ai.py:1087)
- [ ] `_strip_keys()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:181` (app/ai/forecast_ai.py:181)
- [ ] `_top_level_keys()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:263` (app/ai/forecast_ai.py:263)
- [ ] `_types_brief()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:831` (app/ai/forecast_ai.py:831)
- [ ] `_typologies_brief()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:966` (app/ai/forecast_ai.py:966)
- [ ] `_unknown_ids()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:307` (app/ai/forecast_ai.py:307)
- [ ] `_validate_reply()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:273` (app/ai/forecast_ai.py:273)
- [ ] `_vocabulary()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:77` (app/ai/forecast_ai.py:77)
- [ ] `_wrap_free_text()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:190` (app/ai/forecast_ai.py:190)
- [ ] `_years_errors()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:292` (app/ai/forecast_ai.py:292)
- [ ] `_years_text()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:810` (app/ai/forecast_ai.py:810)

**`FuturePaths`**

- [ ] `__forecast` exists in code but not in UML. UML: `—` · code: `dict = forecast or {}` (app/logic/future_paths.py:22)
- [ ] `__market_model` exists in code but not in UML. UML: `—` · code: `MarketModel = market_model or MarketModel()` (app/logic/future_paths.py:24)
- [ ] `__policy` exists in code but not in UML. UML: `—` · code: `dict = policy or {}` (app/logic/future_paths.py:23)
- [ ] class-level `BASELINE_TYPE` exists in code but not in UML. UML: `—` · code: `str = 'T1'` (app/logic/future_paths.py:10)
- [ ] `asset_path()` exists in code but not in UML. UML: `—` · code: `app/logic/future_paths.py:33` (app/logic/future_paths.py:33)
- [ ] `extra_money_up_to()` exists in code but not in UML. UML: `—` · code: `app/logic/future_paths.py:36` (app/logic/future_paths.py:36)
- [ ] `forward_paths()` exists in code but not in UML. UML: `—` · code: `app/logic/future_paths.py:63` (app/logic/future_paths.py:63)
- [ ] `type_wealth_now()` exists in code but not in UML. UML: `—` · code: `app/logic/future_paths.py:55` (app/logic/future_paths.py:55)

**`MarketModel`**

- [ ] class-level `RANGE_KEYS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('low', 'typical', 'high')` (app/logic/market_model.py:4)
- [ ] class-level `SCENARIOS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('steady', 'boom', 'downturn')` (app/logic/market_model.py:4)

**`OnboardingAssessor`**

- [ ] `_check_asset_income()` exists in code but not in UML. UML: `—` · code: `app/logic/onboarding_assessor.py:45` (app/logic/onboarding_assessor.py:45)
- [ ] `_check_declared_sources()` exists in code but not in UML. UML: `—` · code: `app/logic/onboarding_assessor.py:100` (app/logic/onboarding_assessor.py:100)
- [ ] `_fit_for_type()` exists in code but not in UML. UML: `—` · code: `app/logic/onboarding_assessor.py:119` (app/logic/onboarding_assessor.py:119)

### Shared core (276)

**`AIService`**

- [ ] `_warnings` exists in code but not in UML. UML: `—` · code: `list[str] = []` (app/ai/ai_service.py:44)
- [ ] class-level `ATTEMPTS` exists in code but not in UML. UML: `—` · code: `int = 2` (app/ai/ai_service.py:20)
- [ ] `_cache_payload()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:97` (app/ai/ai_service.py:97)
- [ ] `_cached()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:175` (app/ai/ai_service.py:175)
- [ ] `_fill_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:89` (app/ai/ai_service.py:89)
- [ ] `_load_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:156` (app/ai/ai_service.py:156)
- [ ] `_load_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:160` (app/ai/ai_service.py:160)
- [ ] `_options()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:101` (app/ai/ai_service.py:101)
- [ ] `_prepare()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:105` (app/ai/ai_service.py:105)
- [ ] `_prompt_version()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:164` (app/ai/ai_service.py:164)
- [ ] `_save()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:180` (app/ai/ai_service.py:180)
- [ ] `_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:93` (app/ai/ai_service.py:93)
- [ ] `_without_notes()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:171` (app/ai/ai_service.py:171)
- [ ] `warnings()` exists in code but not in UML. UML: `—` · code: `app/ai/ai_service.py:46` (app/ai/ai_service.py:46)

**`App`**

- [ ] `__cloud_syncs` exists in code but not in UML. UML: `—` · code: `list[CloudSync] = [CloudSync(self.__clients, MongoRepository(App.CLIENT_COLLECTION, 'client_ref', uri), state_path), CloudSync(self.__assessments, MongoReposito…` (app/application/app.py:87)
- [ ] `__config_reader` exists in code but not in UML. UML: `—` · code: `ConfigReader = ConfigReader(os.path.join(root, 'config'))` (app/application/app.py:73)
- [ ] `__rate_limiter` exists in code but not in UML. UML: `—` · code: `RateLimiter = RateLimiter(policy.get('assessment_rate_limit', {}))` (app/application/app.py:107)
- [ ] `__root` exists in code but not in UML. UML: `—` · code: `str = root` (app/application/app.py:68)
- [ ] class-level `ASSESSMENT_COLLECTION` exists in code but not in UML. UML: `—` · code: `str = 'ai_assessments'` (app/application/app.py:43)
- [ ] class-level `CLIENT_COLLECTION` exists in code but not in UML. UML: `—` · code: `str = 'client_cases'` (app/application/app.py:43)
- [ ] class-level `NOISY_LOGGERS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('httpx', 'httpcore', 'httpx2', 'httpcore2', 'openai', 'urllib3', 'google_genai', 'hpack', 'pymongo')` (app/application/app.py:43)
- [ ] @property `config` in code is not shown in UML. UML: `—` · code: `getter` (app/application/app.py:43)
- [ ] `__ai_model()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:554` (app/application/app.py:554)
- [ ] `__assess_if_allowed()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:601` (app/application/app.py:601)
- [ ] `__configure_logging()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:634` (app/application/app.py:634)
- [ ] `__create_document_ai()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:558` (app/application/app.py:558)
- [ ] `__create_runner()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:564` (app/application/app.py:564)
- [ ] `__crime_declaration_layout()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:326` (app/application/app.py:326)
- [ ] `__crime_result_layout()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:331` (app/application/app.py:331)
- [ ] `__fill_field()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:610` (app/application/app.py:610)
- [ ] `__handle_failure_quietly()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:594` (app/application/app.py:594)
- [ ] `__saved_verdict()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:622` (app/application/app.py:622)
- [ ] `__show_step()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:619` (app/application/app.py:619)
- [ ] `ai_available()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:136` (app/application/app.py:136)
- [ ] `assess()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:258` (app/application/app.py:258)
- [ ] `assessments()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:537` (app/application/app.py:537)
- [ ] `clients()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:534` (app/application/app.py:534)
- [ ] `documents()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:540` (app/application/app.py:540)
- [ ] `forecast_settings()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:123` (app/application/app.py:123)
- [ ] `new_client_ref()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:487` (app/application/app.py:487)
- [ ] `rate_limiter()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:543` (app/application/app.py:543)
- [ ] `read_amount()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:495` (app/application/app.py:495)
- [ ] `read_case()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:253` (app/application/app.py:253)
- [ ] `read_documents()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:474` (app/application/app.py:474)
- [ ] `record_builder()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:483` (app/application/app.py:483)
- [ ] `response_cache()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:546` (app/application/app.py:546)
- [ ] `runner()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:549` (app/application/app.py:549)
- [ ] `save_assessment()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:291` (app/application/app.py:291)
- [ ] `start_web()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:186` (app/application/app.py:186)
- [ ] `steps()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:115` (app/application/app.py:115)
- [ ] `validate_case()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:491` (app/application/app.py:491)

**`AssessmentRunner`**

- [ ] `__benchmark` exists in code but not in UML. UML: `—` · code: `Benchmark = Benchmark(policy, self.__config)` (app/application/assessment_runner.py:82)
- [ ] `__benchmark_ai` exists in code but not in UML. UML: `—` · code: `BenchmarkAI | None = benchmark_ai` (app/application/assessment_runner.py:67)
- [ ] `__case_reader` exists in code but not in UML. UML: `—` · code: `CaseReader = CaseReader()` (app/application/assessment_runner.py:73)
- [ ] `__crime_scan` exists in code but not in UML. UML: `—` · code: `CrimeScan = CrimeScan(policy)` (app/application/assessment_runner.py:74)
- [ ] `__crime_scan_lock` exists in code but not in UML. UML: `—` · code: `threading.Lock = threading.Lock()` (app/application/assessment_runner.py:77)
- [ ] `__document_ai` exists in code but not in UML. UML: `—` · code: `DocumentAI | None = document_ai` (app/application/assessment_runner.py:68)
- [ ] `__document_store` exists in code but not in UML. UML: `—` · code: `DocumentStore | None = document_store` (app/application/assessment_runner.py:70)
- [ ] `__documents` exists in code but not in UML. UML: `—` · code: `DocumentEvidence = DocumentEvidence(policy)` (app/application/assessment_runner.py:81)
- [ ] `__engine` exists in code but not in UML. UML: `—` · code: `VerdictEngine = VerdictEngine([self.__crime_scan, self.__documents, self.__benchmark, self.__forecast], self.__config)` (app/application/assessment_runner.py:84)
- [ ] `__forecast` exists in code but not in UML. UML: `—` · code: `Forecast = Forecast(policy, self.__config)` (app/application/assessment_runner.py:83)
- [ ] `__forecast_ai` exists in code but not in UML. UML: `—` · code: `ForecastAI | None = forecast_ai` (app/application/assessment_runner.py:69)
- [ ] `__forecast_lock` exists in code but not in UML. UML: `—` · code: `threading.Lock = threading.Lock()` (app/application/assessment_runner.py:80)
- [ ] `__research_ai` exists in code but not in UML. UML: `—` · code: `ResearchAI | None = research_ai` (app/application/assessment_runner.py:65)
- [ ] `__response_cache` exists in code but not in UML. UML: `—` · code: `ResponseCache | None = response_cache` (app/application/assessment_runner.py:71)
- [ ] `__typology_ai` exists in code but not in UML. UML: `—` · code: `TypologyAI | None = typology_ai` (app/application/assessment_runner.py:66)
- [ ] class-level `FORECAST_STEP` exists in code but not in UML. UML: `—` · code: `dict[str, int] = {'step0_declaration': 6, 'call1_markets': 7, 'call2_earnings': 8, 'call3_types': 9, 'call4_events': 10}` (app/application/assessment_runner.py:27)
- [ ] `__crime_categories()` exists in code but not in UML. UML: `—` · code: `app/application/assessment_runner.py:257` (app/application/assessment_runner.py:257)
- [ ] `engine()` exists in code but not in UML. UML: `—` · code: `app/application/assessment_runner.py:87` (app/application/assessment_runner.py:87)

**`Band`**

- [ ] `__eq__()` exists in code but not in UML. UML: `—` · code: `app/model/band.py:37` (app/model/band.py:37)
- [ ] `__repr__()` exists in code but not in UML. UML: `—` · code: `app/model/band.py:40` (app/model/band.py:40)
- [ ] `add()` exists in code but not in UML. UML: `—` · code: `app/model/band.py:74` (app/model/band.py:74)
- [ ] `as_dict()` exists in code but not in UML. UML: `—` · code: `app/model/band.py:66` (app/model/band.py:66)
- [ ] `from_ai()` exists in code but not in UML. UML: `—` · code: `app/model/band.py:86` (app/model/band.py:86)
- [ ] `ordered()` exists in code but not in UML. UML: `—` · code: `app/model/band.py:82` (app/model/band.py:82)
- [ ] `scale()` exists in code but not in UML. UML: `—` · code: `app/model/band.py:78` (app/model/band.py:78)
- [ ] `zero()` exists in code but not in UML. UML: `—` · code: `app/model/band.py:70` (app/model/band.py:70)

**`CaseBuilder`**

- [ ] `__case_schema` exists in code but not in UML. UML: `—` · code: `dict = case_schema or {}` (app/interface/case_builder.py:20)
- [ ] `_composition_from_record()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:163` (app/interface/case_builder.py:163)
- [ ] `_first_filled()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:123` (app/interface/case_builder.py:123)
- [ ] `_payment_method()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:53` (app/interface/case_builder.py:53)
- [ ] `_text_or_ask()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:79` (app/interface/case_builder.py:79)
- [ ] `case_from_client_record()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:184` (app/interface/case_builder.py:184)
- [ ] `validate_case()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:22` (app/interface/case_builder.py:22)

**`CaseReader`**

- [ ] class-level `COMPOSITION_KEYS` exists in code but not in UML. UML: `—` · code: `['property', 'listed_equities', 'private_business', 'cash']` (app/logic/case_reader.py:4)
- [ ] `_read_payment()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:42` (app/logic/case_reader.py:42)
- [ ] `_whole_number()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:240` (app/logic/case_reader.py:240)
- [ ] `_whole_percent()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:209` (app/logic/case_reader.py:209)
- [ ] `benchmark_input()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:215` (app/logic/case_reader.py:215)
- [ ] `crime_scan_input()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:193` (app/logic/case_reader.py:193)

**`Check`**

- [ ] `__empty_lists` exists in code but not in UML. UML: `—` · code: `list[str] = [name for name, value in (('sources', sources), ('supports', supports)) if value is not None and (not value)]` (app/model/check.py:33)
- [ ] `__extra` exists in code but not in UML. UML: `—` · code: `dict = {}` (app/model/check.py:36)
- [ ] class-level `FIELDS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('feature', 'check', 'label', 'theme', 'status', 'detail', 'explanation', 'group', 'sources', 'supports')` (app/model/check.py:4)
- [ ] `extra()` exists in code but not in UML. UML: `—` · code: `app/model/check.py:88` (app/model/check.py:88)
- [ ] `from_dict()` exists in code but not in UML. UML: `—` · code: `app/model/check.py:114` (app/model/check.py:114)
- [ ] `set_extra()` exists in code but not in UML. UML: `—` · code: `app/model/check.py:92` (app/model/check.py:92)

**`ClaimedSource`**

- [ ] `__amount_explained` exists in code but not in UML. UML: `—` · code: `bool = bool(amount_explained)` (app/model/claimed_source.py:38)
- [ ] `__country` exists in code but not in UML. UML: `—` · code: `str | None = country` (app/model/claimed_source.py:43)
- [ ] `__description` exists in code but not in UML. UML: `—` · code: `str = description` (app/model/claimed_source.py:40)
- [ ] `__end_year` exists in code but not in UML. UML: `—` · code: `int | None = end_year` (app/model/claimed_source.py:42)
- [ ] `__layout` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = tuple(layout)` (app/model/claimed_source.py:48)
- [ ] `__linked_asset_index` exists in code but not in UML. UML: `—` · code: `int | None = linked_asset_index` (app/model/claimed_source.py:46)
- [ ] `__linked_position_index` exists in code but not in UML. UML: `—` · code: `int | None = linked_position_index` (app/model/claimed_source.py:45)
- [ ] `__quote` exists in code but not in UML. UML: `—` · code: `str = quote` (app/model/claimed_source.py:44)
- [ ] `__source_id` exists in code but not in UML. UML: `—` · code: `str | None = source_id` (app/model/claimed_source.py:39)
- [ ] `__start_year` exists in code but not in UML. UML: `—` · code: `int | None = start_year` (app/model/claimed_source.py:41)
- [ ] class-level `GIFT_TYPES` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('inheritance', 'gift')` (app/model/claimed_source.py:4)
- [ ] class-level `READING_KEYS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('source_id', 'source_type', 'description', 'start_year', 'end_year', 'amount', 'country', 'linked_position_index', 'linked_asset_index', 'quo…` (app/model/claimed_source.py:4)
- [ ] class-level `__SCAN_NAMES` exists in code but not in UML. UML: `—` · code: `dict = {'amount_sgd': 'amount', 'jurisdiction': 'country', 'evidence_sentence': 'quote'}` (app/model/claimed_source.py:4)
- [ ] @property `amount_explained` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] @property `country` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] @property `description` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] @property `end_year` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] @property `linked_asset_index` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] @property `linked_position_index` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] @property `quote` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] @property `source_id` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] @property `start_year` in code is not shown in UML. UML: `—` · code: `getter` (app/model/claimed_source.py:4)
- [ ] `__check_index()` exists in code but not in UML. UML: `—` · code: `app/model/claimed_source.py:177` (app/model/claimed_source.py:177)
- [ ] `__check_layout()` exists in code but not in UML. UML: `—` · code: `app/model/claimed_source.py:187` (app/model/claimed_source.py:187)
- [ ] `__check_year()` exists in code but not in UML. UML: `—` · code: `app/model/claimed_source.py:173` (app/model/claimed_source.py:173)
- [ ] `__is_whole()` exists in code but not in UML. UML: `—` · code: `app/model/claimed_source.py:181` (app/model/claimed_source.py:181)
- [ ] `counterparty_read()` exists in code but not in UML. UML: `—` · code: `app/model/claimed_source.py:138` (app/model/claimed_source.py:138)
- [ ] `from_dict()` exists in code but not in UML. UML: `—` · code: `app/model/claimed_source.py:51` (app/model/claimed_source.py:51)
- [ ] `to_dict()` exists in code but not in UML. UML: `—` · code: `app/model/claimed_source.py:146` (app/model/claimed_source.py:146)
- [ ] `to_scan_dict()` exists in code but not in UML. UML: `—` · code: `app/model/claimed_source.py:156` (app/model/claimed_source.py:156)

**`Claims`**

- [ ] `__extra` exists in code but not in UML. UML: `—` · code: `dict = dict(extra or {})` (app/model/claims.py:28)
- [ ] class-level `LIQUID_PARTS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('listed_equities', 'cash')` (app/model/claims.py:4)
- [ ] class-level `NO_PEP_VALUES` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('', 'none', 'no', 'not a pep', 'n/a', 'na')` (app/model/claims.py:4)
- [ ] `to_dict()` exists in code but not in UML. UML: `—` · code: `app/model/claims.py:123` (app/model/claims.py:123)

**`ClientForm`**

- [ ] `__report_view` exists in code but not in UML. UML: `—` · code: `ReportView = report_view or ReportView(self.__ui)` (app/interface/client_form.py:38)
- [ ] class-level `PAYMENT_METHODS` exists in code but not in UML. UML: `—` · code: `['cash', 'loan', 'asset_sale']` (app/interface/client_form.py:21)
- [ ] class-level `PEP_OPTIONS` exists in code but not in UML. UML: `—` · code: `list[str] = ['None', 'Domestic PEP', 'Foreign PEP', 'International organisation PEP', 'Family member / close associate of a PEP']` (app/interface/client_form.py:21)
- [ ] `add_asset_record()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:421` (app/interface/client_form.py:421)
- [ ] `add_career_record()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:378` (app/interface/client_form.py:378)
- [ ] `add_supporting_documents()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:521` (app/interface/client_form.py:521)
- [ ] `ask_after_save()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:339` (app/interface/client_form.py:339)
- [ ] `ask_missing_field()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:305` (app/interface/client_form.py:305)
- [ ] `edit_asset_composition()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:481` (app/interface/client_form.py:481)
- [ ] `edit_client_declarations()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:489` (app/interface/client_form.py:489)
- [ ] `edit_client_profile()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:352` (app/interface/client_form.py:352)
- [ ] `find_existing_client()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:640` (app/interface/client_form.py:640)
- [ ] `get_career_history()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:86` (app/interface/client_form.py:86)
- [ ] `get_client_profile()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:45` (app/interface/client_form.py:45)
- [ ] `get_investments()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:119` (app/interface/client_form.py:119)
- [ ] `get_sow_declaration()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:158` (app/interface/client_form.py:158)
- [ ] `get_supporting_documents()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:162` (app/interface/client_form.py:162)

**`ClientProfile`**

- [ ] class-level `MAX_AGE` exists in code but not in UML. UML: `—` · code: `int = 120` (app/model/client_profile.py:4)
- [ ] class-level `MIN_AGE` exists in code but not in UML. UML: `—` · code: `int = 18` (app/model/client_profile.py:4)
- [ ] `__text()` exists in code but not in UML. UML: `—` · code: `app/model/client_profile.py:55` (app/model/client_profile.py:55)

**`ClientRecord`**

- [ ] `__career_extra` exists in code but not in UML. UML: `—` · code: `dict = {}` (app/model/client_record.py:42)
- [ ] `__extra` exists in code but not in UML. UML: `—` · code: `dict = {}` (app/model/client_record.py:41)
- [ ] class-level `CAREER_JOB_KEYS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('occupation', 'seniority', 'industry', 'employer_name', 'employer_size')` (app/model/client_record.py:12)
- [ ] class-level `MIN_WORKING_AGE` exists in code but not in UML. UML: `—` · code: `int = 14` (app/model/client_record.py:12)
- [ ] class-level `REQUIRED` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('client_ref', 'name', 'nationality', 'current_date')` (app/model/client_record.py:12)
- [ ] class-level `__OWN_KEYS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('client_ref', 'name', 'nationality', 'current_date', 'career', 'career_history', 'investments', 'claims', 'sow_declaration', 'supporting_docu…` (app/model/client_record.py:12)
- [ ] @property `claims` in code is not shown in UML. UML: `—` · code: `getter` (app/model/client_record.py:12)
- [ ] @property `declaration` in code is not shown in UML. UML: `—` · code: `getter` (app/model/client_record.py:12)
- [ ] `__this_year()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:160` (app/model/client_record.py:160)
- [ ] `__whole()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:325` (app/model/client_record.py:325)
- [ ] `__whole_percent()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:337` (app/model/client_record.py:337)
- [ ] `career_start_year()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:131` (app/model/client_record.py:131)
- [ ] `investments()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:85` (app/model/client_record.py:85)

**`Config`**

- [ ] `asset_category()` exists in code but not in UML. UML: `—` · code: `app/model/config.py:32` (app/model/config.py:32)

**`ConsoleUI`**

- [ ] `__width` exists in code but not in UML. UML: `—` · code: `int = len(ConsoleUI.LINE)` (app/interface/console_ui.py:38)
- [ ] class-level `LABEL` exists in code but not in UML. UML: `—` · code: `" '.-&/,()%#0123456789"` (app/interface/console_ui.py:13)
- [ ] `_words_error()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:311` (app/interface/console_ui.py:311)
- [ ] `ask_composition()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:241` (app/interface/console_ui.py:241)
- [ ] `ask_count()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:346` (app/interface/console_ui.py:346)
- [ ] `ask_countries()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:332` (app/interface/console_ui.py:332)
- [ ] `ask_currency()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:234` (app/interface/console_ui.py:234)
- [ ] `ask_document_folder()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:123` (app/interface/console_ui.py:123)
- [ ] `ask_document_record_action()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:154` (app/interface/console_ui.py:154)
- [ ] `ask_words()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:316` (app/interface/console_ui.py:316)
- [ ] `display_section()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:100` (app/interface/console_ui.py:100)
- [ ] `keep_count()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:354` (app/interface/console_ui.py:354)
- [ ] `keep_int()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:279` (app/interface/console_ui.py:279)
- [ ] `keep_words()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:323` (app/interface/console_ui.py:323)
- [ ] `read_number()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:381` (app/interface/console_ui.py:381)
- [ ] `read_year()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:398` (app/interface/console_ui.py:398)
- [ ] `show_ai_progress()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:374` (app/interface/console_ui.py:374)
- [ ] `show_case_problems()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:364` (app/interface/console_ui.py:364)
- [ ] `show_client_list()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:107` (app/interface/console_ui.py:107)
- [ ] `show_documents_found()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:143` (app/interface/console_ui.py:143)
- [ ] `show_missing_intro()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:148` (app/interface/console_ui.py:148)
- [ ] `show_unexpected_error()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:70` (app/interface/console_ui.py:70)

**`Declaration`**

- [ ] `from_dict()` exists in code but not in UML. UML: `—` · code: `app/model/declaration.py:20` (app/model/declaration.py:20)
- [ ] `to_dict()` exists in code but not in UML. UML: `—` · code: `app/model/declaration.py:43` (app/model/declaration.py:43)
- [ ] `to_scan_dict()` exists in code but not in UML. UML: `—` · code: `app/model/declaration.py:47` (app/model/declaration.py:47)

**`Investment`**

- [ ] `__extra` exists in code but not in UML. UML: `—` · code: `dict = dict(extra or {})` (app/model/investment.py:23)
- [ ] `__check_year()` exists in code but not in UML. UML: `—` · code: `app/model/investment.py:88` (app/model/investment.py:88)

**`Job`**

- [ ] `__extra` exists in code but not in UML. UML: `—` · code: `dict = dict(extra or {})` (app/model/job.py:23)
- [ ] class-level `KEYS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('start_year', 'end_year', 'occupation', 'seniority', 'industry', 'employer_name', 'employer_size', 'country')` (app/model/job.py:4)

**`RateLimiter`**

- [ ] `__enabled` exists in code but not in UML. UML: `—` · code: `bool = bool(settings.get('enabled', True))` (app/interface/rate_limiter.py:17)
- [ ] `__last_started` exists in code but not in UML. UML: `—` · code: `dict[str, float] = {}` (app/interface/rate_limiter.py:19)
- [ ] class-level `DEFAULT_COOLDOWN_SECONDS` exists in code but not in UML. UML: `—` · code: `int = 60` (app/interface/rate_limiter.py:6)
- [ ] `reset()` exists in code but not in UML. UML: `—` · code: `app/interface/rate_limiter.py:37` (app/interface/rate_limiter.py:37)

**`ReportView`**

- [ ] class-level `REPORT_WIDTH` exists in code but not in UML. UML: `—` · code: `96` (app/interface/report_view.py:12)
- [ ] class-level `SOURCE_TAGS` exists in code but not in UML. UML: `—` · code: `{'documents': '[DOC]   ', 'edited': '[EDITED]', 'entered': '[YOU]   ', 'blank': '[ -- ]  '}` (app/interface/report_view.py:12)
- [ ] class-level `_CRIME_CATEGORY_LABEL` exists in code but not in UML. UML: `—` · code: `{'critical': 'CRITICAL MATCH', 'high': 'HIGH MATCH', 'medium': 'MEDIUM MATCH', 'partial': 'PARTIAL MATCH', 'weak_signal': 'WEAK SIGNAL', 'no_match': 'NO MATCH'}` (app/interface/report_view.py:12)
- [ ] class-level `_CRIME_INDICATOR_LABEL` exists in code but not in UML. UML: `—` · code: `{'counterparty_unnamed': 'Money from unnamed counterparty', 'gift_or_inheritance_unnamed': 'Gift or inheritance from unnamed person', 'source_contradicts_occupa…` (app/interface/report_view.py:12)
- [ ] class-level `_CRIME_SECTION_TITLE` exists in code but not in UML. UML: `—` · code: `'Crime - known patterns for his industry'` (app/interface/report_view.py:12)
- [ ] `_field_name()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:149` (app/interface/report_view.py:149)
- [ ] `_field_value()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:152` (app/interface/report_view.py:152)
- [ ] `_summary_value()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:252` (app/interface/report_view.py:252)
- [ ] `format_assessment_list()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:342` (app/interface/report_view.py:342)
- [ ] `format_onboarding()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:301` (app/interface/report_view.py:301)
- [ ] `format_verdict_report()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:97` (app/interface/report_view.py:97)
- [ ] `show_document_summary()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:266` (app/interface/report_view.py:266)

**`ResponseCache`**

- [ ] class-level `RAW_KIND` exists in code but not in UML. UML: `—` · code: `str = 'forecasting'` (app/ai/response_cache.py:13)
- [ ] `__path()` exists in code but not in UML. UML: `—` · code: `app/ai/response_cache.py:85` (app/ai/response_cache.py:85)
- [ ] `__read()` exists in code but not in UML. UML: `—` · code: `app/ai/response_cache.py:88` (app/ai/response_cache.py:88)
- [ ] `key()` exists in code but not in UML. UML: `—` · code: `app/ai/response_cache.py:29` (app/ai/response_cache.py:29)
- [ ] `path_for()` exists in code but not in UML. UML: `—` · code: `app/ai/response_cache.py:55` (app/ai/response_cache.py:55)

**`RiskAnalysis`**

- [ ] `_best_honest_jump()` exists in code but not in UML. UML: `—` · code: `app/logic/risk_analysis.py:48` (app/logic/risk_analysis.py:48)

**`Verdict`**

- [ ] `__explanation` exists in code but not in UML. UML: `—` · code: `dict = {}` (app/model/verdict.py:42)
- [ ] class-level `CHECK_GROUPS` exists in code but not in UML. UML: `—` · code: `dict[str, str] = {'benchmark': 'benchmark', 'forecast': 'forecast', 'crime': 'crime', 'documents': 'document_findings'}` (app/model/verdict.py:6)
- [ ] class-level `EXPLANATION_KEYS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('name', 'assessed_on', 'policy_version', 'verdict_label', 'summary', 'reasons', 'agreement', 'types', 'documents', 'clean', 'evidence')` (app/model/verdict.py:6)
- [ ] class-level `SEVERITY` exists in code but not in UML. UML: `—` · code: `dict[str, int] = {'PASSED': 0, 'MANUAL_REVIEW': 1, 'RISKY': 2, 'SERIOUS_RISK': 3}` (app/model/verdict.py:6)
- [ ] @property `explanation` in code is not shown in UML. UML: `—` · code: `getter + setter` (app/model/verdict.py:6)
- [ ] @property `not_run` in code is not shown in UML. UML: `—` · code: `getter` (app/model/verdict.py:6)
- [ ] @property `notes` in code is not shown in UML. UML: `—` · code: `getter` (app/model/verdict.py:6)
- [ ] `details()` exists in code but not in UML. UML: `—` · code: `app/model/verdict.py:121` (app/model/verdict.py:121)

**`VerdictEngine`**

- [ ] `__policy` exists in code but not in UML. UML: `—` · code: `dict = self.__config.policy` (app/logic/verdict_engine.py:52)
- [ ] class-level `ORIGINAL_BENCHMARK` exists in code but not in UML. UML: `—` · code: `['TOTAL_WEALTH', 'LIQUIDITY', 'COMPOSITION_PROPERTY', 'COMPOSITION_EQUITIES', 'COMPOSITION_BUSINESS', 'COMPOSITION_CASH', 'VELOCITY', 'COUNTERPARTIES', 'JURISDI…` (app/logic/verdict_engine.py:15)
- [ ] class-level `_ROUTINE_NOTES` exists in code but not in UML. UML: `—` · code: `('converted to', 'renumbered', 'kept first')` (app/logic/verdict_engine.py:15)
- [ ] `_benchmark_items()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:471` (app/logic/verdict_engine.py:471)
- [ ] `_check()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:66` (app/logic/verdict_engine.py:66)
- [ ] `_documents()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:161` (app/logic/verdict_engine.py:161)
- [ ] `_feature()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:57` (app/logic/verdict_engine.py:57)
- [ ] `_feature_checks()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:61` (app/logic/verdict_engine.py:61)
- [ ] `_is_pep()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:71` (app/logic/verdict_engine.py:71)
- [ ] `_items()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:466` (app/logic/verdict_engine.py:466)
- [ ] `features()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:54` (app/logic/verdict_engine.py:54)

**`WebApp`**

- [ ] class-level `ASSET_FIELDS` exists in code but not in UML. UML: `—` · code: `[('asset_type', 'Asset (e.g. Property - Condo)', 'text'), ('country', 'Country', 'text'), ('year_acquired', 'Year bought', 'int'), ('price_paid', 'Price paid (S…` (app/interface/web_app.py:27)
- [ ] class-level `CLAIM_FIELDS` exists in code but not in UML. UML: `—` · code: `[('declared_net_worth', 'Declared net worth (SGD)', 'money'), ('expected_aum', 'Expected assets to be managed by the bank (SGD)', 'money'), ('pep_status', 'PEP …` (app/interface/web_app.py:27)
- [ ] class-level `CLIENT_FIELDS` exists in code but not in UML. UML: `—` · code: `[('name', 'Full name', 'text'), ('nationality', 'Nationality', 'text'), ('country_of_residence', 'Country of residence', 'text'), ('age', 'Age', 'int')]` (app/interface/web_app.py:27)
- [ ] class-level `COMPOSITION_FIELDS` exists in code but not in UML. UML: `—` · code: `[('property', 'Property (%)', 'percent'), ('listed_equities', 'Listed equities (%)', 'percent'), ('private_business', 'Private business (%)', 'percent'), ('cash…` (app/interface/web_app.py:27)
- [ ] class-level `JOB_FIELDS` exists in code but not in UML. UML: `—` · code: `[('start_year', 'Start year', 'int'), ('end_year', 'End year (blank for the current job)', 'int'), ('occupation', 'Job title', 'text'), ('seniority', 'Seniority…` (app/interface/web_app.py:27)
- [ ] class-level `MAX_UPLOAD_BYTES` exists in code but not in UML. UML: `—` · code: `int = 40 * 1024 * 1024` (app/interface/web_app.py:27)
- [ ] class-level `PAYMENT_OPTIONS` exists in code but not in UML. UML: `—` · code: `['cash', 'loan', 'asset_sale']` (app/interface/web_app.py:27)
- [ ] class-level `SECTIONS` exists in code but not in UML. UML: `—` · code: `[('client', 'Client', CLIENT_FIELDS, 'dict'), ('jobs', 'Career history (include the current job and leave its end year blank)', JOB_FIELDS, 'list'), ('assets', …` (app/interface/web_app.py:27)
- [ ] class-level `SOW_FIELDS` exists in code but not in UML. UML: `—` · code: `[('sow_declaration', 'Declaration (at least 50 characters)', 'textarea')]` (app/interface/web_app.py:27)
- [ ] `__crime_result_layout()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:613` (app/interface/web_app.py:613)
- [ ] `__typology_layout()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:620` (app/interface/web_app.py:620)
- [ ] `_documents_on_save()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:648` (app/interface/web_app.py:648)
- [ ] `_is_stored_document()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:464` (app/interface/web_app.py:464)
- [ ] `_run_assessment_job()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:571` (app/interface/web_app.py:571)
- [ ] `_same_entry()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:413` (app/interface/web_app.py:413)
- [ ] `_steps()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:920` (app/interface/web_app.py:920)
- [ ] `autofill_form()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:494` (app/interface/web_app.py:494)
- [ ] `build_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:217` (app/interface/web_app.py:217)
- [ ] `check_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:388` (app/interface/web_app.py:388)
- [ ] `extracted_to_values()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:396` (app/interface/web_app.py:396)
- [ ] `fill_blanks()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:423` (app/interface/web_app.py:423)
- [ ] `flash_ai_unavailable()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:554` (app/interface/web_app.py:554)
- [ ] `flash_rate_limit_error()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:557` (app/interface/web_app.py:557)
- [ ] `flash_unexpected_error()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:560` (app/interface/web_app.py:560)
- [ ] `flask()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:122` (app/interface/web_app.py:122)
- [ ] `get_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:528` (app/interface/web_app.py:528)
- [ ] `handle_404()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:910` (app/interface/web_app.py:910)
- [ ] `handle_exception()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:913` (app/interface/web_app.py:913)
- [ ] `page_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:533` (app/interface/web_app.py:533)
- [ ] `pending_documents()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:468` (app/interface/web_app.py:468)
- [ ] `read_amount()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:207` (app/interface/web_app.py:207)
- [ ] `read_year()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:199` (app/interface/web_app.py:199)
- [ ] `run()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:126` (app/interface/web_app.py:126)
- [ ] `save_form_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:543` (app/interface/web_app.py:543)
- [ ] `show_form()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:563` (app/interface/web_app.py:563)
- [ ] `show_report()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:624` (app/interface/web_app.py:624)
- [ ] `store_uploads()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:474` (app/interface/web_app.py:474)
- [ ] `to_text()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:141` (app/interface/web_app.py:141)
- [ ] `today()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:130` (app/interface/web_app.py:130)
- [ ] `trim()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:133` (app/interface/web_app.py:133)
- [ ] `values_from_form()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:181` (app/interface/web_app.py:181)
- [ ] `values_from_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:156` (app/interface/web_app.py:156)

## Stage 6: Minor: default and starting values (90)

A parameter default the UML leaves out, or an attribute whose starting value differs.

How to fix: **UML:** add or correct the `= value`. Where the code is computed, decide by hand. For the `= None` pattern, the team can agree once on whether parts created in `__init__` are shown as `= None` or without a value. Do it last.

### Benchmark (1)

**`Benchmark`**

- [ ] `__config` starts with a different value. UML: `None` · code: `Config(self._policy, {})` (app/logic/benchmark.py:53) *(pattern: UML writes `= None` for a part that `__init__` creates)*

### Crime Scan (9)

**`CrimeScan`**

- [ ] `__indicators` starts with a different value. UML: `[]` · code: `[GiftOrInheritanceUnnamed(self._policy), CounterpartyUnnamed(self._policy), SourceContradictsOccupation(self._policy), UnvaluedSource(self._policy), RelatedPart…` (app/logic/crime_scan.py:104) *(computed in code: check by hand)*

**`MatchResult`**

- [ ] `__typology` starts with a different value. UML: `None` · code: `Typology()` (app/model/match_result.py:20) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__core_fired` starts with a different value. UML: `[]` · code: `MatchResult.__signs('core', core_fired, self.__typology.core_indicators())` (app/model/match_result.py:21) *(computed in code: check by hand)*

**`ResearchReport`**

- [ ] `__report_id` starts with a different value. UML: `""` · code: `ResearchReport.__text('report_id', report_id)` (app/model/research_report.py:17) *(computed in code: check by hand)*
- [ ] `__url` starts with a different value. UML: `""` · code: `ResearchReport.__text('url', url or '')` (app/model/research_report.py:18) *(computed in code: check by hand)*
- [ ] `__excerpts` starts with a different value. UML: `[]` · code: `[str(excerpt) for excerpt in ResearchReport.__list('excerpts', excerpts)]` (app/model/research_report.py:19) *(computed in code: check by hand)*

**`Typology`**

- [ ] `__typology_id` starts with a different value. UML: `""` · code: `Typology.__text('typology_id', typology_id)` (app/model/typology.py:17) *(computed in code: check by hand)*
- [ ] `__name` starts with a different value. UML: `""` · code: `Typology.__text('name', name)` (app/model/typology.py:18) *(computed in code: check by hand)*
- [ ] `__indicators` starts with a different value. UML: `[]` · code: `[Typology.__indicator(indicator) for indicator in Typology.__list('indicators', indicators)]` (app/model/typology.py:19) *(computed in code: check by hand)*

### Data (13)

**`CloudSync`**

- [ ] `__init__` parameter `local` has a default in code that UML does not show. UML: `—` · code: `None` (app/data/cloud_sync.py:22)
- [ ] `__init__` parameter `remote` has a default in code that UML does not show. UML: `—` · code: `None` (app/data/cloud_sync.py:22)

**`ConfigReader`**

- [ ] `__folder` starts with a different value. UML: `"config"` · code: `os.path.join(ROOT_DIR, 'config')` (app/data/config_reader.py:21) *(computed in code: check by hand)*

**`DatabaseRepository`**

- [ ] `_key_field` starts with a different value. UML: `"client_ref"` · code: `""` (app/data/database_repository.py:20)
- [ ] `__init__` parameter `collection_name` has a default in code that UML does not show. UML: `—` · code: `''` (app/data/database_repository.py:17)
- [ ] `__init__` parameter `key_field` has a default in code that UML does not show. UML: `—` · code: `''` (app/data/database_repository.py:17)
- [ ] `__init__` parameter `uri` has a default in code that UML does not show. UML: `—` · code: `''` (app/data/database_repository.py:17)

**`JsonRepository`**

- [ ] `_key_field` starts with a different value. UML: `"client_ref"` · code: `""` (app/data/json_repository.py:24)
- [ ] `__init__` parameter `path` has a default in code that UML does not show. UML: `—` · code: `''` (app/data/json_repository.py:21)
- [ ] `__init__` parameter `key_field` has a default in code that UML does not show. UML: `—` · code: `''` (app/data/json_repository.py:21)

**`MongoRepository`**

- [ ] `__init__` parameter `collection_name` has a default in code that UML does not show. UML: `—` · code: `''` (app/data/mongo_repository.py:21)
- [ ] `__init__` parameter `key_field` has a default in code that UML does not show. UML: `—` · code: `''` (app/data/mongo_repository.py:21)
- [ ] `__init__` parameter `uri` has a default in code that UML does not show. UML: `—` · code: `''` (app/data/mongo_repository.py:21)

### Document Evidence (3)

**`DocumentRecordBuilder`**

- [ ] `__policy` starts with a different value. UML: `{}` · code: `self.__config.policy` (app/logic/document_record_builder.py:27)

**`DocumentStore`**

- [ ] `__folder` starts with a different value. UML: `"data/documents"` · code: `folder if os.path.isabs(folder) else os.path.join(root, folder)` (app/data/document_store.py:24) *(computed in code: check by hand)*
- [ ] `__reader_factory` starts with a different value. UML: `None` · code: `DocumentReaderFactory()` (app/data/document_store.py:25) *(pattern: UML writes `= None` for a part that `__init__` creates)*

### Forecast (18)

**`AssetPath`**

- [ ] `__market_model` starts with a different value. UML: `None` · code: `MarketModel()` (app/logic/asset_path.py:17) *(pattern: UML writes `= None` for a part that `__init__` creates)*

**`Forecast`**

- [ ] `__market_model` starts with a different value. UML: `None` · code: `MarketModel()` (app/logic/forecast.py:31) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__future_paths` starts with a different value. UML: `None` · code: `FuturePaths(self.__market_model, {}, self._policy)` (app/logic/forecast.py:32) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__assessor` starts with a different value. UML: `None` · code: `OnboardingAssessor(self.__future_paths, self._policy, self.__config)` (app/logic/forecast.py:33) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__pay_calibrator` starts with a different value. UML: `None` · code: `PayCalibrator(self.__future_paths.career_savings(), self._policy)` (app/logic/forecast.py:34) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__config` starts with a different value. UML: `None` · code: `Config(self._policy, {})` (app/logic/forecast.py:29) *(pattern: UML writes `= None` for a part that `__init__` creates)*

**`FuturePaths`**

- [ ] `__career_savings` starts with a different value. UML: `None` · code: `CareerSavings(earnings)` (app/logic/future_paths.py:26) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__asset_path` starts with a different value. UML: `None` · code: `AssetPath(self.__market_model, earnings.get('assets'))` (app/logic/future_paths.py:27) *(pattern: UML writes `= None` for a part that `__init__` creates)*

**`MarketModel`**

- [ ] `__history` starts with a different value. UML: `{}` · code: `{market_id: {row['year']: row['change_pct'] for row in one['history']} for market_id, one in series.items()}` (app/logic/market_model.py:19) *(computed in code: check by hand)*
- [ ] `__outlook` starts with a different value. UML: `{}` · code: `{market_id: {row['year']: {s: row[s] for s in MarketModel.SCENARIOS} for row in one['outlook']} for market_id, one in series.items()}` (app/logic/market_model.py:22) *(computed in code: check by hand)*

**`OnboardingAssessor`**

- [ ] `__future_paths` starts with a different value. UML: `None` · code: `FuturePaths()` (app/logic/onboarding_assessor.py:22) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__config` starts with a different value. UML: `None` · code: `Config()` (app/logic/onboarding_assessor.py:24) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__init__` parameter `future_paths` has a default in code that UML does not show. UML: `—` · code: `None` (app/logic/onboarding_assessor.py:20)
- [ ] `__init__` parameter `policy` has a default in code that UML does not show. UML: `—` · code: `None` (app/logic/onboarding_assessor.py:20)
- [ ] `__init__` parameter `config` has a default in code that UML does not show. UML: `—` · code: `None` (app/logic/onboarding_assessor.py:20)

**`PayCalibrator`**

- [ ] `__career_savings` starts with a different value. UML: `None` · code: `CareerSavings()` (app/logic/pay_calibrator.py:18) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__init__` parameter `career_savings` has a default in code that UML does not show. UML: `—` · code: `None` (app/logic/pay_calibrator.py:17)
- [ ] `__init__` parameter `policy` has a default in code that UML does not show. UML: `—` · code: `None` (app/logic/pay_calibrator.py:17)

### Shared core (46)

**`App`**

- [ ] `__config` starts with a different value. UML: `None` · code: `Config(self.__config_reader.read('policy'), self.__config_reader.read('vocabulary'))` (app/application/app.py:74) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__ui` starts with a different value. UML: `None` · code: `ConsoleUI()` (app/application/app.py:102) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__report_view` starts with a different value. UML: `None` · code: `ReportView(self.__ui)` (app/application/app.py:103) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__client_form` starts with a different value. UML: `None` · code: `ClientForm(self.__ui, self.__report_view)` (app/application/app.py:104) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__case_builder` starts with a different value. UML: `None` · code: `CaseBuilder(self.__ui, schema)` (app/application/app.py:106) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__case_files` starts with a different value. UML: `None` · code: `CaseFiles(os.path.join(root, 'data', 'sample'))` (app/application/app.py:84) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__clients` starts with a different value. UML: `None` · code: `ClientRepository(os.path.join(database_dir, 'sow_cases.json'))` (app/application/app.py:78) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__assessments` starts with a different value. UML: `None` · code: `AssessmentRepository(os.path.join(database_dir, 'ai_assessments.json'))` (app/application/app.py:79) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__runner` starts with a different value. UML: `None` · code: `self.__create_runner(policy)` (app/application/app.py:99)
- [ ] `__documents` starts with a different value. UML: `None` · code: `DocumentStore(os.path.join(data_dir, 'documents'), root=os.path.dirname(data_dir))` (app/application/app.py:82) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__document_ai` starts with a different value. UML: `None` · code: `self.__create_document_ai()` (app/application/app.py:98)
- [ ] `__response_cache` starts with a different value. UML: `None` · code: `ResponseCache(cache_folder if os.path.isabs(cache_folder) else os.path.join(root, cache_folder))` (app/application/app.py:95) *(pattern: UML writes `= None` for a part that `__init__` creates)*

**`AssessmentRunner`**

- [ ] `__config` starts with a different value. UML: `None` · code: `Config()` (app/application/assessment_runner.py:64) *(pattern: UML writes `= None` for a part that `__init__` creates)*

**`CaseBuilder`**

- [ ] `__ui` starts with a different value. UML: `None` · code: `ConsoleUI()` (app/interface/case_builder.py:19) *(pattern: UML writes `= None` for a part that `__init__` creates)*

**`CaseTimeline`**

- [ ] `__forecast_years` starts with a different value. UML: `4` · code: `FORECAST_YEARS` (app/logic/case_timeline.py:13)

**`Claims`**

- [ ] `__pep_status` starts with a different value. UML: `"no"` · code: `""` (app/model/claims.py:22)

**`ClientForm`**

- [ ] `__ui` starts with a different value. UML: `None` · code: `ConsoleUI()` (app/interface/client_form.py:37) *(pattern: UML writes `= None` for a part that `__init__` creates)*

**`ClientProfile`**

- [ ] `__init__` parameter `name` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/client_profile.py:10)
- [ ] `__init__` parameter `nationality` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/client_profile.py:10)

**`ClientRecord`**

- [ ] `__profile` starts with a different value. UML: `None` · code: `ClientProfile(name, nationality, country_of_residence, age)` (app/model/client_record.py:31) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__init__` parameter `client_ref` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/client_record.py:28)
- [ ] `__init__` parameter `name` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/client_record.py:28)
- [ ] `__init__` parameter `nationality` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/client_record.py:28)
- [ ] `__init__` parameter `current_date` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/client_record.py:28)

**`Config`**

- [ ] `__init__` parameter `policy` has a default in code that UML does not show. UML: `—` · code: `None` (app/model/config.py:11)
- [ ] `__init__` parameter `vocabulary` has a default in code that UML does not show. UML: `—` · code: `None` (app/model/config.py:11)

**`ConsoleUI`**

- [ ] `__read` starts with a different value. UML: `input` · code: `read if read is not None else lambda question: input(question)` (app/interface/console_ui.py:36) *(computed in code: check by hand)*
- [ ] `__write` starts with a different value. UML: `print` · code: `write if write is not None else lambda text: print(text)` (app/interface/console_ui.py:37) *(computed in code: check by hand)*
- [ ] `show` parameter `text` has a default in code that UML does not show. UML: `—` · code: `''` (app/interface/console_ui.py:159)
- [ ] `show_ai_unavailable` parameter `feature` has a default in code that UML does not show. UML: `—` · code: `'Assessment'` (app/interface/console_ui.py:67)

**`Investment`**

- [ ] `__year_acquired` starts with a different value. UML: `0` · code: `None` (app/model/investment.py:17)
- [ ] `__current_declared_value` starts with a different value. UML: `0.0` · code: `None` (app/model/investment.py:19)
- [ ] `__income_produced` starts with a different value. UML: `0.0` · code: `None` (app/model/investment.py:20)

**`Job`**

- [ ] `__start_year` starts with a different value. UML: `0` · code: `None` (app/model/job.py:14)

**`RateLimiter`**

- [ ] `__cooldown_seconds` starts with a different value. UML: `60` · code: `int(settings.get('cooldown_seconds', RateLimiter.DEFAULT_COOLDOWN_SECONDS))` (app/interface/rate_limiter.py:18) *(computed in code: check by hand)*

**`ReportView`**

- [ ] `__ui` starts with a different value. UML: `None` · code: `ConsoleUI()` (app/interface/report_view.py:46) *(pattern: UML writes `= None` for a part that `__init__` creates)*

**`ResponseCache`**

- [ ] `__folder` starts with a different value. UML: `"data/cache"` · code: `folder if os.path.isabs(folder) else os.path.join(ROOT_DIR, folder)` (app/ai/response_cache.py:27) *(computed in code: check by hand)*

**`Verdict`**

- [ ] `__outcome` starts with a different value. UML: `""` · code: `"MANUAL_REVIEW"` (app/model/verdict.py:35)
- [ ] `__init__` parameter `assessment_id` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/verdict.py:28)
- [ ] `__init__` parameter `client_ref` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/verdict.py:28)
- [ ] `__init__` parameter `assessed_at` has a default in code that UML does not show. UML: `—` · code: `''` (app/model/verdict.py:28)
- [ ] `__init__` parameter `outcome` has a default in code that UML does not show. UML: `—` · code: `'MANUAL_REVIEW'` (app/model/verdict.py:28)

**`VerdictEngine`**

- [ ] `__config` starts with a different value. UML: `None` · code: `Config()` (app/logic/verdict_engine.py:51) *(pattern: UML writes `= None` for a part that `__init__` creates)*
- [ ] `__init__` parameter `features` has a default in code that UML does not show. UML: `—` · code: `None` (app/logic/verdict_engine.py:49)
- [ ] `__init__` parameter `config` has a default in code that UML does not show. UML: `—` · code: `None` (app/logic/verdict_engine.py:49)

**`WebApp`**

- [ ] `__flask` starts with a different value. UML: `Flask(__name__)` · code: `flask` (app/interface/web_app.py:119)

## Stage 7: Relationships (43)

105 of 114 UML arrows are confirmed in the code. The script and the independent reviewer agreed on every verdict below.

How to fix: mostly **UML** (redraw an arrow, change a verb or multiplicity, add missing arrows). Where an arrow shows a model class but the code passes a plain `dict`, the team has to decide: either the diagram drops the arrow, or the code starts using the model class (a bigger change).

### Wrong kind of arrow (4)

- [ ] `App *-- "1" CaseReader`: only uses it in methods, does not store it (dependency) (app/application/app.py:253 (used in method in read_case))
- [ ] `App ..> ConfigReader : creates`: stores it in an attribute (association/composition, not a passing dependency) (app/application/app.py:73 self.__config_reader = ConfigReader(os.path.join(root, 'config')))
- [ ] `FuturePaths ..> MarketModel : uses`: stores it in an attribute (association/composition, not a passing dependency) (app/logic/future_paths.py:24 self.__market_model = market_model or MarketModel())
- [ ] `WebApp -- RateLimiter : checks with`: no stored reference, only used inside methods (dependency, not association) (app/interface/web_app.py:823 (gets one from .rate_limiter() in assess_client))

### Wrong multiplicity (2)

- [ ] `App *-- "0..*" CloudSync`: creates and stores it; code always holds exactly 2 (a fixed list) (app/application/app.py:87 self.__cloud_syncs = [CloudSync(self.__clients, MongoRepository(App.CLIENT_COLLECTION, 'client_ref', uri), state_path), CloudSync(self.__asse)
- [ ] `ClientRecord *-- "1" Claims`: creates and stores it; starts as None and is created later, so 0..1 (app/model/client_record.py:36 self.__claims = None)

### No evidence in the code (3)

Most of these show a model class (`ClientRecord`, `Verdict`, `Typology`, `MatchResult`, `Declaration`) where the code actually passes a plain `dict`. `RiskAnalysis ..> Formatter` belongs on its children `Benchmark` and `Forecast` instead (see the missing list).

- [ ] `ConsoleUI ..> Band : uses`: the code never connects these two classes
- [ ] `RiskAnalysis ..> Formatter : uses`: the code never connects these two classes
- [ ] `Typology -- "1..*" ResearchReport : cites`: the code never connects these two classes

### Missing from the UML (33)

Real class-to-class links in the code with no UML line between the two classes. *Constant only* means the class just reads another class's constant; the team can decide to leave those out.

- [ ] add `AssessmentRunner *-- "1" CaseReader`: creates and keeps one (app/application/assessment_runner.py:70)
- [ ] add `AssessmentRunner o-- "1" DocumentStore`: stores the one App hands in (app/application/assessment_runner.py:67)
- [ ] add `AssessmentRunner o-- "1" ResponseCache`: stores the one App hands in (app/application/assessment_runner.py:68)
- [ ] add `App ..> CaseTimeline : uses`: reads CaseTimeline.FORECAST_YEARS (constant only) (app/application/app.py:517)
- [ ] add `App ..> Check : creates`: Check.from_dict(...) (app/application/app.py:559)
- [ ] add `App ..> ReviewStatus : uses`: record.review_status.update(...) / to_dict() (app/application/app.py:568) *(found by the reviewer)*
- [ ] add `VerdictEngine ..> Formatter : uses`: Formatter calls (app/logic/verdict_engine.py:242)
- [ ] add `VerdictEngine ..> FuturePaths : uses`: reads FuturePaths.BASELINE_TYPE (constant only) (app/logic/verdict_engine.py:87)
- [ ] add `VerdictEngine ..> CrimeScan : uses`: reads CrimeScan.SIGN_THEMES / SIGN_LABELS / FULL_MATCH / MATCH_LABELS (design smell: the engine is meant to treat every RiskAnalysis alike) (app/logic/verdict_engine.py:139) *(found by the reviewer)*
- [ ] add `VerdictEngine ..> Benchmark : uses`: reads Benchmark.BENCHMARK_LABELS (constant only) (app/logic/verdict_engine.py:470) *(found by the reviewer)*
- [ ] add `VerdictEngine ..> Forecast : calls`: calls honest_numbers(), which only Forecast has, through the RiskAnalysis list (app/logic/verdict_engine.py:226) *(found by the reviewer)*
- [ ] add `Benchmark ..> Formatter : uses`: Formatter calls (the UML puts this on RiskAnalysis, which never uses Formatter) (app/logic/benchmark.py:7) *(found by the reviewer)*
- [ ] add `Forecast ..> Formatter : uses`: Formatter calls (the UML puts this on RiskAnalysis, which never uses Formatter) (app/logic/forecast.py:5) *(found by the reviewer)*
- [ ] add `Benchmark ..> CaseTimeline : creates`: CaseTimeline(...) in a method (app/logic/benchmark.py:323)
- [ ] add `Forecast ..> CareerSavings : passes on`: gets it from FuturePaths and hands it to PayCalibrator (app/logic/forecast.py:34)
- [ ] add `Forecast ..> AssetPath : uses`: self.__future_paths.asset_path().build(...) (app/logic/forecast.py:145) *(found by the script)*
- [ ] add `DocumentEvidence *-- "1" CaseReader`: creates and keeps one (app/logic/document_evidence.py:20)
- [ ] add `DocumentRecordBuilder o-- "1" Config`: stores the Config App hands in (app/logic/document_record_builder.py:24)
- [ ] add `DocumentRecordBuilder ..> CaseReader : uses`: reads CaseReader constants (COMPOSITION_KEYS) (app/logic/document_record_builder.py:76)
- [ ] add `Indicator ..> ClaimedSource : uses`: all four sign classes call methods on declaration.sources() (app/logic/indicator.py:31)
- [ ] add `AssetPath ..> CaseTimeline : creates`: CaseTimeline(...) in a method (app/logic/asset_path.py:25)
- [ ] add `PayCalibrator ..> CaseTimeline : creates`: CaseTimeline(...) in a method (app/logic/pay_calibrator.py:34)
- [ ] add `PayCalibrator ..> MarketModel : uses`: reads MarketModel.SCENARIOS (constant only) (app/logic/pay_calibrator.py:56)
- [ ] add `OnboardingAssessor ..> CaseTimeline : creates`: CaseTimeline(...) in a method (app/logic/onboarding_assessor.py:88)
- [ ] add `OnboardingAssessor ..> Verdict : uses`: reads Verdict.SEVERITY (constant only) (app/logic/onboarding_assessor.py:160)
- [ ] add `OnboardingAssessor ..> AssetPath : uses`: future_paths.asset_path().income_up_to(...) (app/logic/onboarding_assessor.py:78)
- [ ] add `ClientForm o-- "1" ReportView`: stores the ReportView App hands in (app/interface/client_form.py:33)
- [ ] add `CaseBuilder ..> ClientForm : uses`: reads ClientForm.PAYMENT_METHODS (constant only) (app/interface/case_builder.py:150)
- [ ] add `WebApp ..> ClientForm : uses`: reads ClientForm.PEP_OPTIONS (constant only) (app/interface/web_app.py:97)
- [ ] add `WebApp ..> Repository : uses`: calls on App.clients() / App.assessments() (app/interface/web_app.py:519)
- [ ] add `WebApp ..> DocumentStore : uses`: calls on App.documents() (app/interface/web_app.py:461)
- [ ] add `WebApp ..> DocumentRecordBuilder : uses`: calls on App.record_builder() (app/interface/web_app.py:399)
- [ ] add `CloudSync ..> JsonRepository : uses`: JsonRepository.DATA_DIR as a default argument (constant only) (app/data/cloud_sync.py:23) *(found by the reviewer)*

### main.py note (1)

- [ ] The note on `App` says `caller = with_fallback(openai_caller(OpenAI()), gemini_caller(genai.Client()))` then `App(caller)`, but `main.py:22` is `App(with_fallback(openai_caller(), gemini_caller()))`: no `caller` variable, and the callers take no arguments. Fix in UML.

## Appendix: values shortened with `...` (not checked, 18)

`App.CRITICAL_STEPS`, `AssessmentRunner.STEPS`, `Band.MONEY_IN`, `Band.MONEY_OUT`, `Benchmark.BENCHMARK_LABELS`, `Benchmark.COMPOSITION_RULES`, `BenchmarkAI.ALLOWED_FIELDS`, `CaseFiles.__folder`, `ClientRepository.OLD_ASSET_KEYS`, `CloudSync.__state_path`, `ImageReader.IMAGE_TYPES`, `RelatedPartyTransaction.__KEYWORDS`, `ReportView.FIELD_NAMES`, `ReportView.OUTCOME_LABELS`, `VerdictEngine.MARKS`, `VerdictEngine.REPORT_LEGEND`, `VerdictEngine.THEMES`, `VerdictEngine.VERDICT_LABELS`

