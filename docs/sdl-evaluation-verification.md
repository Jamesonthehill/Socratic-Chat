# SDL evaluation verification — November 17, 2026

## Outcome

Authentication fixed through the existing local workspace configuration. No credentials were printed, copied into reports or committed. The stale inherited key returned HTTP 401; the workspace dotenv key returned HTTP 200. `--env-file` overrides provider settings only for the evaluation CLI process.

The real production Scrum pipeline completed generation, validation and independent evaluation. The final explicit-audit evaluation of that saved lesson passes. The generator was `gpt-4o-mini-2024-07-18`; the independent evaluator was `gpt-4.1-2025-04-14`. No production validator verdict was used as independent score evidence.

## Final baseline scores

| Dimension | Synthetic Scrum | Actual guide |
|---|---:|---:|
| accuracy | 3/3 | 3/3 |
| coverage | 3/3 | 2/3 |
| prerequisites | 3/3 | 3/3 |
| quiz_quality | 2/3 | 2/3 |
| progression | 3/3 | 2/3 |
| application | 2/3 | 2/3 |
| rubrics | 2/3 | 2/3 |
| grounding | 3/3 | 3/3 |

The actual-guide run fails the quality gate. Its outcome audit finds no direct assessment of the requested Sprint Retrospective distinction. This is a completed evaluation with a substantive finding, not an execution/provider error.

## Challenges against the same saved baseline

All seven final mutations were rejected, with the intended reason confirmed from the structured audit or deterministic invariant—not merely from overall failure.

| Challenge | Detection | Evidence |
|---|---|---|
| weak_distractors | Independent question audit | Only option 1 is defensible; the other options are 'ignore all evidence' and do not represent plausible misconceptions. |
| ambiguous_options | Independent question audit | Options 1 and 2 are semantically equivalent ('To establish a Sprint Goal and create a Sprint Backlog'), so both are defensible as correct. Distractors are plausible and based on common misconceptions. |
| experience_assumption | Independent prerequisite audit | The required_task prompt demands actual professional experience, which is explicitly excluded by the prerequisites and constraints. The scenario is otherwise sufficient and elicits distinct reasoning steps. |
| missing_coverage | Independent outcome audit | Distinguishing Daily Scrum, Sprint Review, and Retrospective is not actually assessed; Q3 is a duplicate of Q1 and the application prompt is a restatement, not a new scenario. |
| duplicate_application | Deterministic exact-duplicate check | application:decide repeats application:identify verbatim. |
| malformed_evidence | Deterministic rubric evidence-group check | Q1 reasoning_rubric[0] contains a one-entry evidence group; at least two distinct alternatives are required when a group is supplied. |
| unsupported_citation | Deterministic citation-membership check | Q1 cites S999: Invented supporting passage., which is absent from the fixed source corpus. |

## Problems exposed and corrected

- Inherited invalid provider credentials shadowed a working local dotenv key: added explicit process-scoped provider configuration selection.
- A runpy launcher exposed unresolved deferred Pydantic annotations: removed unnecessary deferred annotations and added a launcher/schema test.
- Judges conflated instructor requests with source evidence and fabricated combined quotations: constrained quote selection to actual excerpts, separated source text from expectations and saved raw responses even on validation errors.
- Broad dimension scoring missed weak distractors, equivalent options and prerequisite violations on a fresh baseline: added per-question option audits, an entire-task prerequisite/scenario audit and explicit per-outcome assessment audits within the same existing evaluator call. Failed audits block a pass even when numeric scores look adequate.
- Missing-coverage corruption retained the target outcome in the shared task and accidentally mismatched answer feedback: removed that escape route and preserved matching option feedback. Its final failure has no deterministic structural error and is explicitly attributed to missing event-distinction assessment.

Earlier exploratory runs and the pre-audit false negatives are retained in the artifacts. The first broad evaluator detected all seven on an earlier lesson but missed three on a different baseline. That is not a reliable 7/7 result; only the final structured-audit runs are summarized as current.

## Actual source fixture

Selected guide pages: 2, 4, 5, 6, 7, 10, 11, 12, 13. The original PDF has 14 pages; source SHA-256 is `731948c2f58505e0e0c592f76e75c85fa92adedd7ad1ac51fe771f71a630871b`. The version-controlled extracted fixture is 18,498 characters and retains guide-page headings and source maps. It covers the requested planning, accountabilities, self-management, artifacts/commitments, events and practical adaptation scope. Optional estimation/story-writing sections were not selected. The original PDF was not rewritten.

The dataset now has 14 candidate cases. This authentic-source case remains a candidate pending subject-matter review; source authenticity is not an authoritative answer key or human-rating calibration.

## Actual tests

Executed from the complete repository root, not the ZIP:

```powershell
$env:PYTHONPATH=Join-Path (Get-Location) "self-directed-learning/backend"
python -m pytest self-directed-learning/backend/tests/test_sdl_evaluation.py self-directed-learning/backend/tests/test_instructional_quality.py self-directed-learning/backend/tests/test_generation_quality.py self-directed-learning/backend/tests/test_edumind_quiz.py -q -p no:cacheprovider --junitxml=artifacts/sdl-eval-audited-tests.xml
```

Final result: **142 passed**: 45 evaluation-framework tests and 97 production regressions; zero failures/errors. One existing Starlette/AnyIO deprecation warning. The actual JUnit XML and console log are included. Ordinary tests block network calls and do not spend model tokens.

## What can be relied on

**Deterministic invariants:** schema/type validity, required fields, counts and answer-index structure, valid IDs/mappings, exact repeated prompts, optional evidence-group shape, exact source-citation membership and approved reading-URL provenance. These checks do not certify meaning. Reachability checks are time-dependent network observations; no external reading URLs were returned in the final baseline, so that live branch was not exercised by this run. Offline tests cover URL provenance/reachability outcomes.

**Model judgments:** factual support, substantive outcome coverage, prerequisite/experience assumptions, semantic option equivalence and plausibility, cognitive progression, scenario sufficiency, semantic redundancy and rubric assessability. Structured audits make omissions harder but remain model judgments. Verbatim evidence selection proves provenance, not relevance or correctness of the judgment.

**Not validated against human ratings:** every semantic dimension, the 0–3 score scale, pass thresholds, inter-rater agreement, false-positive/negative rates and sensitivity to subtle defects. No human panel or blinded human scores were used.

## Remaining limitations

- One synthetic baseline, one actual-guide case and seven conspicuous corruptions are a smoke/sensitivity test, not statistical validation. The full 14-case dataset was not run live.
- Numeric scores and subjective flags remain unstable: the malformed-rubric mutation also caused a new complaint about unchanged Q3 distractors. Treat that as a potential inconsistency, not proof of a second injected defect. Human calibration and repeated holdout runs remain necessary.
- Evaluator changes were developed against these probes. Further untouched topics/defects are needed to assess generalization and avoid evaluation overfitting.
- The real-guide lesson still has a coverage defect; generation prompts were not rewritten to force a passing lesson during verification.
- This suite begins with selected source text; it does not test PDF parsing fidelity, database document ownership/selection or student-time vector retrieval.
- Existing production retry/repair logic was invoked normally; the final successful baseline did not need a semantic repair. Offline tests exercise bounded repair paths.
- Per-call models, tokens and latency are saved. Pricing was not supplied, so cost remains unknown. No credentials are included.

## Artifact map

- `scrum-lesson.json`: standalone fresh production lesson.
- `audited-baseline/report.md` and `report.json`: final independent baseline scores, findings and explicit audits.
- `scrum-end-to-end/`: uninterrupted production generation-to-evaluation execution and model usage; final audits reuse this exact saved output.
- `study-guide-lesson.json` and `audited-study-guide/`: authentic-source lesson and substantive failing evaluation.
- `audited-challenges/<challenge>/`: corrupted outputs, raw judge responses and reports for all seven final challenges.
- `verification-summary.json`: machine-readable detection reasons, source/baseline hashes and counts.
- `test-results/`: actual final JUnit XML and console log.
- Earlier directories retain the failed experiments and pre-audit false negatives.
