# Professor reflection analysis

Open `/platform/professor/reflection-analysis` using a professor account. The
**Reflection analysis** link sits immediately after **Professor dashboard**.
The existing AIducate participation viewer remains available.

This is a native CourseLab adaptation of the workflows in
`/Users/das/nikole_reflection_app/reflection_analysis`:
`https://github.com/NicoleWiktor/reflection_analysis`, source commit
`8a7044c6b69d75eb6a8b6bf996efc7ef59227d04`. The topic annotation prompt in
`platform_app/prompts/reflection_topic_analysis.json` is copied from its
`application/model/prompts/topic_analysis.json`. Other code is implemented
against CourseLab's authenticated API and React interface. No source datasets,
environment files, or credentials are imported. Streamlit is not required.

## Workflow

1. Load saved student messages from a Reflection assignment you manage, or
   upload CSV/TSV data. Assignment data includes saved work in progress and
   excludes students with no responses. The existing assignment endpoint
   enforces instructor course membership before returning student records.
2. For a file, map student ID, optional name and percentage grade, and one or
   more response columns. Inspect the preview before importing. The template
   download shows a supported format. To use a separate gradebook, first join
   its numeric percentage grade into the reflection CSV by student ID.
3. Supply course context if useful, then run topic analysis in explicit batches
   of up to 50 reflections. Successful annotations stay available if another
   reflection fails. The next batch retries failures and includes remaining
   records. Course context is locked after the first successful analysis;
   reloading the dataset starts a new analysis.
4. Review topic frequencies, unresolved challenges, and class/topic/student
   summaries. Search and filter by topic, urgency, unresolved challenges, and
   supplied grade range. Missing grades are excluded when a grade filter is set.
5. Download prepared CSV, annotation CSV (one row per reflection/topic), complete
   or filtered HTML reports, or an individual student report.

Data cleaning trims whitespace, retains leading zeros, skips empty IDs and
responses with notes, reports duplicate IDs without merging their reflections,
and ignores invalid grades with a note. Malformed rows and ambiguous headers
are rejected. Imports are limited to 2 MB, 100 columns, and 5,000 rows.

## Configuration and boundaries

The service uses CourseLab's existing `settings.llm_client_config("generation")`
and provider token settings. There is no separate API key field in the browser.
The model receives response text and course context; ID, name, and supplied
grade fields are not included in the model request. Text supplied inside a
response can itself contain identifying information.

All new endpoints require professor access. Model annotations are validated
against the original topic labels, urgency enum, resolution enum, and matching
topic/resolution list lengths. Provider failures are returned as per-reflection
errors without provider response details or credentials. Each request accepts
up to 120,000 response characters, each reflection up to 16,000 characters,
and model calls have a 45-second timeout with at most five concurrent calls.

Class and topic summaries aggregate successful annotations. Student summaries
and instructor suggestions come from the model. Supplied grades are summarized
without inventing missing scores. AI output requires instructor review.

The workspace survives switching routes within the professor interface, but
refreshing or closing the page clears it. Download results before leaving.
There are no new database migrations or server-side saved analysis files.
This adaptation does not include the original filesystem folder manager,
arbitrary JSON converters, custom prompt file picker, separate gradebook
uploader, emotion reports, or statistical significance tests.

## Validation

```sh
.venv/bin/python -m pytest tests/test_reflection_analysis.py -q
cd platform_frontend
npm test -- src/reflection-analysis.test.jsx src/platform.test.jsx src/instructor-summary.test.jsx
npm run build
```

Tests cover file import edge cases, invalid model annotations, partial failures,
professor/student/unauthenticated API access, assignment loading, explicit CSV
column selection, summary filters, route/navigation access, and safe exports.
Model calls are mocked in automated tests; these tests do not measure live
provider quality.

Implementation validation also included one live generation call with a
synthetic reflection about struggling with Python loops. It returned a valid
`python_and_coding`, `unresolved`, `medium` annotation. No real student data was
used for this check. The local preview returned HTTP 200 for the page and HTTP
401 for an unauthenticated configuration request. Visual browser validation
has not been completed.
