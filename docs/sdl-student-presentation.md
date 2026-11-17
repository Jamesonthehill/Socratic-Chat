# SDL student learning presentation

The student workspace renders the existing attempt and learning_state; submission,
turn IDs, retries, evaluation and persistence still use the same transport.

## Duplication root cause

Bounded-flow tutor messages serialize `Scenario: ...`, `Application part N of M`,
and `Interview question N of M` instruction envelopes into conversation history.
LessonWorkspace also rendered an application-task card and a current-question card,
so the same question and scenario could appear through multiple independent paths.
ChatMessage additionally gave every paragraph its own rounded bubble. Fixed-height
messages and a viewport-height current-turn placeholder added nested scrolling and
large gaps.

## Presentation mapping

- `learning_state.current_application` / `current_interview` owns the active prompt.
  ActiveQuestion renders it once inside the answer form, which retains the exact
  question_id and action payload.
- presentTutorMessage recognizes only the existing server-generated envelopes.
  It converts earlier prompts into history cards, omits the matching active prompt,
  and leaves feedback, hints, unknown prose and Socratic questions intact. The saved
  messages are never mutated. Unexpected or incomplete envelopes remain visible.
- During application, ScenarioCard owns the task context. Exact duplicate fields
  are consolidated. Outside application, the original scenario remains in history.
- Tutor paragraphs share one message body. Student responses and feedback have
  distinct treatments. Quiz hints/readings/options retain their existing handlers.
- The bounded workspace uses document scrolling, without the chat's independent
  fixed-height viewport or blank turn spacer. Application progress is derived from
  saved answer counts; it does not affect grades.
- CSS is limited to the SDL student wrapper and uses theme colors. Other tools and
  instructor screens are unchanged.

## Verification

Component regression tests cover all three application parts with correct IDs,
only one active prompt/scenario, preserved history, both interview questions,
completion, reloading saved completion, retry UI, and malformed-envelope fallback.
Browser review uses the real LessonWorkspace with local synthetic attempt data;
no production student records are created or modified. Light and dark views and
all three application parts were inspected. A real signed Canvas launch and live
LLM grading are outside this UI verification.

No new questions, praise, scores or hints are synthesized by the frontend. The
short-answer backend does not currently accept hint actions, so the redesign does
not add a nonfunctional short-answer Hint button. Existing quiz hints stay available.

## Study readings and student turns

The generated Selected course materials / Instructor course materials resource is
an internal fallback marker with no URL, not an authored reading. The student UI
resolves that marker to assignment file downloads rather than displaying generic
description/focus metadata. Authored readings remain visible. During Study, the
reading list appears in the main learning area once; other stages retain the
sidebar readings. Missing files are reported honestly instead of claiming that
material is included. Existing lesson snapshots need no regeneration.

Student replies use right-aligned blue bubbles with white text, including short
control replies such as Read more. Tutor instructions keep the structured layout.
Light and dark views were visually checked with the real workspace component.
