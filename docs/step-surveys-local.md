# Local step surveys

In a published Socratic or Reflection assignment, open Settings and find **Step surveys**.
Choose a learning step (or Reflection sub-topic). Use **Generate step survey**, review/edit the
questions, and choose **Save survey draft** or **Publish survey**. Manual question entry also works.
Draft generation uses the existing setup model only when requested.

Students who have started the assignment can choose **Quiz / Survey**. The first version collects
ungraded confidence ratings (1–5) and written reflections. Future Socratic steps are not exposed.
The survey never changes quiz state, grades, step readiness, messages, or completion status.

In **AIducate**, select the course and assignment, choose **Run analysis**, then **Step surveys**.
Results are grouped by step and published survey version, with original questions and responses.
Confidence is self-reported, not a mastery assessment. AI theme/emotion analysis and Canvas survey
imports are not included in this version.

Publication creates a new version. Earlier responses retain their exact question snapshot.
Saving a draft leaves the previously published version available. Submissions are idempotent;
a changed publication requires the student to reopen the survey before submitting.

Storage reuses assignments_platform.config.step_surveys and
assignment_attempts_platform.engine_state.step_survey_responses. No new tables or migrations.
Instructor access requires management of the course; students must be approved recipients.

Validation uses isolated PostgreSQL integration tests and mocked model calls. No AI provider
requests are needed to run the tests. The feature reuses existing JSON fields and needs no
new database tables or migrations. Local model-provider settings are not part of this release.
