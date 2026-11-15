# UML v4 vs code: differences, staged

Checked code at commit `00fba40` against `uml/class_diagram_v4.puml`, which is converted from `uml/class_diagram_v4.drawio` and was independently verified as faithful. Every class, attribute, property, constant and method signature was compared by script, so nothing was sampled.

**How to use this file:** work through one stage at a time, and tick `[x]` when an item is fixed. Then re-export the draw.io file, regenerate the `.puml` and re-run the check.

## How this was checked

| Link | How | Result |
|---|---|---|
| draw.io → PlantUML | A round-trip script plus an independent agent with its own parser | **Faithful**: 69 classes, 224 attributes, 393 methods, 114 relationships, 35 multiplicities and the main.py note all identical |
| PlantUML → code: members | Script reads every class with Python's `ast` | Stages 1–6 below |
| PlantUML → code: relationships | Script (static analysis) **and** an independent agent reading the code by hand; every disagreement was settled by re-reading the code | Stage 7 below |

**What was compared:** class presence, kind, package and parent; attribute name, visibility, type and starting value; `{get}` / `{get, set}` properties; «const» name, type and value; method name, visibility, parameters (names, order, types, defaults), return type, «static», abstract; every relationship's kind, direction, verb and multiplicity; class-to-class links in the code that have no UML line; module-level functions (only `app/ai/ai_caller.py`: ✅); the main.py note.

**Not checked (can't be, statically):** method behaviour; 54 values the UML shortens with `...` (listed at the end).

**Area** is the feature area of the class, to help split the work. It is a best guess, so confirm it with the team. Don't change a teammate's files without asking them.

## Overview

| Stage | What | Items | Mostly fixed in |
|---|---|---|---|
| 1 | Structure: classes and inheritance | 0 | Code + UML |
| 2 | Graded code rules: types and `__init__` | 0 | Code |
| 3 | Same member, different details | 0 | Decide per item |
| 4 | In UML, missing in code | 0 | Decide per item |
| 5 | In code, missing from UML | 471 | UML |
| 6 | Minor: default and starting values | 0 | UML |
| 7 | Relationships (arrows, verbs, multiplicities) and the main.py note | 0 | Mostly UML |
| | **Total** | **471** | |

Pairs where only the underscores differ (`__x` in UML, `_x` in code) are merged into one item in stage 3, so the total is lower than the raw count of differences.

## Stage 1: Structure: classes and inheritance (0)

Fix first, because every later stage depends on the class names being right.

How to fix: **Code:** rename `Feature` to `RiskAnalysis` (file, class, imports, tests). **UML:** change `list[Feature]` to `list[RiskAnalysis]` in `AssessmentRunner` and `VerdictEngine`, and add `CaseFiles` and `CaseTimeline`, which exist in code.

**Done.** Nothing left in this stage.

## Stage 2: Graded code rules: types and `__init__` (0)

CLAUDE.md §1 says every attribute has a type and is created in `__init__`. These are code fixes; the UML is already right.

How to fix: **Code:** add the missing type hints, and create every attribute in `__init__` with a default.

**Done.** Nothing left in this stage.

## Stage 3: Same member, different details (0)

Both sides have it, but the signature, type, visibility, static or abstract marker, or constant value differs.

How to fix: Decide per item. If the code is the better design, update the UML. If the code breaks the design, fix the code.

**Done.** Nothing left in this stage.

## Stage 4: In UML, missing in code (0)

The diagram promises something the code doesn't have.

How to fix: Either the work was done under another name (then update the UML), or it was dropped (then remove it from the UML or build it).

**Done.** Nothing left in this stage.

## Stage 5: In code, missing from UML (471)

The code grew past the diagram, mostly helper methods and constants.

How to fix: **UML:** add them to the draw.io boxes. If a class gets too big (professor: more than ~10 attributes is a worry), think about splitting it before adding everything.

### Benchmark (12)

**`Benchmark`**

- [ ] class-level `FORECAST_DERIVED` exists in code but not in UML. UML: `—` · code: `('UNEXPLAINED_GAP', 'PEP_STATUS', 'PEER_BENCHMARK')` (app/logic/benchmark.py:14)
- [ ] class-level `LIMITS` exists in code but not in UML. UML: `—` · code: `{'total_wealth': 3, 'liquidity': 2, 'composition': 40, 'velocity': 2, 'counterparties': 1, 'jurisdiction': 1}` (app/logic/benchmark.py:14)
- [ ] class-level `NAME` exists in code but not in UML. UML: `—` · code: `str = 'benchmark'` (app/logic/benchmark.py:14)
- [ ] class-level `_COMPOSITION_PARTS` exists in code but not in UML. UML: `—` · code: `[('COMPOSITION_PROPERTY', 'property', 'expected_property', 'Property'), ('COMPOSITION_EQUITIES', 'listed_equities', 'expected_listed_equities', 'Listed equities…` (app/logic/benchmark.py:14)
- [ ] `_benchmark_checks()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:229` (app/logic/benchmark.py:229)
- [ ] `_best_market_stretch()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:202` (app/logic/benchmark.py:202)
- [ ] `_clean_country()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:119` (app/logic/benchmark.py:119)
- [ ] `_market_growth()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:195` (app/logic/benchmark.py:195)
- [ ] `_market_history()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:70` (app/logic/benchmark.py:70)
- [ ] `_run_rules()` exists in code but not in UML. UML: `—` · code: `app/logic/benchmark.py:144` (app/logic/benchmark.py:144)

**`BenchmarkAI`**

- [ ] `_cache_payload()` exists in code but not in UML. UML: `—` · code: `app/ai/benchmark_ai.py:36` (app/ai/benchmark_ai.py:36)
- [ ] `_fill_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/benchmark_ai.py:30` (app/ai/benchmark_ai.py:30)

### Crime Scan (77)

**`CrimeScan`**

- [ ] `__warnings` exists in code but not in UML. UML: `—` · code: `list[str] = []` (app/logic/crime_scan.py:108)
- [ ] class-level `FULL_MATCH` exists in code but not in UML. UML: `—` · code: `('critical', 'high', 'medium')` (app/logic/crime_scan.py:17)
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

### Data (10)

**`AssessmentRepository`**

- [ ] `__old_outcome()` exists in code but not in UML. UML: `—` · code: `app/data/assessment_repository.py:48` (app/data/assessment_repository.py:48)

**`ClientRepository`**

- [ ] `load()` exists in code but not in UML. UML: `—` · code: `app/data/client_repository.py:41` (app/data/client_repository.py:41)

**`ConfigReader`**

- [ ] `__files` exists in code but not in UML. UML: `—` · code: `dict[str, dict] = {}` (app/data/config_reader.py:23)
- [ ] class-level `REQUIRED` exists in code but not in UML. UML: `—` · code: `dict[str, tuple[str, ...]] = {'vocabulary': ('signal_codes', 'document_codes', 'source_types', 'crime_categories'), 'policy': ('policy_version', 'tolerance', 'f…` (app/data/config_reader.py:12)

**`DatabaseRepository`**

- [ ] @property `key_field` in code is not shown in UML. UML: `—` · code: `getter` (app/data/database_repository.py:13)
- [ ] @property `name` in code is not shown in UML. UML: `—` · code: `getter` (app/data/database_repository.py:13)
- [ ] `__require_connection()` exists in code but not in UML. UML: `—` · code: `app/data/database_repository.py:85` (app/data/database_repository.py:85)

**`MongoRepository`**

- [ ] class-level `TIMEOUT_MS` exists in code but not in UML. UML: `—` · code: `int = 2000` (app/data/mongo_repository.py:15)
- [ ] `__collection()` exists in code but not in UML. UML: `—` · code: `app/data/mongo_repository.py:67` (app/data/mongo_repository.py:67)

**`Repository`**

- [ ] `__init__()` exists in code but not in UML. UML: `—` · code: `app/data/repository.py:10` (app/data/repository.py:10)

### Document Evidence (30)

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

### Forecast (78)

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
- [ ] `__check_market_series()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:357` (app/ai/forecast_ai.py:357)
- [ ] `__check_position_pay()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:377` (app/ai/forecast_ai.py:377)
- [ ] `_add_vocabulary()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:141` (app/ai/forecast_ai.py:141)
- [ ] `_ask()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:733` (app/ai/forecast_ai.py:733)
- [ ] `_build_instructions()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:128` (app/ai/forecast_ai.py:128)
- [ ] `_can_ask()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:80` (app/ai/forecast_ai.py:80)
- [ ] `_career_positions()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:84` (app/ai/forecast_ai.py:84)
- [ ] `_career_years()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:96` (app/ai/forecast_ai.py:96)
- [ ] `_check_type_behaviour()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:667` (app/ai/forecast_ai.py:667)
- [ ] `_check_type_reactions()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:716` (app/ai/forecast_ai.py:716)
- [ ] `_client_facts()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:196` (app/ai/forecast_ai.py:196)
- [ ] `_crime_categories()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:835` (app/ai/forecast_ai.py:835)
- [ ] `_current_year()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:92` (app/ai/forecast_ai.py:92)
- [ ] `_empty_result()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:727` (app/ai/forecast_ai.py:727)
- [ ] `_extract_json()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:167` (app/ai/forecast_ai.py:167)
- [ ] `_fallback_asset_model()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:436` (app/ai/forecast_ai.py:436)
- [ ] `_fill_placeholders()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:119` (app/ai/forecast_ai.py:119)
- [ ] `_follows_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:157` (app/ai/forecast_ai.py:157)
- [ ] `_future_years()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:107` (app/ai/forecast_ai.py:107)
- [ ] `_link_typologies()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:448` (app/ai/forecast_ai.py:448)
- [ ] `_load_forecast_prompt()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:114` (app/ai/forecast_ai.py:114)
- [ ] `_load_forecast_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:151` (app/ai/forecast_ai.py:151)
- [ ] `_looks_like_schema()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:268` (app/ai/forecast_ai.py:268)
- [ ] `_market_changes()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:819` (app/ai/forecast_ai.py:819)
- [ ] `_market_outlooks()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:825` (app/ai/forecast_ai.py:825)
- [ ] `_markets_brief()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:814` (app/ai/forecast_ai.py:814)
- [ ] `_parse_reply()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:253` (app/ai/forecast_ai.py:253)
- [ ] `_position_end()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:103` (app/ai/forecast_ai.py:103)
- [ ] `_range_errors()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:219` (app/ai/forecast_ai.py:219)
- [ ] `_read_declaration()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:845` (app/ai/forecast_ai.py:845)
- [ ] `_repair_asset_model()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:412` (app/ai/forecast_ai.py:412)
- [ ] `_repair_person_types()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:485` (app/ai/forecast_ai.py:485)
- [ ] `_repair_type_behaviour()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:627` (app/ai/forecast_ai.py:627)
- [ ] `_repair_type_reactions()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:654` (app/ai/forecast_ai.py:654)
- [ ] `_run_forecast()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:1098` (app/ai/forecast_ai.py:1098)
- [ ] `_settings()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:74` (app/ai/forecast_ai.py:74)
- [ ] `_sort_ranges()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:235` (app/ai/forecast_ai.py:235)
- [ ] `_stopped()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:1086` (app/ai/forecast_ai.py:1086)
- [ ] `_strip_keys()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:181` (app/ai/forecast_ai.py:181)
- [ ] `_top_level_keys()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:263` (app/ai/forecast_ai.py:263)
- [ ] `_types_brief()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:830` (app/ai/forecast_ai.py:830)
- [ ] `_typologies_brief()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:965` (app/ai/forecast_ai.py:965)
- [ ] `_unknown_ids()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:307` (app/ai/forecast_ai.py:307)
- [ ] `_validate_reply()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:273` (app/ai/forecast_ai.py:273)
- [ ] `_vocabulary()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:77` (app/ai/forecast_ai.py:77)
- [ ] `_wrap_free_text()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:190` (app/ai/forecast_ai.py:190)
- [ ] `_years_errors()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:292` (app/ai/forecast_ai.py:292)
- [ ] `_years_text()` exists in code but not in UML. UML: `—` · code: `app/ai/forecast_ai.py:809` (app/ai/forecast_ai.py:809)

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

### Shared core (264)

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

- [ ] `__config_reader` exists in code but not in UML. UML: `—` · code: `ConfigReader = ConfigReader(os.path.join(root, 'config'))` (app/application/app.py:79)
- [ ] `__root` exists in code but not in UML. UML: `—` · code: `str = root` (app/application/app.py:74)
- [ ] `__settings_ok` exists in code but not in UML. UML: `—` · code: `bool = True` (app/application/app.py:80)
- [ ] class-level `ASSESSMENTS_UNAVAILABLE` exists in code but not in UML. UML: `—` · code: `str = "We can't load the saved assessments right now. Please try again later."` (app/application/app.py:44)
- [ ] class-level `ASSESSMENT_COLLECTION` exists in code but not in UML. UML: `—` · code: `str = 'ai_assessments'` (app/application/app.py:44)
- [ ] class-level `CLIENTS_UNAVAILABLE` exists in code but not in UML. UML: `—` · code: `str = "We can't load the client database right now. Please try again later."` (app/application/app.py:44)
- [ ] class-level `CLIENT_COLLECTION` exists in code but not in UML. UML: `—` · code: `str = 'client_cases'` (app/application/app.py:44)
- [ ] class-level `NOISY_LOGGERS` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('httpx', 'httpcore', 'httpx2', 'httpcore2', 'openai', 'urllib3', 'google_genai', 'hpack', 'pymongo')` (app/application/app.py:44)
- [ ] class-level `SETTINGS_UNAVAILABLE` exists in code but not in UML. UML: `—` · code: `str = "The app's settings could not be loaded. Please contact your administrator."` (app/application/app.py:44)
- [ ] @property `config` in code is not shown in UML. UML: `—` · code: `getter` (app/application/app.py:44)
- [ ] `__ai_model()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:629` (app/application/app.py:629)
- [ ] `__configure_logging()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:709` (app/application/app.py:709)
- [ ] `__create_document_ai()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:633` (app/application/app.py:633)
- [ ] `__create_runner()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:639` (app/application/app.py:639)
- [ ] `__crime_declaration_layout()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:371` (app/application/app.py:371)
- [ ] `__crime_result_layout()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:376` (app/application/app.py:376)
- [ ] `__fill_field()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:685` (app/application/app.py:685)
- [ ] `__handle_failure_quietly()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:669` (app/application/app.py:669)
- [ ] `__saved_verdict()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:697` (app/application/app.py:697)
- [ ] `__show_step()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:694` (app/application/app.py:694)
- [ ] `ai_available()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:159` (app/application/app.py:159)
- [ ] `assess()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:297` (app/application/app.py:297)
- [ ] `assessments()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:612` (app/application/app.py:612)
- [ ] `clients()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:609` (app/application/app.py:609)
- [ ] `documents()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:615` (app/application/app.py:615)
- [ ] `forecast_settings()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:146` (app/application/app.py:146)
- [ ] `new_client_ref()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:537` (app/application/app.py:537)
- [ ] `rate_limiter()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:618` (app/application/app.py:618)
- [ ] `read_amount()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:545` (app/application/app.py:545)
- [ ] `read_case()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:292` (app/application/app.py:292)
- [ ] `read_documents()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:524` (app/application/app.py:524)
- [ ] `record_builder()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:533` (app/application/app.py:533)
- [ ] `response_cache()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:621` (app/application/app.py:621)
- [ ] `runner()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:624` (app/application/app.py:624)
- [ ] `save_assessment()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:330` (app/application/app.py:330)
- [ ] `start_web()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:212` (app/application/app.py:212)
- [ ] `steps()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:137` (app/application/app.py:137)
- [ ] `validate_case()` exists in code but not in UML. UML: `—` · code: `app/application/app.py:541` (app/application/app.py:541)

**`AssessmentRunner`**

- [ ] `__benchmark` exists in code but not in UML. UML: `—` · code: `Benchmark = Benchmark(policy, self.__config)` (app/application/assessment_runner.py:82)
- [ ] `__benchmark_ai` exists in code but not in UML. UML: `—` · code: `BenchmarkAI | None = benchmark_ai` (app/application/assessment_runner.py:67)
- [ ] `__case_reader` exists in code but not in UML. UML: `—` · code: `CaseReader = CaseReader()` (app/application/assessment_runner.py:73)
- [ ] `__crime_scan` exists in code but not in UML. UML: `—` · code: `CrimeScan = CrimeScan(policy)` (app/application/assessment_runner.py:74)
- [ ] `__crime_scan_lock` exists in code but not in UML. UML: `—` · code: `threading.Lock = threading.Lock()` (app/application/assessment_runner.py:77)
- [ ] `__document_ai` exists in code but not in UML. UML: `—` · code: `DocumentAI | None = document_ai` (app/application/assessment_runner.py:68)
- [ ] `__document_store` exists in code but not in UML. UML: `—` · code: `DocumentStore | None = document_store` (app/application/assessment_runner.py:70)
- [ ] `__documents` exists in code but not in UML. UML: `—` · code: `DocumentEvidence = DocumentEvidence(policy)` (app/application/assessment_runner.py:81)
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
- [ ] `__composition_from_record()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:163` (app/interface/case_builder.py:163)
- [ ] `__first_filled()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:123` (app/interface/case_builder.py:123)
- [ ] `__payment_method()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:53` (app/interface/case_builder.py:53)
- [ ] `__text_or_ask()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:79` (app/interface/case_builder.py:79)
- [ ] `validate_case()` exists in code but not in UML. UML: `—` · code: `app/interface/case_builder.py:22` (app/interface/case_builder.py:22)

**`CaseReader`**

- [ ] class-level `COMPOSITION_KEYS` exists in code but not in UML. UML: `—` · code: `['property', 'listed_equities', 'private_business', 'cash']` (app/logic/case_reader.py:4)
- [ ] `_read_payment()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:43` (app/logic/case_reader.py:43)
- [ ] `_whole_number()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:241` (app/logic/case_reader.py:241)
- [ ] `_whole_percent()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:210` (app/logic/case_reader.py:210)
- [ ] `benchmark_input()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:216` (app/logic/case_reader.py:216)
- [ ] `crime_scan_input()` exists in code but not in UML. UML: `—` · code: `app/logic/case_reader.py:194` (app/logic/case_reader.py:194)

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
- [ ] class-level `NO_PEP_VALUES` exists in code but not in UML. UML: `—` · code: `tuple[str, ...] = ('none', 'no', 'not a pep', 'n/a', 'na')` (app/model/claims.py:4)
- [ ] `to_dict()` exists in code but not in UML. UML: `—` · code: `app/model/claims.py:127` (app/model/claims.py:127)

**`ClientForm`**

- [ ] `__report_view` exists in code but not in UML. UML: `—` · code: `ReportView = report_view or ReportView(self.__ui)` (app/interface/client_form.py:39)
- [ ] `add_asset_record()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:423` (app/interface/client_form.py:423)
- [ ] `add_career_record()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:380` (app/interface/client_form.py:380)
- [ ] `add_supporting_documents()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:520` (app/interface/client_form.py:520)
- [ ] `ask_after_save()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:341` (app/interface/client_form.py:341)
- [ ] `ask_missing_field()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:307` (app/interface/client_form.py:307)
- [ ] `edit_asset_composition()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:483` (app/interface/client_form.py:483)
- [ ] `edit_client_declarations()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:491` (app/interface/client_form.py:491)
- [ ] `edit_client_profile()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:354` (app/interface/client_form.py:354)
- [ ] `find_existing_client()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:686` (app/interface/client_form.py:686)
- [ ] `get_career_history()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:87` (app/interface/client_form.py:87)
- [ ] `get_client_profile()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:46` (app/interface/client_form.py:46)
- [ ] `get_investments()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:120` (app/interface/client_form.py:120)
- [ ] `get_sow_declaration()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:159` (app/interface/client_form.py:159)
- [ ] `get_supporting_documents()` exists in code but not in UML. UML: `—` · code: `app/interface/client_form.py:163` (app/interface/client_form.py:163)

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
- [ ] `__this_year()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:162` (app/model/client_record.py:162)
- [ ] `__whole()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:327` (app/model/client_record.py:327)
- [ ] `__whole_percent()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:339` (app/model/client_record.py:339)
- [ ] `career_start_year()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:131` (app/model/client_record.py:131)
- [ ] `investments()` exists in code but not in UML. UML: `—` · code: `app/model/client_record.py:85` (app/model/client_record.py:85)

**`Config`**

- [ ] `asset_category()` exists in code but not in UML. UML: `—` · code: `app/model/config.py:32` (app/model/config.py:32)

**`ConsoleUI`**

- [ ] `__width` exists in code but not in UML. UML: `—` · code: `int = len(ConsoleUI.LINE)` (app/interface/console_ui.py:33)
- [ ] class-level `LABEL` exists in code but not in UML. UML: `—` · code: `" '.-&/,()%#0123456789"` (app/interface/console_ui.py:8)
- [ ] `__words_error()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:266` (app/interface/console_ui.py:266)
- [ ] `ask_composition()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:194` (app/interface/console_ui.py:194)
- [ ] `ask_count()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:314` (app/interface/console_ui.py:314)
- [ ] `ask_countries()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:287` (app/interface/console_ui.py:287)
- [ ] `ask_currency()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:187` (app/interface/console_ui.py:187)
- [ ] `ask_document_record_action()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:106` (app/interface/console_ui.py:106)
- [ ] `ask_words()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:271` (app/interface/console_ui.py:271)
- [ ] `keep_count()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:322` (app/interface/console_ui.py:322)
- [ ] `keep_int()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:232` (app/interface/console_ui.py:232)
- [ ] `keep_words()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:278` (app/interface/console_ui.py:278)
- [ ] `read_number()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:336` (app/interface/console_ui.py:336)
- [ ] `read_year()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:353` (app/interface/console_ui.py:353)
- [ ] `show_documents_found()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:95` (app/interface/console_ui.py:95)
- [ ] `show_missing_intro()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:100` (app/interface/console_ui.py:100)
- [ ] `show_unexpected_error()` exists in code but not in UML. UML: `—` · code: `app/interface/console_ui.py:65` (app/interface/console_ui.py:65)

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

- [ ] `__enabled` exists in code but not in UML. UML: `—` · code: `bool = enabled` (app/interface/rate_limiter.py:22)
- [ ] class-level `DEFAULT_COOLDOWN_SECONDS` exists in code but not in UML. UML: `—` · code: `int = 60` (app/interface/rate_limiter.py:6)
- [ ] `reset()` exists in code but not in UML. UML: `—` · code: `app/interface/rate_limiter.py:42` (app/interface/rate_limiter.py:42)

**`ReportView`**

- [ ] class-level `REPORT_WIDTH` exists in code but not in UML. UML: `—` · code: `96` (app/interface/report_view.py:12)
- [ ] class-level `_CRIME_CATEGORY_LABEL` exists in code but not in UML. UML: `—` · code: `{'critical': 'CRITICAL MATCH', 'high': 'HIGH MATCH', 'medium': 'MEDIUM MATCH', 'partial': 'PARTIAL MATCH', 'weak_signal': 'WEAK SIGNAL', 'no_match': 'NO MATCH'}` (app/interface/report_view.py:12)
- [ ] class-level `_CRIME_INDICATOR_LABEL` exists in code but not in UML. UML: `—` · code: `{'counterparty_unnamed': 'Money from unnamed counterparty', 'gift_or_inheritance_unnamed': 'Gift or inheritance from unnamed person', 'source_contradicts_occupa…` (app/interface/report_view.py:12)
- [ ] class-level `_CRIME_SECTION_TITLE` exists in code but not in UML. UML: `—` · code: `'Crime - known patterns for his industry'` (app/interface/report_view.py:12)
- [ ] `_field_name()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:157` (app/interface/report_view.py:157)
- [ ] `_field_value()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:160` (app/interface/report_view.py:160)
- [ ] `_summary_value()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:289` (app/interface/report_view.py:289)
- [ ] `format_assessment_list()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:379` (app/interface/report_view.py:379)
- [ ] `format_onboarding()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:338` (app/interface/report_view.py:338)
- [ ] `format_verdict_report()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:105` (app/interface/report_view.py:105)
- [ ] `show_document_summary()` exists in code but not in UML. UML: `—` · code: `app/interface/report_view.py:303` (app/interface/report_view.py:303)

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
- [ ] `_benchmark_items()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:497` (app/logic/verdict_engine.py:497)
- [ ] `_check()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:66` (app/logic/verdict_engine.py:66)
- [ ] `_documents()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:162` (app/logic/verdict_engine.py:162)
- [ ] `_feature()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:57` (app/logic/verdict_engine.py:57)
- [ ] `_feature_checks()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:61` (app/logic/verdict_engine.py:61)
- [ ] `_is_pep()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:71` (app/logic/verdict_engine.py:71)
- [ ] `_items()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:492` (app/logic/verdict_engine.py:492)
- [ ] `features()` exists in code but not in UML. UML: `—` · code: `app/logic/verdict_engine.py:54` (app/logic/verdict_engine.py:54)

**`WebApp`**

- [ ] class-level `ASSESSMENT_NOT_SAVED` exists in code but not in UML. UML: `—` · code: `str = "This assessment was NOT saved, so it is not in the client's history and the client's outcome was not changed. Please try again later."` (app/interface/web_app.py:28)
- [ ] class-level `ASSET_FIELDS` exists in code but not in UML. UML: `—` · code: `[('asset_type', 'Asset (e.g. Property - Condo)', 'text'), ('country', 'Country', 'text'), ('year_acquired', 'Year bought', 'int'), ('price_paid', 'Price paid (S…` (app/interface/web_app.py:28)
- [ ] class-level `CLAIM_FIELDS` exists in code but not in UML. UML: `—` · code: `[('declared_net_worth', 'Declared net worth (SGD)', 'money'), ('expected_aum', 'Expected assets to be managed by the bank (SGD)', 'money'), ('pep_status', 'PEP …` (app/interface/web_app.py:28)
- [ ] class-level `CLIENT_FIELDS` exists in code but not in UML. UML: `—` · code: `[('name', 'Full name', 'text'), ('nationality', 'Nationality', 'text'), ('country_of_residence', 'Country of residence', 'text'), ('age', 'Age', 'int')]` (app/interface/web_app.py:28)
- [ ] class-level `COMPOSITION_FIELDS` exists in code but not in UML. UML: `—` · code: `[('property', 'Property (%)', 'percent'), ('listed_equities', 'Listed equities (%)', 'percent'), ('private_business', 'Private business (%)', 'percent'), ('cash…` (app/interface/web_app.py:28)
- [ ] class-level `JOB_FIELDS` exists in code but not in UML. UML: `—` · code: `[('start_year', 'Start year', 'int'), ('end_year', 'End year (blank for the current job)', 'int'), ('occupation', 'Job title', 'text'), ('seniority', 'Seniority…` (app/interface/web_app.py:28)
- [ ] class-level `MAX_UPLOAD_BYTES` exists in code but not in UML. UML: `—` · code: `int = 40 * 1024 * 1024` (app/interface/web_app.py:28)
- [ ] class-level `SECTIONS` exists in code but not in UML. UML: `—` · code: `[('client', 'Client', CLIENT_FIELDS, 'dict'), ('jobs', 'Career history (include the current job and leave its end year blank)', JOB_FIELDS, 'list'), ('assets', …` (app/interface/web_app.py:28)
- [ ] class-level `SOW_FIELDS` exists in code but not in UML. UML: `—` · code: `[('sow_declaration', 'Declaration (at least 50 characters)', 'textarea')]` (app/interface/web_app.py:28)
- [ ] `__crime_result_layout()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:621` (app/interface/web_app.py:621)
- [ ] `__typology_layout()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:628` (app/interface/web_app.py:628)
- [ ] `_documents_on_save()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:664` (app/interface/web_app.py:664)
- [ ] `_is_stored_document()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:470` (app/interface/web_app.py:470)
- [ ] `_same_entry()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:419` (app/interface/web_app.py:419)
- [ ] `_steps()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:955` (app/interface/web_app.py:955)
- [ ] `autofill_form()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:500` (app/interface/web_app.py:500)
- [ ] `build_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:223` (app/interface/web_app.py:223)
- [ ] `check_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:394` (app/interface/web_app.py:394)
- [ ] `extracted_to_values()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:402` (app/interface/web_app.py:402)
- [ ] `fill_blanks()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:429` (app/interface/web_app.py:429)
- [ ] `flash_ai_unavailable()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:561` (app/interface/web_app.py:561)
- [ ] `flash_rate_limit_error()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:564` (app/interface/web_app.py:564)
- [ ] `flash_unexpected_error()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:567` (app/interface/web_app.py:567)
- [ ] `flask()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:128` (app/interface/web_app.py:128)
- [ ] `get_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:534` (app/interface/web_app.py:534)
- [ ] `handle_404()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:945` (app/interface/web_app.py:945)
- [ ] `handle_exception()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:948` (app/interface/web_app.py:948)
- [ ] `page_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:539` (app/interface/web_app.py:539)
- [ ] `pending_documents()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:474` (app/interface/web_app.py:474)
- [ ] `read_amount()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:213` (app/interface/web_app.py:213)
- [ ] `read_year()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:205` (app/interface/web_app.py:205)
- [ ] `save_form_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:549` (app/interface/web_app.py:549)
- [ ] `show_form()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:570` (app/interface/web_app.py:570)
- [ ] `show_report()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:632` (app/interface/web_app.py:632)
- [ ] `store_uploads()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:480` (app/interface/web_app.py:480)
- [ ] `to_text()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:147` (app/interface/web_app.py:147)
- [ ] `today()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:136` (app/interface/web_app.py:136)
- [ ] `trim()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:139` (app/interface/web_app.py:139)
- [ ] `values_from_form()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:187` (app/interface/web_app.py:187)
- [ ] `values_from_record()` exists in code but not in UML. UML: `—` · code: `app/interface/web_app.py:162` (app/interface/web_app.py:162)

## Stage 6: Minor: default and starting values (0)

A parameter default the UML leaves out, or an attribute whose starting value differs.

How to fix: **UML:** add or correct the `= value`. Where the code is computed, decide by hand. For the `= None` pattern, the team can agree once on whether parts created in `__init__` are shown as `= None` or without a value. Do it last.

**Done.** Nothing left in this stage.

## Stage 7: Relationships (0)

148 of 150 UML arrows are confirmed in the code by the pattern check (its known blind spots are listed in uml/FOLLOW_UPS.md #44).

How to fix: mostly **UML** (redraw an arrow, change a verb or multiplicity, add missing arrows). Where an arrow shows a model class but the code passes a plain `dict`, the team has to decide: either the diagram drops the arrow, or the code starts using the model class (a bigger change).

### Missing from the UML (0)

Real class-to-class links in the code that the drawing rule says to draw, with no UML line between the two classes.


### Kept without code evidence, by decision (2)

- `Typology -- "1..*" ResearchReport : cites`: linked by report id: a Typology keeps the ids of the ResearchReports it cites (source_ids), not the objects; the link is real in the data, so the diagram keeps it
- `VerdictEngine ..> MatchResult : uses`: checked by hand: __type_patterns reads m.typology, match.category and calls match.fired() on the MatchResult objects in crime_result (app/logic/verdict_engine.py:82, 102-103); the scan cannot see it because the class name is never written there

### Not drawn, by the drawing rule (14)

An arrow is drawn when a class stores, creates or directly works with another class, including calling methods on an object it gets back from another call. Not drawn: reads of another class's constant, and objects a class only passes on (checked by hand). See uml/UML_CORRECTIONS.md, stage 7.

- App → CaseTimeline: constant only
- AssessmentRunner → Declaration: only passed on: the declaration goes straight into CrimeScan's methods (assessment_runner.py:212-216)
- AssessmentRunner → ResearchReport: only passed on: the reports go straight into CrimeScan.verify_typology_sources (assessment_runner.py:143, 158)
- AssessmentRunner → Verdict: only passed on: the Verdict from combine() is put into the result dict unchanged (assessment_runner.py:229, 242-)
- CaseBuilder → ClientForm: constant only
- ClientForm → DocumentStore: false match: record.documents() returns a list of document entries, not the DocumentStore (client_form.py:763)
- DocumentRecordBuilder → CaseReader: constant only
- Forecast → ClientRecord: only passed on: the case is handed to AssetPath.build (forecast.py:146, 270)
- FuturePaths → ClientRecord: only passed on: the record is handed to AssetPath.build (future_paths.py:72)
- OnboardingAssessor → Verdict: constant only
- PayCalibrator → MarketModel: constant only
- ReportView → DocumentStore: false match: record.documents() returns a list of document entries, not the DocumentStore (report_view.py:270)
- VerdictEngine → FuturePaths: constant only
- WebApp → ClientForm: constant only

## Appendix: values shortened with `...` (checked by pattern: class name or folder, 54)

`App.__assessments`, `App.__case_builder`, `App.__case_files`, `App.__client_form`, `App.__clients`, `App.__config`, `App.__document_ai`, `App.__documents`, `App.__limiter`, `App.__report_view`, `App.__response_cache`, `App.__runner`, `App.__syncs`, `AssessmentRunner.STEPS`, `AssessmentRunner.__verdict_engine`, `Band.MONEY_IN`, `Band.MONEY_OUT`, `Benchmark.BENCHMARK_LABELS`, `Benchmark.COMPOSITION_RULES`, `Benchmark.__config`, `BenchmarkAI.ALLOWED_FIELDS`, `CaseFiles.__folder`, `CaseReader.__PRESENT_WORDS`, `ClientForm.PAYMENT_METHODS`, `ClientForm.PEP_OPTIONS`, `ClientRecord.__profile`, `ClientRepository.OLD_ASSET_KEYS`, `CloudSync.__state_path`, `ConfigReader.__folder`, `ConsoleUI.__read`, `ConsoleUI.__write`, `CrimeScan.MATCH_LABELS`, `CrimeScan.__COUNTRY_TO_ISO`, `CrimeScan.__indicators`, `DocumentReaderFactory.READER_TYPES`, `DocumentStore.__folder`, `Forecast.__assessor`, `Forecast.__config`, `Forecast.__future_paths`, `Forecast.__pay_calibrator`, `FuturePaths.__asset_path`, `FuturePaths.__career_savings`, `ImageReader.IMAGE_TYPES`, `JsonRepository.DATA_DIR`, `RelatedPartyTransaction.__KEYWORDS`, `ReportView.FIELD_NAMES`, `ReportView.OUTCOME_LABELS`, `ReportView.SOURCE_TAGS`, `ResponseCache.__folder`, `VerdictEngine.MARKS`, `VerdictEngine.REPORT_LEGEND`, `VerdictEngine.THEMES`, `VerdictEngine.VERDICT_LABELS`, `WebApp.__flask`

