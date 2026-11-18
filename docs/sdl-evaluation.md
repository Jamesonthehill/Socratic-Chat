# SDL lesson regression evaluation

This is a small CLI, not a production service. The 14 candidate cases in
`self-directed-learning/backend/evaluation/cases.json` are **candidate inputs
requiring subject-matter review**, not authoritative gold standards. Expected
coverage and misconceptions describe competencies; there are no ideal lessons or
exact expected sentences. The Scrum case incorporates the requested Sprint
planning/execution/inspection/adaptation focus and explicitly excludes practical
Scrum experience. Other cases cover Git, SQL, HTTP/REST, testing, probability,
biology, physics, economics and cybersecurity at several educational levels.
An additional Scrum case uses selected pages from the actual user-supplied study
guide, with PDF and fixture hashes. Three adversarial requests exercise inadequate
SQL evidence, contradictory Git
experience constraints and a biology source too weak to teach the outcomes.

## Architecture and scope

The runner calls the real `app.platform_lessons.prepare(PrepareInput(...))`, which
calls `main._document_plan`, objective design, production source-passage selection,
EduMind quiz generation, lesson generation, configuration checks and
`instructional_quality.review_and_repair`. No generation, validator or repair
function is reimplemented or replaced. No lessons are published and no database
is opened or modified by the runner.

This boundary is deliberate: `platform_app.workspace.prepare_sdl` normally loads
the selected indexed documents with `shared_rag.course_chunks`, concatenates the
returned text up to 30,000 characters and sends it to this preparation function.
Fixtures stand in for that **already selected document text**. Production authoring
uses the numbered passages from this text, not the student's nearest-neighbor
retrieval route. The runner exercises that real authoring passage selection and
records the evidence corpus and final citations. It does **not** benchmark upload
parsing, remote database selection/ownership, embedding quality or student-time
vector search. Changes confined to those upstream components need their existing
integration tests or exported, reviewed selected-document snapshots added here.
This is not a claim to measure a retrieval algorithm the authoring path doesn't use.

The independent evaluator has its own eight-dimensional anchored rubric and prompt.
It sees the original instructor request, source and actual lesson/error, with the
production review verdict and approval fields withheld. It does not call the
production quality validator for a score. Source and lesson evidence must be
verbatim excerpts from the actual inputs or the evaluator result is invalid. The response schema constrains evidence choices to those excerpts; whitespace wrapping is tolerated but words cannot be invented. Instructor outcome declarations and production coverage claims are withheld from observed lesson content. Raw evaluator responses are saved even when evidence validation fails.
The configured production provider transport is reused; `--judge-model` can choose
a different model on that provider without changing generation. The default model
can share systematic biases with the generator despite the separate prompt.

Deterministic checks reuse `LearningPlan` and the citation partition contract but
independently inspect required content, quiz counts/keys/options, application
counts, IDs/mappings, exact repeated prompts, rubric evidence groups and exact
source references. Semantic duplicates, factual support, plausible distractors,
coverage and assessability belong to independent model review, not keyword rules.
Generated reading URLs must be among the URLs actually returned by production
resource verification, and must pass a separate HTTPS reachability probe. URLs
without provenance are never fetched. Redirects are bounded and private targets
are excluded. Embedded resources intentionally have empty URLs. Unavailable,
blocked or timed-out URLs fail the check rather than silently pass; availability
is a temporal check, not proof of educational authority or relevance.

## Commands

Run from `self-directed-learning/backend` using the existing Python environment
with backend dependencies installed. In PowerShell, set
`$env:PYTHONPATH=(Get-Location).Path` for pytest. `python -m` already makes this
directory available to the CLI. No new dependencies are required.

```powershell
python -m evaluation.runner --list

# After reading/correcting every source and case, attest review and freeze hashes.
python -m evaluation.runner --freeze evaluation/frozen.json --reviewed-by "Reviewer name"

# Real, paid production generation + independent evaluation for one case.
python -m evaluation.runner --case scrum --manifest evaluation/frozen.json --live --output artifacts/sdl-eval/baseline

# Complete dataset. Configure credentials through the existing environment/.env.
python -m evaluation.runner --manifest evaluation/frozen.json --live --output artifacts/sdl-eval/full

# Early development smoke test on unreviewed inputs; explicitly labeled candidate run.
python -m evaluation.runner --case scrum --allow-candidates --live --output artifacts/sdl-eval/candidate

# Compare a later generation against an unchanged frozen baseline.
python -m evaluation.runner --case scrum --manifest evaluation/frozen.json --live --baseline artifacts/sdl-eval/baseline/report.json --output artifacts/sdl-eval/changed

# No LLM or network calls: replay only structural checks. Overall remains NOT EVALUATED.
python -m evaluation.runner --case scrum --manifest evaluation/frozen.json --replay artifacts/sdl-eval/baseline --output artifacts/sdl-eval/offline

# Rejudge the same generated output, or probe sensitivity with a controlled defect.
python -m evaluation.runner --case scrum --manifest evaluation/frozen.json --replay artifacts/sdl-eval/baseline --challenge ambiguous_options --live --output artifacts/sdl-eval/ambiguous
```

Other replay challenges: `experience_assumption`, `weak_distractors`,
`duplicate_application`, `malformed_evidence`, `missing_coverage`,
`unsupported_citation`. They corrupt copies of **saved real outputs**, never the
production pipeline. Inspect the injected output and judge evidence to determine
whether the evaluator caught the intended defect. A failing corrupted lesson is
expected; a pass is a signal that the evaluator needs calibration. The challenges
are probes, not a psychometrically validated test bank. Some corruptions can
produce more than one related defect; use the actual explanations, not only an
overall failing status, when assessing sensitivity.

An existing output directory is never overwritten. A run exits 0 only when every
selected case passes; failures, operational errors and offline-only runs exit 1.
Invalid command arguments exit 2. Reports checkpoint after every case, so earlier
cases survive a later failure. Provider failures are recorded as errors, not
successful safe rejections. Cases continue after an error; interrupt the CLI to
stop spending when a provider-wide outage is apparent. There are no evaluator
retries; the production pipeline retains its own bounded retry/repair behavior.

## Rubric, reports and comparison

`evaluation/rubric.json` anchors every dimension at 0 (unacceptable), 1 (substantial
weakness), 2 (adequate) and 3 (strong): factual accuracy, coverage, prerequisites,
quiz/distractor quality, cognitive progression, application tasks, assessable
rubrics and source faithfulness. A normal lesson passes only with every dimension
at least 2, mean at least 2.5, no independent unresolved failures and no structural
failures. These are initial policy thresholds requiring calibration with human
ratings. They do not make subjective model judgments objective facts.

For insufficient-source/conflicting-instruction cases, eight lesson-quality
scores are not applicable and are excluded from dimension means. The independent
judge must instead find evidence that the **specific** gap/conflict was surfaced
and unsupported requirements were not silently fulfilled. A generic failure is
not successful handling. Aggregate reports show the scored denominator for each
dimension, pass count, operational errors, latency and known/unknown costs.

Each output directory contains:

- `report.md`: human-readable scores, concrete failures, lesson/source quotations,
  usage summary and optional comparison table.
- `report.json`: all results, aggregate scores, protocol hash, Git revision and
  working-diff hash. Per-call records include model, token usage when returned,
  status and latency, never authorization headers or request bodies.
- `<case>/input.json`, `output.json`, `evidence.json`, `evaluation.json`: exact
  case/source, complete production output/error, numbered source passages, scores
  and usage for inspection. Production review findings remain in the raw saved
  output for debugging, but are withheld from the independent judge.

Use `--pricing path/to/pricing.json` to supply USD rates per million tokens:

```json
{"your-model-name": {"input_per_million": 1.0, "output_per_million": 2.0}}
```

These example numbers are placeholders, **not current provider pricing**. Without
both supplied rates and reported token usage the cost is null, never zero. The
estimate uses prompt/output totals; cached-token discounts, tiers and ancillary
costs are not modeled. Generator and evaluator model calls both contribute. On
replay, call costs are for the current invocation; the saved generation latency
is retained and does not imply regeneration occurred.

Comparison matches IDs only when input/source hashes and the evaluation protocol
(rubric, evaluator configuration, runner implementation and challenge) match.
It shows per-dimension deltas, newly added structural failures and regressions
(a prior pass becomes a failure, a score decreases or a new structural failure
appears). Changed fixtures/protocols are marked incomparable. The generator Git
revision may change: this is the behavior being compared. Keep judge settings
fixed, repeat runs to estimate noise and review borderline differences manually.
Model providers can change aliased models and optional reading discovery can
change over time; saved usage/output evidence exposes but cannot eliminate these
sources of variation. This framework is repeatable, not bitwise deterministic.

## Updating and testing

Edit the compact sources and case expectations together; keep facts and source
limitations explicit. Ask a subject reviewer to check accuracy, educational level,
scope and misconceptions before creating/committing `evaluation/frozen.json`.
Do not bless model-generated cases automatically or use a baseline as ideal text.
Any input/source change invalidates its frozen hash and baseline compatibility.
Store reports under ignored `artifacts/`; do not commit credentials, private
course documents or student responses. Fixtures are synthetic except for the explicitly attributed actual Scrum study-guide extraction.

```powershell
python -m pytest tests/test_sdl_evaluation.py -q
```

Ordinary tests block all network calls and inject model responses. They verify
dataset integrity, freezing, deterministic failure modes, evaluator evidence
validation/independence, production-function delegation, saved reports, usage
accounting and baseline comparability. They do not establish live evaluator
accuracy. A useful next review is blind human scoring of several normal and
corrupted saved outputs, followed by comparing the independent model ratings.


## Initial verification on November 17, 2026

The candidate Scrum smoke run reached the real production provider request, which
returned HTTP 401 using the local environment's configured OpenAI credential.
The runner saved an operational-error report without quality scores under
`self-directed-learning/backend/artifacts/sdl-eval/scrum-candidate-smoke/report.md`.
This is a local credential failure, not a finding about the deployed Render
configuration. No live educational-quality scores or reviewed baseline were
produced. The candidate dataset remains unfrozen pending subject review. The
ordinary harness tests make no network or paid model calls.


## Verified local authentication and live-run follow-up

The initial 401 was caused by a stale inherited `OPENAI_API_KEY`, not a rejected
key in the existing workspace `.env`. The workspace file authenticated with HTTP
200; the inherited key and another SDL-local key returned 401. No key was printed,
copied into a new file or committed. `--env-file` now explicitly loads only provider
settings from an existing dotenv file before the production modules import their
configuration. It overrides inherited provider settings in this CLI process only;
it does not import database settings, change the parent environment or change
production configuration precedence.

In this worktree, from `self-directed-learning/backend`:

```powershell
python -m evaluation.runner --env-file ../../../.env --case scrum --allow-candidates --live --judge-model gpt-4.1 --output artifacts/sdl-eval/my-new-run
```

Use the appropriate existing provider file on another checkout. Never place its
contents in a command, report, Git commit or evaluation ZIP. See
`sdl-evaluation-verification.md` for the actual run and challenge results. The
original November 17 smoke-test failure above is historical and was superseded
by the authenticated runs; the candidate inputs still await human review.


### Explicit audits after live false-negative testing

The same independent evaluator call now returns one option audit per quiz item,
one prerequisite/scenario/step audit for the entire application task, and one
assessment audit per expected outcome. The server rejects omitted audits and
invalid IDs. A false audit flag adds an explicit failure even when the model
assigns apparently adequate numeric scores. This addresses three demonstrated
false negatives without adding agents or extra evaluator calls. The authentic
study-guide case exposes a missing Retrospective assessment that production
validation accepted. Details, earlier misses, corrected challenge results and
remaining model inconsistencies are in the verification report.

`judge-response.json` preserves the raw response. The final report adds validated
audit findings; it does not fabricate or automatically remap model dimension
scores. Verbatim excerpt selection constrains provenance, while the explanatory
judgment remains subjective. Passing the seven final probes does not establish
human agreement or general sensitivity. All semantic scores remain provisional.
