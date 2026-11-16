# UML views

Readable views of `uml/class_diagram_v4.puml`, as a draw.io file: `uml/class_diagram_v4_views.drawio`.
Each tab is one page; a PNG of each generated tab is in this folder. Do not edit these files by hand:
they are rebuilt from the diagram (see the end of this file).

| Tab | PNG | What it shows |
|---|---|---|
| Overview | `00_overview.png` | Every class (name only) in a box per folder, folders in architecture order. Inside a folder only the structural links (inheritance, realization, composition, aggregation, association). Between folders: one thick arrow per ordered pair of folders, labelled with a count, e.g. `owns 9 · uses 5`. |
| Application | `01_application.png` | `App` and `AssessmentRunner` |
| IO Manager | `02_interface.png` | The 6 classes of `app/interface` |
| AI Manager | `03_ai.png` | The 7 classes of `app/ai` |
| Logic: risk checks | `04a_logic_risk.png` | `RiskAnalysis`, `CrimeScan`, `Benchmark`, `DocumentEvidence`, `Indicator` and its 5 children, `VerdictEngine` |
| Logic: forecast | `04b_logic_forecast.png` | `Forecast`, `FuturePaths`, `AssetPath`, `CareerSavings`, `MarketModel`, `CaseTimeline`, `PayCalibrator`, `OnboardingAssessor` |
| Logic: helpers | `04c_logic_helpers.png` | `CaseReader`, `DocumentRecordBuilder`, `RecordDiff`, `AuditChain`, `Formatter` |
| Data Manager | `05_data.png` | The 18 classes of `app/data` |
| Model: client record | `06a_model_client.png` | `ClientRecord`, `ClientProfile`, `Job`, `Investment`, `Claims`, `Declaration`, `ClaimedSource`, `ReviewStatus` |
| Model: results and config | `06b_model_results.png` | `Verdict`, `Check`, `MatchResult`, `Typology`, `ResearchReport`, `Band`, `Config`, `Account` |
| Model: audit | `06c_model_audit.png` | `AuditEvent`, `AuditFilter`, `AuditPage`, `TrailFilter` |

Every class is an own class (full box) on exactly one tab. Every relationship that touches a tab's own classes is drawn on
that tab, so each relationship appears on at least one tab (on two when its ends are on different tabs).

The overview leaves out the dashed uses/creates links inside a folder, and all verb labels and multiplicities. The links
between folders are summarised in the thick arrows; each one is drawn class to class on the folder tabs.

## Reading a folder tab

- The big coloured frame holds the folder's own classes: name, attributes with types, then public and protected methods.
- Small grey boxes are classes that are not own classes of the tab. They sit in a grey frame per folder, on the side of the
  page nearest to the classes that use them (other folders above on top, Domain Model along the bottom, Data on the right).
  The classes of the same folder that live on another tab are in a frame labelled "(other tabs)", on the right.
- Hidden: constants (`«const»`) and private methods (`−`). The grey last line of each box says how many.
  Private attributes are still shown. Long method signatures are wrapped, one group of parameters per line.
- Lines are right-angled, in the same styles as the main diagram. Where several lines go to one class they may share a
  stretch, drawn on top of each other and ending in one arrowhead.

## Arrow kinds (same as the main diagram)

| Arrow | Meaning |
|---|---|
| Hollow triangle | Inheritance (solid line) or realization of an interface (dashed line); the triangle is at the parent |
| Filled diamond | Composition; the diamond is at the whole |
| Hollow diamond | Aggregation; the diamond is at the whole |
| Plain line | Association |
| Dashed open arrow | Dependency (uses, creates); folder tabs only |
| Thick arrow (overview) | All the links from one folder to another, counted by kind: owns = composition, has = aggregation, links = association, uses = dependency, inherits = inheritance |

## Regenerate

```bash
python3 ~/Documents/uml-check-tools/make_views.py "<repo>"
```

`--only overview,logic` builds just some tabs (the tabs already in the file are kept). The script checks that every
class and every relationship is accounted for and runs `layout_check.py` on every tab; it stops with an error if not.
