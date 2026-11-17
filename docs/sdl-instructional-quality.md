# SDL instructional quality

The supplied example exposed two upstream problems: the whole end-goal paragraph
became OBJ1, and instructor setup text was prepended to material used for source
citations. New platform preparations now opt into a versioned authoring contract:

- Keep source evidence separate from instructor focus and teaching preferences.
  Remove empty Page/Document wrappers and build paragraph-aware passages.
- Group all exact instructor requirements into three distinct measurable objectives.
  Assign the three quiz questions to different objective groups.
- Require one shared scenario and identify/decide/apply progression. Later prompts
  build on prior student responses. Stage criteria and the combined rubric must
  assess the actual requested reasoning, not only role identification.
- Reject duplicated prompts, fabricated/placeholder references, repeated objective
  mappings and invalid stage ordering with deterministic checks.
- Independently review actual source text, study explanations, MCQ options/keys,
  application prompts and rubrics. Check every requirement for study coverage,
  assessed evidence and source support. IDs alone do not prove alignment.
- Return a failed/unavailable semantic review as an editable draft with clear
  issues. Force a fresh server-side review at publication after edits; never trust
  a client-supplied claimed pass. Publication remains blocked until review passes.
- Supply objective/section criteria to runtime interview generation and reject
  exact repetition of application prompts. The two purposes remain justification
  and transfer under a changed condition. Before publication only this contract
  can be checked; future personalized questions do not yet exist.

The student workflow, scoring, sessions and 3 quiz / 3 application / 2 interview
format remain unchanged. Older frozen lessons keep their existing contract.
No database migration is needed. Model-assisted checks reduce risk but do not
certify semantic correctness; instructors must still review the generated draft.
Additional design/review requests add provider latency and cost.

Verification uses local source/coverage/rubric/progression failure fixtures and
existing assessment regressions. The approved local OpenAI test returned HTTP 401,
so no live generated sample was validated. The user declined testing through the
preview service and will test the deployed branch directly.

## Citation-size regression

Paragraph-aware source passages initially allowed up to 1200 characters while
QuizQuestion.material_reference is limited to 1000 including the passage ID.
This caused deterministic adapter ValidationErrors on long source excerpts,
which the error handler incorrectly collapsed into a generic provider failure.
Passages are now bounded to 900 characters and split without dropping the rest
of the source. Schema errors report only field locations and validation messages,
never the rejected source/student/provider payload. A long-source regression
reproduces the original failure and verifies the corrected adapter contract.

## Objective-allocation recovery

The first objective designer represented requirement IDs as lists nested under
three generated objective descriptions. That shape allowed the model to omit a
broad end goal while mapping its component subquestions. The validator reported a
combined omission/duplication error and blamed the instructor's scope.

The designer now returns two fixed-key objects: exactly OBJ1/OBJ2/OBJ3 descriptions,
and one required allocation entry for every exact REQ ID. Broad goals may map to
multiple objective groups. Strict structured output requires all keys. The local
validator still rejects missing/unknown/empty/duplicate allocations and repeated
objective descriptions. One bounded repair receives the original requirements,
previous design and precise validation issues; it cannot silently drop inputs.
Descriptions now honor the downstream 1200-character Objective limit as well.
This changes authoring recovery only; source review and publication guards remain.

## Quiz prompt and same-call planning

EduMind remains in the existing lesson workflow with the same model/provider and
one existing quiz-generation call. No service, API, agent, or extra quiz pipeline
is introduced. The call now receives the original full learning focus, concept/
subquestion list, prior knowledge and end goal alongside source passages and the
existing derived objective groups. It silently interprets intent, ranks important
concepts, distributes questions, writes all options/support, and validates the
complete quiz within that same call. No internal planning is returned to students.

The prompt prioritizes meaningful understanding/application, at least two
scenario-dependent questions in the three-item quiz, parallel plausible distractors,
one defensible key, option-indexed feedback, source support, calibrated difficulty,
and reasoning hints without answer leakage. Scrum examples are explicitly optional
coverage guidance, not hardcoded questions or subject matter for other courses.

For the new three-objective mode, the existing structured response has one required
question slot per objective ID. The server binds each named slot to its objective
instead of asking the model to repeat and correctly distribute free objective_id
strings. It normalizes those private slots back to the unchanged QuizQuestion
array, with Q1/Q2/Q3, four options, integer answer key, hints, citations and indexed
feedback. Missing slots and conflicting IDs are rejected, never silently relabeled.
The older array response remains readable for legacy formats.

Exactly three slots and distinct concept checks are structural safeguards; the
existing independent review still checks actual content coverage, not labels.
The response schema is supplied once through response_format when supported, and
unused definitions are removed to avoid duplicating schema tokens in the prompt.
Scoring, student workflow, application/interview counts and saved sessions do not
change. Tests verify instructor-input forwarding, schema completeness, one quiz
provider request, unchanged output, rejected missing/relabelled slots and prior
source/assessment regressions. No live generation test was performed.

## Generation duration and compact short lessons

The platform bridge used a 180-second read timeout for every document-service
request. Lesson preparation chains authoring stages and can exceed that window;
the error described file processing even though the source was already indexed.
Only POST /internal/platform/lessons/prepare now uses a 480-second read budget with
a 15-second connect budget. Other paths retain their existing timeout. A timed-out
request is never automatically replayed. The generation-specific error explicitly
says draft inputs and selection are retained.

New short-assessment generation no longer requests legacy foundational/standard/
accelerated practice banks. Three objective groups previously required at least
18 extra exercises that the 3-3-2 student path never uses. Short lessons retain
all study explanations, worked examples, counterexamples, quiz hints/feedback,
application questions/criteria and the two interviews. Empty banks are accepted
only in the short lesson contract; legacy plans still require their practice
bands, and existing saved banks are not removed from frozen lessons.

The model-facing short-lesson schema omits unused practice fields; the server
normalizes them to empty arrays for compatibility. Short-lesson quiz-support
repairs also skip unused practice generation. Schema text is supplied once
through response_format rather than duplicated in the prompt. Authoring logs
record stage names, elapsed time and HTTP status only, never course content,
student answers or credentials. These changes reduce requested output and allow
bounded waiting; live generation speed has not been measured by this test suite.

## Draft recovery and assessment-wide alignment

Quality-mode coverage is assessed across quiz and application together. An
application stage must map to real, relevant objectives and explicit criteria,
but every stage (or the application alone) need not repeat all broad objective
groups already assessed by the quiz. Reusing a broad objective across progressive
stages is judged from the actual questions/criteria by the independent reviewer,
not rejected solely because IDs repeat. Legacy frozen lesson contracts remain.

Before reviewing new generated drafts, malformed optional evidence groups are
removed: single examples, repeated alternatives, empty strings or copies of the
criterion. Valid alternative groups and all criterion descriptions remain intact.
The instructor sees an explicit note describing these omissions. Published and
student-session rubrics are not rewritten.

Typed, editable quality-mode drafts are no longer discarded by the legacy
quiz/practice repair path when configuration checks find issues. Prepare returns
the draft with failed review status and specific findings; it does not spend an
additional semantic-review call until those structural issues are fixed. The
instructor can edit/save the draft. Publication still requires structural and
independent content review to pass and never accepts a failed draft as approved.


## Semantic review and scoped repair (November 17, 2026)

Investigation followed `platform_app/workspace.py` document preparation through
`platform_lessons.prepare`, `main._document_plan`, `design_objectives`,
`generate_learning_plan`, `edumind_quiz.generate_quiz`, `review_plan`, publishing,
and `LessonPreview`. Existing authoring already forwards instructor boundaries
and the selected source text. Numbered passages cover that text; authoring does
not use the student-runtime nearest-neighbor retrieval path. Exact citation
membership therefore proves provenance, not that an answer follows from evidence.

The independent reviewer already checked content, not just JSON, and publication
forced a fresh review before writes. Gaps remained: no explicit prerequisite,
quiz-progression, factual-support or rubric-discrimination verdicts; no automatic
component repair on semantic failure; cached passes had no evaluator version;
and the review UI printed machine passage references as assessment settings.

`InstructionalReview` now requires these four additional judgments. The same
review request identifies allowed component keys and concrete findings. Only a
semantic failure with valid targets can trigger `review_and_repair`: one request
replaces the named questions, application stages, objective rubrics, teaching
assets, task or introduction. Instructor source, prerequisites, outcomes and
objective descriptions cannot be changed. IDs and mappings are preserved.
Schema and configuration checks run before a fresh full semantic review. There
is no recursive retry. Missing targets, unavailable providers, invalid patches
and unresolved issues return an editable, failed original draft; publishing
still forces review and never automatically rewrites instructor edits. A passing
first review adds no repair calls; a failed review adds at most two calls.
Review cache version 2 invalidates older passes.

Generation explicitly constrains personal-experience assumptions and requests
observable partial-versus-strong reasoning criteria. Citations retain their
internal exact passage references but review shows the available document title
and a complete supporting passage. Missing page/section metadata is not inferred.
The fallback reading title preserves the supplied filename.

Verification: 97 focused backend tests passed, including review failure flags,
scoped repair, retry bounds, protected inputs and cache migration. The source
and topic parameterization includes Scrum and ecology; these are mocked-provider
control-flow tests, not evidence of live model quality. Frontend coverage verifies
readable source display. FastAPI tests require execution outside this Windows
sandbox because asyncio socket-pair initialization stalls inside it.

Limitations: semantic judgments remain fallible model evaluations. No live model
generation or blinded instructional-quality evaluation was run in this change.
Selected material is still bounded by the existing 30,000-character contract;
missing source coverage must be reported rather than invented. Accurate page or
section citations require preserving extraction metadata through the upstream
material-selection contract; this patch does not invent that metadata or change
the published lesson schema. Legacy lessons without quality mode retain their
existing behavior.
