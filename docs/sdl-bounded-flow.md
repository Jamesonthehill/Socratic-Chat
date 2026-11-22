# SDL lesson boundaries and completion

Open Self-Directed Learning in the professor workspace and choose **Create SDL activity**.
This uses Geonwoo's existing tool route and course membership controls; no Canvas
launch is required. The existing standalone instructor app remains available.
On the SDL activity form, select the existing shared RAG documents and enter
**Starting point** and **Ending outcomes**. Review activity generates the topic,
assumed prerequisite knowledge, verified prerequisite readings, lesson content,
three questions with distractor misconceptions, and one application scenario with
three short-answer sections (identify, decide, apply).
Review prerequisite assumptions and edit their topic/link fields before publishing.
The scenario, section titles/prompts, and application assessment rubric are editable too.

For sparse source material, the instructor can optionally select **Expand this
material** after selecting indexed files and defining the starting point and
ending outcomes. One model call drafts missing explanations and a worked example;
it does not search the internet, invent citations, or generate the assessment.
Ambiguous scope is returned as a clarification error rather than guessed.
The instructor can edit the additions, approve them for accuracy/scope, or remove
them. Editing additions clears approval in the UI. They are saved with the draft.
Source text and scope are hashed so changed documents/outcomes cannot reuse an
old approval. Preparation and publishing enforce approval and source binding;
changed additions require preparing the lesson again before publishing.

Approved additions are combined with the source before lesson generation, then
stored as `supplemental_material` in the frozen lesson. Students can read them
under **Additional lesson material** throughout the activity. Generation, study
help, application assessment and interview generation use the same combined
approved teaching material. Older lessons without additions are unchanged.
New drafts also map each application section to explicit learning objective IDs
and expected reasoning criteria. Instructors can edit these before publishing.
Publication checks require valid mappings, nonblank criteria, and coverage of all
learning objectives. These checks apply to `assessment_grounding_version: 1`;
older published snapshots keep their original validation rules.

Students confirm prerequisites, study the main topic with examples/readings, and
answer three questions. Each question permits three attempts. Incorrect answers
offer readings and a hint with a related worked example. Correct answers, or a
third incorrect attempt, reveal the explanation and advance. Assistance requests
do not consume attempts or deduct points. Quiz score counts correct first
attempts; saved quiz history retains every attempt and assistance request.

After the quiz, students answer three application sections individually. Each
submitted answer is saved, with substantive feedback withheld until the interview
is finished. A couple of sentences or bullets is enough for each section.
The interview generates exactly two questions from these answers: justify a
specific decision, then consider a changed scenario condition. Students answer
each briefly. The grader evaluates application and interview evidence together
against the application rubric and ending outcomes, crediting valid clarifications.
Section reasoning criteria are supplied to grading but hidden from student views.
Completion records participation rather than claiming mastery.

New interview questions include a purpose, source application section ID, and an
exact quotation from that student's answer. Local validation checks the reference,
quote, distinct purpose order (justification, changed condition), nonblank changed
condition for the second question, and repeated prompts. The server renders the
verified quote and changed condition rather than trusting the model to display
them. Invalid generated interviews use the existing saved-answer retry path.
Saved interviews containing older string questions remain readable.
These are structural and provenance checks, not a separate AI semantic review;
they cannot prove that a paraphrase interprets the answer correctly or that two
differently worded prompts are semantically distinct.

If interview generation or final grading is unavailable, all submitted answers
remain saved and the student selects Try again without retyping. Pause/resume
and turn-ID retry deduplication continue to apply. Stale section/question IDs are
rejected. No extra interview rounds are added automatically.

This sequence applies to newly prepared platform lessons (`bounded_flow: true`,
`assessment_version: 2`). Counts are defined in `app/assessment_flow.py`.
Previously published lessons and saved attempts retain their original flow.
Plans without an assessment version default to version 1 (five quiz questions,
one application response, no interview). Re-prepare an unpublished draft to get
the new structure; existing content is not silently truncated or converted.
No new database migration is needed: lesson snapshots, attempt state and the
existing task submission/completion columns store the additional data.

Generation still requires a configured AI provider and network access for reading
verification. Unit/API tests simulate authoring and grading; validate generated
content with real course materials before publishing to students.
