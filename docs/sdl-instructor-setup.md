# SDL instructor lesson setup

The CreateActivity SDL settings use SdlLessonSetup's four numbered sections:
learning focus and optional concepts; optional prior knowledge; optional end goal;
and optional instructor-only teaching instructions. Existing prompt,
custom_questions, starting_point and ending_point values keep their storage keys.
The additional_instructions JSON config field defaults to empty for old drafts.
No database migration is needed.

Missing boundaries use a separate suggest-sdl-boundaries gateway action and a
trusted internal suggest-boundaries endpoint. Both confirm instructor/service
access. The model returns only two validated text suggestions, preserving any
provided value exactly. Suggestions are not written into the draft or used to
generate a lesson. The UI displays editable proposed values and requires Confirm
lesson details; Review activity then generates the lesson in a separate action.
Changing the scope/material selection discards outstanding suggestions. Drafts
can be saved with blank boundaries. Failed suggestions leave authored inputs
unchanged, so instructors can enter them manually or retry.

The gateway refuses lesson preparation until both reviewed boundaries are present,
preventing a silent fallback to the legacy assessment. Confirmed values select the
existing short assessment: three quiz questions, three application sections and
two interview questions. No grading, student sessions or evaluation routes change.

Teaching instructions are forwarded separately from source material to quiz and
lesson authoring. They are not appended to approved_material, stored on the student
lesson plan, copied into the assignment description, or exposed by the student
assignment response. The authoring prompts apply preferences without quoting the
notes. Generated student content remains subject to instructor review.

Verification includes full frontend tests, instructor create/review integration,
suggestion validation and error fallback, preserved supplied values, private-note
transport, gateway access and confirmation guards, and existing generation and
3-3-2 flow regressions. The real CreateActivity component was visually inspected
using local synthetic course data. Live provider responses and signed Canvas
launches are not exercised by these tests.

## Coverage-link generation and repair

New short-assessment schemas constrain application section IDs to identify,
decide and apply and constrain coverage references to the actual generated quiz
IDs plus those three section IDs. This prevents invented cross-reference names
in constrained model output.

Previously the validation repair path only generated quiz/practice repairs. It
could not fix coverage_requirements, even when that was the sole validation
failure. It now first requests a focused mapping from the exact instructor
requirements to the existing questions (including options) and application
prompts with their shared scenario. The schema permits only real task IDs.
Question text, answer keys, rubrics, requirements and assessment counts are not
rewritten by this repair. The original draft is not mutated.

The mapping request may return an empty list for an outcome that is not assessed.
That remains a blocking error naming the outcome and asking for narrower scope
or a revised assessment. The frontend does not invent links or disable coverage
validation. Mapping relevance is still model-assisted; structural validation
alone does not independently prove semantic coverage.

The optional material-expansion section is temporarily removed from the instructor
form. Existing stored additions and backend expansion support remain intact.
