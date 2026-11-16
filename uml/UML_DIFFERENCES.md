# UML v4 vs code: differences, staged

Checked code at commit `6623eda` against `uml/class_diagram_v4.puml`, which is converted from `uml/class_diagram_v4.drawio` and was independently verified as faithful. Every class, attribute, property, constant and method signature was compared by script, so nothing was sampled.

**How to use this file:** work through one stage at a time, and tick `[x]` when an item is fixed. Then re-export the draw.io file, regenerate the `.puml` and re-run the check.

## How this was checked

| Link | How | Result |
|---|---|---|
| draw.io → PlantUML | A round-trip script plus an independent agent with its own parser | **Faithful**: 69 classes, 224 attributes, 393 methods, 114 relationships, 35 multiplicities and the main.py note all identical |
| PlantUML → code: members | Script reads every class with Python's `ast` | Stages 1–6 below |
| PlantUML → code: relationships | Script (static analysis) **and** an independent agent reading the code by hand; every disagreement was settled by re-reading the code | Stage 7 below |

**What was compared:** class presence, kind, package and parent; attribute name, visibility, type and starting value; `{get}` / `{get, set}` properties; «const» name, type and value; method name, visibility, parameters (names, order, types, defaults), return type, «static», abstract; every relationship's kind, direction, verb and multiplicity; class-to-class links in the code that have no UML line; module-level functions (only `app/ai/ai_caller.py`: ✅); the main.py note.

**Not checked (can't be, statically):** method behaviour; 98 values the UML shortens with `...` (listed at the end).

**Area** is the feature area of the class, to help split the work. It is a best guess, so confirm it with the team. Don't change a teammate's files without asking them.

## Overview

| Stage | What | Items | Mostly fixed in |
|---|---|---|---|
| 1 | Structure: classes and inheritance | 0 | Code + UML |
| 2 | Graded code rules: types and `__init__` | 0 | Code |
| 3 | Same member, different details | 0 | Decide per item |
| 4 | In UML, missing in code | 0 | Decide per item |
| 5 | In code, missing from UML | 0 | UML |
| 6 | Minor: default and starting values | 0 | UML |
| 7 | Relationships (arrows, verbs, multiplicities) and the main.py note | 0 | Mostly UML |
| | **Total** | **0** | |

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

## Stage 5: In code, missing from UML (0)

The code grew past the diagram, mostly helper methods and constants.

How to fix: **UML:** add them to the draw.io boxes. If a class gets too big (professor: more than ~10 attributes is a worry), think about splitting it before adding everything.

**Done.** Nothing left in this stage.

## Stage 6: Minor: default and starting values (0)

A parameter default the UML leaves out, or an attribute whose starting value differs.

How to fix: **UML:** add or correct the `= value`. Where the code is computed, decide by hand. For the `= None` pattern, the team can agree once on whether parts created in `__init__` are shown as `= None` or without a value. Do it last.

**Done.** Nothing left in this stage.

## Stage 7: Relationships (0)

146 of 148 UML arrows are confirmed in the code by the pattern check (its known blind spots are listed in uml/FOLLOW_UPS.md #44).

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
- Forecast → ClientRecord: only passed on: the case is handed to AssetPath.build (forecast.py:146, 270)
- FuturePaths → ClientRecord: only passed on: the record is handed to AssetPath.build (future_paths.py:72)
- OnboardingAssessor → Verdict: constant only
- PayCalibrator → MarketModel: constant only
- ReportView → DocumentStore: false match: record.documents() returns a list of document entries, not the DocumentStore (report_view.py:270)
- VerdictEngine → FuturePaths: constant only
- WebApp → ClientForm: constant only
- WebApp → DocumentStore: false match: record.documents() returns the client's list of document entries, not the DocumentStore (web_app.py:601, 834); since #39 WebApp asks App (owns_document, read_document_for_extraction)

## Appendix: values shortened with `...` (checked by pattern: class name or folder, 98)

`App.ASSESSMENTS_UNAVAILABLE`, `App.CLIENTS_UNAVAILABLE`, `App.NOISY_LOGGERS`, `App.SETTINGS_UNAVAILABLE`, `App.__assessments`, `App.__case_builder`, `App.__case_files`, `App.__client_form`, `App.__clients`, `App.__config`, `App.__config_reader`, `App.__document_ai`, `App.__documents`, `App.__limiter`, `App.__report_view`, `App.__response_cache`, `App.__runner`, `App.__syncs`, `AssessmentRunner.FORECAST_STEP`, `AssessmentRunner.RESEARCH_STEP`, `AssessmentRunner.STEPS`, `AssessmentRunner.__verdict_engine`, `Band.MONEY_IN`, `Band.MONEY_OUT`, `Benchmark.BENCHMARK_LABELS`, `Benchmark.COMPOSITION_RULES`, `Benchmark.FORECAST_DERIVED`, `Benchmark.LIMITS`, `Benchmark._COMPOSITION_PARTS`, `Benchmark.__config`, `BenchmarkAI.ALLOWED_FIELDS`, `CaseFiles.__folder`, `CaseReader.COMPOSITION_KEYS`, `CaseReader.__PRESENT_WORDS`, `Check.FIELDS`, `ClaimedSource.READING_KEYS`, `ClaimedSource.__SCAN_NAMES`, `ClientForm.PAYMENT_METHODS`, `ClientForm.PEP_OPTIONS`, `ClientForm.__report_view`, `ClientRecord.CAREER_JOB_KEYS`, `ClientRecord.REQUIRED`, `ClientRecord.__OWN_KEYS`, `ClientRecord.__profile`, `ClientRepository.OLD_ASSET_KEYS`, `CloudSync.__state_path`, `ConfigReader.REQUIRED`, `ConfigReader.__folder`, `ConsoleUI.__read`, `ConsoleUI.__write`, `CrimeScan.MATCH_LABELS`, `CrimeScan.SIGN_LABELS`, `CrimeScan.SIGN_THEMES`, `CrimeScan.__COUNTRY_TO_ISO`, `CrimeScan.__indicators`, `DocumentReaderFactory.READER_TYPES`, `DocumentRecordBuilder.SUMMARY_SECTIONS`, `DocumentRecordBuilder.__config`, `DocumentStore.__folder`, `Forecast.__assessor`, `Forecast.__config`, `Forecast.__future_paths`, `Forecast.__pay_calibrator`, `ForecastAI.STAGES`, `FuturePaths.__asset_path`, `FuturePaths.__career_savings`, `ImageReader.IMAGE_TYPES`, `Job.KEYS`, `JsonRepository.DATA_DIR`, `MatchResult.CATEGORIES`, `RelatedPartyTransaction.__KEYWORDS`, `ReportView.FIELD_NAMES`, `ReportView.OUTCOME_LABELS`, `ReportView.SOURCE_TAGS`, `ReportView._CRIME_CATEGORY_LABEL`, `ReportView._CRIME_INDICATOR_LABEL`, `ReportView._CRIME_SECTION_TITLE`, `ResponseCache.__folder`, `TypologyAI.ALLOWED_FIELDS`, `TypologyAI.REPORT_FIELDS`, `Verdict.CHECK_GROUPS`, `Verdict.EXPLANATION_KEYS`, `Verdict.SEVERITY`, `VerdictEngine.MARKS`, `VerdictEngine.ORIGINAL_BENCHMARK`, `VerdictEngine.REPORT_LEGEND`, `VerdictEngine.THEMES`, `VerdictEngine.VERDICT_LABELS`, `VerdictEngine._ROUTINE_NOTES`, `WebApp.ASSESSMENT_NOT_SAVED`, `WebApp.ASSET_FIELDS`, `WebApp.CLAIM_FIELDS`, `WebApp.CLIENT_FIELDS`, `WebApp.COMPOSITION_FIELDS`, `WebApp.JOB_FIELDS`, `WebApp.SECTIONS`, `WebApp.SOW_FIELDS`, `WebApp.__flask`

