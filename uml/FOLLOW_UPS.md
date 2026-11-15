# Follow-ups found during the UML conformance work

These are problems found by the independent reviews. They were **not** fixed in the step that found them,
because they are outside that step's scope. Each needs its own small fix later.

| # | Found in | Problem | Where | Kind |
|---|---|---|---|---|
| 1 | R1 review | A damaged client file is read as **empty**: `JsonRepository.load` returns `[]`, so `find_client` reports "No client found" instead of "the database can't be read" (CLAUDE.md §9: empty and broken are different) | `app/data/json_repository.py:37-40` | §9 bug (existed before R1) |
| 2 | R1 review | Saving to a damaged client file overwrites it with one record | `app/data/client_repository.py:23-30` | §9 / data-loss risk (existed before R1) |
| 3 | R1 review | If the client record fails to save after an assessment, this is only logged; the CLI and web still say the assessment was saved | `app/application/app.py:301-302` | §9 bug (existed before R1) |
| 4 | R1 review | A saved record that `ClientRecord` can't read (e.g. age 15) can no longer be opened, not even to fix it. It should open on the edit page with the problem shown | `app/interface/web_app.py` view/edit, `client_form.py` find | Usability risk (new in R1; both sample files load fine) |
| 5 | R1 review | One impossible value in an AI document reading throws away **all** the fields it read; it would be kinder to clear only the bad field | `app/application/app.py:413-421`, `app/interface/web_app.py:507-513` | Design choice |
| 6 | R1 review | `ClientRecord.from_dict` drops a saved `forecasting_case` when there is no `outcome` (no current code writes that shape) | `app/model/client_record.py:319-321` | Small data-loss risk |
| 7 | R1 review | `ClientRecord.current_job()` falls back to the last *ended* job for records whose current job is only in `career` (nothing calls it on that path today) | `app/model/client_record.py` | Latent bug |
| 8 | R1 review | Only `ValueError` is caught around `ClientRecord.from_dict` in the form/web paths (`App.find_client` also catches `TypeError`/`AttributeError`) | `client_form.py`, `web_app.py:543-547`, `app.py:415` | Consistency nit |
| 9 | Stage 2 review | The WebApp helpers the page types rely on (`show_form`, `autofill_form`, `show_report`, `get_record`) have no return types | `app/interface/web_app.py` | Typing (stage 3/5) |
| 10 | R2 review | `VerdictEngine` helpers `_feature`, `_feature_checks`, `_check` use one underscore but the class has no children (should be `__`); its `_check(feature, …)` differs from `RiskAnalysis._check(check, …)` | `app/logic/verdict_engine.py:56-68` | Naming (stage 3) |
| 11 | R2 review | `Check` carries feature details (`signs`, `match`, `typology_id`, `independent`, `optional`) through `extra()`/`set_extra()`/`FIELDS`, which the UML `Check` box doesn't show | `app/model/check.py` | UML update (stage 5) |
| 12 | R2 review | `Forecast.document_request` is `(failures: list[dict], candidates) -> list[dict]`; the UML says `(failures : list[Check]) : dict`. It runs on the assessor's raw failure records before any checks exist | `app/logic/forecast.py` | Stage 3/4 decision |

Fixed straight away (not listed above): the R1 review's two bugs, (a) "changes could not be kept" followed by
"Changes saved successfully" in `find_existing_client`, and (b) an open "previous" job replacing the current
job in the CLI New Client form.
