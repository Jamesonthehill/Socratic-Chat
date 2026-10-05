# Socratic-Chat code walkthrough for a professor

This guide follows the **local-socratic-chat/Socratic-Chat** project. It explains the
important executable statements in their call order, while the adjacent comments
in the source files explain why each non-obvious branch exists. This is a code
walkthrough, not proof that any particular hosted deployment has these settings.

## Start here: what each file owns

| File | Responsibility | What it does **not** do |
| --- | --- | --- |
| `backend/app/__init__.py` | Marks `app` as the Python package imported by the server. | It does not run the teaching pipeline. |
| `backend/app/main.py` | FastAPI routes and the orchestration order for each request. | It does not contain the whole search or scoring algorithm. |
| `backend/app/auth.py` | Issues and verifies signed, expiring session tokens. | A token alone does not grant instructor/course permission. |
| `backend/app/db.py` | PostgreSQL schema, reads/writes, course membership checks, and hybrid SQL search. | It does not decide which teaching question to ask. |
| `backend/app/chunking.py` | Converts structured document text into bounded, labeled passages. | It does not generate embeddings or student replies. |
| `backend/app/rag.py` | Text extraction, embeddings, retrieval filtering, and model-based response generation. | Its search rank is not a learning score. |
| `backend/app/classifier.py` | Interprets student intent, question shape, concepts, and temporary support need. | Its `understanding_level` is not the stored mastery percentage. |
| `backend/app/answer_evaluation.py` | Checks eligible answers against the previous tutor question and course evidence. | It does not score every user message. |
| `backend/app/socratic.py` | Chooses the teaching move and how much explanation to reveal. | It does not store scores or search PostgreSQL itself. |
| `backend/app/schemas.py` | Validates API request and response shapes. | It does not execute business decisions. |
| `backend/app/settings.py` | Reads provider, model, database, auth, and logging configuration. | A default value here does not prove the live deployment uses it. |
| `backend/app/pipeline_logging.py` | Gives a chat request one trace ID and records stage events. | Routine logs are not the conversation database. |
| `frontend/app.js`, `index.html`, `styles.css`, `config.js` | Browser UI, authentication screens, course/chat interactions, and API endpoint selection. | The browser does not determine course permission or mastery. |

`backend/data/raw_docs` is a local source-document workspace. `backend/storage`
can contain local pipeline logs and optional prompt snapshots. `docs` contains
explanatory/generated material, not the live PostgreSQL search index. The
`tools` scripts are maintenance/inspection utilities, not an automatic stage
in every student chat request.

In the screenshot, `.venv` contains installed Python dependencies and `.idea`
contains editor settings; neither implements chatbot decisions. `README.md`
explains setup, and `render.yaml` describes one hosted deployment configuration.

### One-sentence explanation

The instructor publishes course evidence; PostgreSQL stores and searches its
chunks; the student asks within an approved course; the backend interprets the
message, retrieves evidence, optionally evaluates demonstrated understanding,
chooses a Socratic teaching move, generates a grounded reply, and saves the turn.

### Authentication and access before the AI pipeline

1. `main.py` accepts the configured sign-in method. In restricted school mode,
   `_verify_google_credential()` verifies the Google token and permitted school
   domain; onboarding and an optional GitHub connection may also be required.
   Password login is available only when configuration permits it.
2. `auth.issue_session()` makes a signed token containing user ID and expiry.
   `auth.verify_session()` checks its HMAC signature and expiration on later
   requests. This is application authentication; it does not imply Canvas LTI.
3. `_current_user_id()` checks that the account still exists and satisfies
   onboarding/GitHub requirements. `_require_authority()` checks administrator
   or instructor roles. `_require_course_access()` checks the membership of the
   **specific course** before chat or document operations.
4. The instructor creates a course; a student requests access; the instructor
   approves or rejects the request. A pending request is not chat permission.

These checks happen before retrieval. Even a perfect vector match from another
course must not be visible to an unapproved student.

## 1. Whole-application path

### A. Instructor prepares a course knowledge base

| Code to point at | What it does | Why it exists |
| --- | --- | --- |
| `frontend/app.js`: course creation and upload requests | Sends the instructor's course and files to FastAPI. | The browser is an interface, not the authority on course access. |
| `main.py`: `upload_course_documents()` → `_require_course_access(..., manage=True)` | Verifies that the caller manages the course. | Students must not publish evidence for their own tutor. |
| `main.py`: `db.save_rag_file(...)` | Stores original file bytes and course ownership in PostgreSQL. | The indexed chunks remain traceable to their source file. |
| `rag.py`: `ingest_file()` → `read_document()` / `read_pdf_pages()` | Extracts text according to file type. | An embedding model needs text, not raw PDF/HTML bytes. |
| `chunking.py`: `chunk_document()` | Parses headings and blocks, then groups them into size-limited chunks. | Retrieval should return a coherent passage rather than an entire large file. |
| `chunking.py`: section/assignment boundary check | Starts a new chunk when the section or assignment changes. | Assignment 1 requirements should not be mixed with Assignment 2. |
| `rag.py`: `create_embeddings()` | Converts each chunk into a numeric vector. | The system can search by meaning as well as by exact words. |
| `db.py`: `replace_document_chunks()` | Writes chunk text, metadata, embedding model, and vector to `document_chunks`. | PostgreSQL becomes the searchable knowledge base. |

Deletion follows `main.py` → `db.delete_course_document()`. The database's
`ON DELETE CASCADE` relationship removes the deleted file's chunks too, so
future searches cannot retrieve them.

The `document_chunks` table contains `chunk_index`, optional `page_number`,
`chunk_text`, JSONB `metadata` (including section path and assignment number),
the embedding model name, a pgvector `embedding`, and a generated PostgreSQL
`text_search` vector. Its vector and text-search indexes support two different
retrieval methods. The original file's bytes remain in `rag_files`; a disk copy
used during extraction is not the source that ordinary SQL search reads.

### B. Student asks a question

1. `frontend/app.js` sends `message`, `course_id`, `conversation_id`, recent
   `history`, and `top_k` to `/api/chat/stream`. Streamed status events update the
   loading indicator; the final event contains the actual reply.
2. `main.py` calls `_require_course_access()`. This prevents an unapproved
   student from searching another course's material.
3. `main.py` loads saved conversation history from PostgreSQL and saves the
   student's new message. An existing chat's saved topic takes precedence over
   a topic supplied by the browser.
4. `classifier.py` calls `classify_message()`. It produces structured labels
   such as question type, target concept, dialogue state, next action, and a
   focused retrieval query. Deterministic rules handle protected session
   commands and act as fallback if the model response is invalid.
5. `rag.py` calls `retrieve()`: embed the query, search the course's **published**
   chunks using both vector similarity and full-text ranking, apply relevance
   thresholds, deduplicate, and return up to `top_k` accepted passages.
6. If no passage supports the topic, `generate_answer()` returns a boundary
   message rather than answering from a model's general knowledge.
7. For a supported topic, the backend optionally evaluates the student's
   answer, chooses a teaching strategy, asks the configured model to generate
   a response, saves the assistant message, and returns sources and any score.

PostgreSQL tables have different jobs: `rag_files` stores source files;
`document_chunks` stores searchable text and vectors; `conversations` and
`conversation_messages` store dialogue; `mastery_assessments` stores individual
evaluations; `student_concept_progress` stores the current per-concept estimate.

### What happens inside retrieval

`classifier.py` may rewrite a short or ambiguous message into a standalone
search query, and may supply subqueries for a compound question. `rag.py`
embeds these queries using the **embedding provider**, independently configured
from the chat model. `db.hybrid_search_chunks()` searches published chunks in
the selected course twice: cosine distance over pgvector embeddings and
PostgreSQL full-text `ts_rank_cd` over `text_search`. Reciprocal-rank fusion
combines the two rankings. A relevance gate then requires enough lexical or
semantic evidence before any chunk can become a source. The final selection
deduplicates passages and ordinarily returns up to four (`top_k=4`, configurable
per request). Explicit assignment numbers can filter chunk metadata, reducing
cross-assignment mixing. The search score orders passages; it does **not** say
how well a student understands the topic.

### What is saved, and when

| Event | PostgreSQL record |
| --- | --- |
| Account registration/sign-in | `users` and related verification/link records. |
| Course creation/access request | `courses`, `course_memberships`. |
| Document upload | Original bytes in `rag_files`; text, metadata, vector in `document_chunks`. |
| Chat turn | Thread in `conversations`; student and tutor text in `conversation_messages`. |
| Eligible answer evaluation | One new `mastery_assessments` row plus updated `student_concept_progress`. |
| Temporary missing-context question | `conversation_state` until the clarification is answered/cleared. |

If the evaluator is skipped or fails validation, there should be no new
assessment row for that turn. The UI may then show no score; that is different
from a recorded score of zero.

## 2. Socratic-questioning path, separate from RAG indexing

The Socratic pipeline does **not** train a new language model. It combines
classification, retrieved instructor evidence, an explicit teaching policy,
conditional evaluation, and prompted generation.

| Key statement or branch | Why it is there |
| --- | --- |
| `classify_message()` first computes `_rule_classification()` | There is always a fallback for unavailable/malformed model output. |
| The classifier asks for `target_concepts`, `question_type`, `understanding_level`, and `support_level` | The next teaching action should respond to the student's current turn, not just repeat a generic question. |
| `answer_evaluation_query()` adds the prior tutor question to short answers | “Because it catches mistakes” is ambiguous without knowing what the tutor asked. |
| `should_evaluate_answer()` checks the latest tutor turn and dialogue status | A new question, “I understand,” or “thanks” is not demonstrated knowledge. |
| `evaluate_student_answer()` uses the tutor question, recent dialogue, and retrieved chunks | The judgment is tied to the actual task and course evidence. |
| `validated_evaluation()` calculates `0.2 × concept coverage + 0.2 × semantic alignment + 0.6 × rubric` | The score combines term coverage, paraphrase/meaning, and substantive reasoning. It is not an official grade. |
| `application=None` removes that dimension from the rubric denominator | Do not penalize a student for an application task the tutor never asked. |
| `save_mastery_assessment()` appends the result and updates `student_concept_progress` | We retain both the individual evidence and a running per-concept estimate. |
| `_mastery_progress_update()` uses `0.65 × previous + 0.35 × current` | One unusually strong answer should not suddenly establish mastery. |
| `estimated_mastery >= 80` **and** at least two answers | This triggers a final verification task, not immediate completion. |
| A strong later application answer with no critical misconception | This can mark the concept `mastered` and end that objective. |
| `choose_socratic_strategy()` selects a mode, example type, disclosure level, and question type | Teaching choices can be inspected in code and logs. |
| `_disclosure_instruction()` maps levels 0–4 to increasing help | A new learner gets a short example; repeated difficulty can receive a clear explanation. |
| `socratic_system_instruction()` builds the teaching prompt | It asks for grounded, concise feedback and one focused next question. |
| `generate_answer()` forwards the model's reply without rewriting it | The prompt is a behavioral instruction, **not** a guaranteed output validator. |

The policy has important exceptions. A direct information request may get a
direct answer. A bare claim of understanding triggers a teach-back or prediction
check. Uncertainty gets a smaller clue; repeated difficulty gets a simpler
explanation and example. A clear closing is handled without another question.

### A single Socratic turn in detail

1. **Classify.** The rule-based result is calculated first. The configured LLM
   can return a strict JSON object with `route`, `question_type`,
   `target_concepts`, `conversation_state`, `dialogue_status`,
   `conversation_action`, `understanding_level`, `support_level`, and search
   wording. Invalid/missing labels are constrained by allowlists and fallback
   rules. A model is used for nuanced interpretation, but session commands and
   selected safety/continuity rules remain code-controlled.
2. **Route.** Closing, operational questions, clarification, and explicit
   topic changes can return before the ordinary RAG/teaching path. A chat's
   original learning topic is recovered from saved history; a clearly unrelated
   new primary topic is directed to a new chat.
3. **Retrieve.** Course-scoped hybrid search supplies the factual basis. A new
   concept question normally has no answer evaluation yet. A short answer to a
   previous tutor question gets that question included in its search query.
4. **Evaluate conditionally.** Only a substantive student response to a tutor
   question with supporting course evidence is eligible. The evaluator returns
   accepted concepts, semantic alignment, four 0–4 rubric dimensions,
   misconception information, and feedback. Code computes the 0–100 score:
   `20% concept coverage + 20% semantic alignment + 60% normalized rubric`.
   `application=NULL` means no application task was asked; it is excluded from
   the rubric denominator. A critical misconception caps the score at 59.
5. **Update progress.** An eligible score is appended to
   `mastery_assessments`. `student_concept_progress` combines the old estimate
   and new score as `0.65 × previous + 0.35 × current`. At least two assessed
   answers and an estimate of 80+ produce `ready_for_verification`, not
   `mastered`. A later strong, correct application answer can complete the
   concept. These numbers guide tutoring; they are not official grades.
6. **Choose the teaching move.** `socratic.py` considers the classification,
   evaluation, retrieved evidence, prior tutor questions, and established
   scenario. It selects direct explanation, a diagnostic example, comparison,
   smaller clue, correction, explanation-then-check, or transfer check.
   Disclosure levels 0–4 specify how much explanation is permitted. The
   scenario anchor keeps the example consistent across turns.
7. **Generate and save.** `rag.py` constructs a prompt with course-evidence
   boundary, teaching decision, response format, retrieved chunks, and recent
   dialogue. The model reply is forwarded without a final answer-rewriter.
   The assistant message is saved so the next student answer has context.

For example, “What is code review?” should be classified as a new concept,
retrieve relevant course chunks, and start with a brief grounded situation plus
one question; it should not create a learning score yet. If the student answers
that question, the evaluator may create a score and specific feedback before
the next guided question. If the student says “I still don't understand,” the
policy should increase support instead of repeatedly withholding an explanation.

### Failure and observability paths

- No relevant document chunk: respond that the topic is outside the published
  course documentation rather than silently substituting general knowledge.
- Classifier unavailable/invalid: use deterministic classification rules.
- Evaluator unavailable/invalid: record **no score** for that turn, not zero.
- Generation provider unavailable: return a student-facing fallback message;
  the exact response depends on whether evidence was found.
- `pipeline_logging.py` gives each chat request a trace ID and numbered events
  spanning classification, retrieval, evaluation, strategy, model request, and
  final response. The streaming endpoint maps selected events to the loading
  indicator. Routine logs omit full student text; optional full prompt/result
  snapshots require an explicit setting and need careful handling because they
  contain course and conversation content.

### Local versus hosted configuration

The checked-in local defaults select Ollama for chat and embeddings. The
checked-in `render.yaml` selects Groq GPT-OSS 120B for chat roles, while
embedding selection is a separate setting. Actual Render environment variables
may override either. The presence of the OpenAI-compatible Python client does
not prove OpenAI is the provider: it is also used with compatible Ollama and
Groq endpoints. Verify the running provider through deployment settings and
pipeline logs rather than inferring it from one import.

This local repository's backend does not implement the separate CourseLab
Canvas/LTI import flow discussed elsewhere. Do not present Canvas import as a
stage of this exact code path unless you are showing that other project.

## 3. Where to show the professor the code

Open these files in this order during a demonstration:

1. [`frontend/app.js`](../frontend/app.js) — find `formEl.addEventListener("submit"` and `postChatStream`.
2. [`backend/app/main.py`](../backend/app/main.py) — find `upload_course_documents` and `_run_chat_pipeline`.
3. [`backend/app/rag.py`](../backend/app/rag.py) and [`backend/app/chunking.py`](../backend/app/chunking.py) — show ingestion, embeddings, and retrieval.
4. [`backend/app/classifier.py`](../backend/app/classifier.py) — show the student-intent labels and fallback.
5. [`backend/app/answer_evaluation.py`](../backend/app/answer_evaluation.py) and [`backend/app/db.py`](../backend/app/db.py) — show when a score is produced and stored.
6. [`backend/app/socratic.py`](../backend/app/socratic.py) — show how the teaching move and disclosure level are selected.
7. [`backend/app/rag.py`](../backend/app/rag.py) — return to `generate_answer` for the final grounded prompt and reply.

`settings.py` selects local or hosted providers through environment variables.
Do not claim that a specific deployed server uses Ollama, Groq, or OpenAI solely
from this folder; inspect that server's actual environment and logs first.
