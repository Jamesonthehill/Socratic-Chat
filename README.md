# Socratic-Chat

A clean personal workspace for a retrieval-augmented chatbot.

The backend indexes course documents with local Qwen embeddings, retrieves relevant
PostgreSQL chunks, and runs student-state classification, conditional learning
evaluation, and grounded Socratic responses locally through Ollama. The default
local model is Qwen3.5 9B Q4_K_M, with Qwen3 Embedding 0.6B for local semantic
retrieval. No hosted model API key is required.

## Setup

```bash
cd Socratic-Chat
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
```

Install Ollama, pull the selected 6.6 GB Q4 model, and keep Ollama running:

```bash
ollama pull qwen3.5:9b-q4_K_M
ollama pull qwen3-embedding:0.6b
ollama serve
```

The conversational roles use this local configuration:

```env
LLM_PROVIDER=ollama
OLLAMA_API_KEY=ollama
OLLAMA_API_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODEL=qwen3.5:9b-q4_K_M
OLLAMA_CLASSIFIER_MODEL=qwen3.5:9b-q4_K_M
OLLAMA_ANSWER_EVALUATION_MODEL=qwen3.5:9b-q4_K_M
```

`OLLAMA_API_KEY` is only a placeholder required by the OpenAI-compatible client;
the local Ollama server ignores it. No hosted chat API key is required.

Document ingestion and dense semantic retrieval use `qwen3-embedding:0.6b`
locally with its native 1,024-dimensional vectors. PostgreSQL validates this
dimension at startup; changing embedding models requires re-indexing old chunks.
Restart the backend after changing provider variables.

To switch conversational roles to a hosted provider later, set the matching
provider variables. For OpenAI:

```env
LLM_PROVIDER=openai
OPENAI_API_BASE_URL=https://api.openai.com/v1
RAG_MODEL=gpt-4.1-mini
```

Hybrid retrieval applies a relevance gate before any answer or Socratic example
is generated. A chunk is retained when PostgreSQL full-text search finds lexical
evidence or its absolute cosine similarity reaches `RAG_MIN_DENSE_SIMILARITY`
(default `0.42`). Rank-fusion scores decide the order of retained chunks; they
are not treated as proof of relevance. If every candidate is rejected, the
pipeline returns the grounded “not found in uploaded notes” response without
calling the generation model. Tune the threshold against a labeled set of
course questions rather than lowering it simply to force results.

## Socratic questioning pipeline

Each learning message passes through a hybrid interpretation stage before RAG
retrieval. Session commands, access checks, and safe fallbacks remain
deterministic. The configured conversational model then returns validated labels
for the student's intent, question type, target concepts, current demonstrated
understanding, required support level, dialogue status, next conversation action,
and a focused retrieval query. For a compound question, it can also provide up
to three standalone subqueries. Each subquery runs through the same course-scoped
hybrid search and relevance filter; retrieved chunks are deduplicated and
selected across the question's parts before answer generation. A single-topic
message keeps the original one-query path. The status distinguishes
ordinary learning, a substantive claim asking for confirmation, a bare claim of
understanding, acknowledgement, topic change, and a request to close. Invalid
JSON, unsupported labels, or a provider failure automatically falls back to the
rules.

Operational chat requests—such as listing published documents or asking for the
course title—are selected from the classifier's structured `operational_request`
field. They are no longer detected by loose keyword combinations such as
`files + have`. Ordinary mentions of files, folders, documents, or unrelated
topic words proceed through classification and RAG. Unsupported topics are
rejected by configurable sparse and dense retrieval thresholds rather than a
fixed list of words, and the generator is instructed to use only retrieved
instructor-published evidence. Unsupported requests receive a short boundary
message instead of an answer from the model's general knowledge.
Classification uses strict JSON Schema output to keep these semantic routes
reliable.

After retrieval, the teaching policy chooses one explainable action. A new
concept begins with a short document-grounded example and one discovery
question; comparisons use contrasting cases; procedure, application, and
debugging requests use an incomplete scenario. Uncertainty or an explicit hint
request increases disclosure. Repeated difficulty raises the classifier's
support level and produces a clear explanation plus a simpler, meaningfully
different example; continued difficulty permits a step-by-step example. The tutor prompt
asks for limited disclosure and one focused question, but model replies are shown without
post-generation rewriting. A substantive claim is intended to receive a short grounded
`Yes—`/`Partly—`/`Not quite—` check before one revision question. A bare “I
understand” receives a transfer or teach-back check instead of unearned praise.
Acknowledgements and clear endings are routed to a short, question-free response
instead of another Socratic prompt.

Question categories remain internal planning labels. Student-facing questions
use plain language and name a concrete action, choice, example, or outcome from
the current topic rather than canned stems such as `What evidence?` or `What
factor?`. A substantial pasted passage is intended to receive one neutral reflection before
the question. These are model instructions; no response validator replaces a generated reply.

Substantive responses to tutor questions pass through a separate hybrid answer
evaluator. It calculates deterministic course-concept coverage (20%), model-based
semantic alignment (20%), and a grounded rubric for correctness, completeness,
reasoning, and application (60%). Application is stored as `NULL` and excluded
from the rubric denominator when the tutor did not ask for transfer or application;
zero now means application was requested but not demonstrated. The evaluator also
compares recent responses and records whether understanding improved. Retrieval rank is never used as a learning
score. The evaluator uses the preceding tutor question as part of retrieval so
short replies remain attached to the correct topic. Questions, acknowledgements,
requests for help, and unsupported topics are not scored.

Each eligible assessment is appended to `mastery_assessments`, while an
exponentially weighted estimate and evidence count are stored in
`student_concept_progress`. An eligible answer scoring at least 80 completes
the teaching sequence without another verification question. The tutor gives
final feedback, corrects any identified misconception, resolves the original
scenario, and answers the student's opening question in a saved summary. The
student can then submit the completed chat; the summary and submission time
remain available when the chat is reopened. Submitted chats are read-only and
cannot be deleted by the student. Critical misconceptions cap the
assessment below 80. Scores are adaptive tutoring signals, not official grades.

The evaluator uses strict JSON Schema output. Empty or incomplete
evaluator responses are rejected and logged instead of being converted into
zero-score database records. The persisted conversation concept is reused for
follow-up answers so a short reply cannot be stored under a generic `current
concept` key.

Set `CLASSIFIER_ENABLED=false` to use deterministic classification only.
`OLLAMA_CLASSIFIER_MODEL` and `OLLAMA_ANSWER_EVALUATION_MODEL` can override the
local model for those roles. Set `ANSWER_EVALUATION_ENABLED=false` to disable
adaptive assessment.

These are three logical LLM roles: student-state classification, conditional
learning-progress evaluation, and grounded response generation. The evaluator is
skipped for a new topic, acknowledgement, unsupported request, or other message
that does not demonstrate an answer to a tutor question.
Classifier concept labels are inferred from the current message and conversation;
they are not a fixed list of course topics. Retrieved instructor documents supply
the factual content for tutor answers.

## Pipeline Logs

Set `DEBUG_PIPELINE_LOGS=true` to record an end-to-end trace for every chat turn.
Logs are written to `backend/storage/pipeline.log` as well as the server console.
Every event includes a request `trace_id`, numbered pipeline stage, conversation
ID, and cumulative `elapsed_ms`. Use the trace ID to follow one request from
`chat_received` through `response_returned`. Log files rotate at 10 MB and retain
five backups. Message and prompt digests are non-reversible; displayed previews
redact email addresses and secret-like values.

Set `LOG_FULL_PROMPTS=true` to additionally save the exact request sent to each
LLM stage. Pretty-printed JSON snapshots are written under
`backend/storage/pipeline_prompts/`, grouped by the same trace ID and labeled as
`classifier`, `answer-evaluation`, `tutor-generation`, or
`conversation-transition`. Completed learning chats add a `learning-completion`
snapshot. These local files contain the complete system
instructions, conversation history, retrieved document passages, and student
message. After each model call finishes, the same snapshot records the raw model
response, parsed classifier or evaluator result, unchanged tutor answer, and
model latency. They are excluded from Git and created with owner-only
permissions.

Run the local trace viewer to inspect this automatically instead of opening the
JSON files individually:

```bash
.venv/bin/python tools/trace_viewer.py
```

Open `http://127.0.0.1:8765`. The page groups all model calls from one chat turn
under its trace ID and refreshes every three seconds while the pipeline runs.
Open a phase's **Exact messages sent to Qwen** section to inspect its full prompt.
Use **Copy request** on a phase to copy its full JSON request, including model
settings and every message.
Use **Delete trace** beside a selected trace to remove only that trace's local
prompt snapshots after confirmation. This does not delete the chat conversation
or the rotating pipeline log. Use **Traces** to fold or reopen the sidebar; on
small screens it opens over the page and closes when you tap outside it.

## Add Documents

Put `.txt`, `.md`, `.pdf`, `.tex`, `.html`, or `.htm` files in:

```text
backend/data/raw_docs/
```

Then start the backend and press **Scan documents** in the UI.

### Chunking behavior

Instructor uploads are split by document structure before retrieval. HTML and
Markdown headings become section boundaries, paragraphs remain intact, and each
chunk receives a document-and-section breadcrumb plus retrieval metadata.

- The Software Engineering 3155 core uses a 300-token target, a 500-token limit,
  and up to 40 tokens of same-section overlap.
- *Software Engineering at Google* chapters use a 650-token target, a 900-token
  limit, and up to 100 tokens of same-section overlap.
- Other documents use a 450-token target, a 700-token limit, and up to 80 tokens
  of same-section overlap.

Chunks never overlap across heading boundaries. Re-uploading a previously indexed
document replaces its older chunk layout rather than retaining stale duplicates.
Assignment requests are hard-filtered by structural assignment metadata before
retrieval, so a cross-reference to Assignment 1 inside Assignment 2 cannot leak
Assignment 2 content into an Assignment 1 answer.

### Software Engineering 3155 corpus

The Fall 2026 Socratic tutoring corpus is generated from the course overview and
Assignments 1–5. Human-readable and retrieval-ready artifacts are stored in:

```text
docs/rag/software-engineering-3155-fall-2026/
```

The current lexical RAG scanner reads the semantic Markdown units named
`backend/data/raw_docs/se3155-*.md`. Regenerate every representation after
editing the source structure:

```bash
python tools/build_se3155_corpus.py
```

The JSONL version preserves assignment, content-type, confidence, privacy, and
verification metadata for a future vector-embedding pipeline. The corpus follows
the course AI policy: no chatbot assistance on quizzes, no assignment code from
scratch, and code-level help only for debugging a learner's own attempt.

## Run

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
```

## API

- `GET /health`
- `POST /api/documents/text`
- `POST /api/documents/scan`
- `POST /api/chat`


## PostgreSQL conversation memory

The chatbot saves every user and assistant message in PostgreSQL. It also stores
the conversation's latest LLM-derived dialogue status, active concept, and
whether the session is active, paused, or completed. These fields describe the
current interaction; they are not a student mastery score.

1. Create a database:

```bash
createdb my_rag_chatbot
```

2. Add this to `.env`:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/my_rag_chatbot
```

Change the username, password, host, and database name to match your PostgreSQL setup.

3. Install the database driver:

```bash
cd backend
../.venv/bin/python -m pip install -r requirements.txt
```

4. Restart the server:

```bash
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The app creates these tables automatically on startup:

- `conversations`
- `conversation_messages`
- `mastery_assessments` (one immutable record per evaluated student answer)
- `student_concept_progress` (the latest per-student, per-course concept state)

## Chat pipeline logs on Render

Each `POST /api/chat` request writes concise structured events to stdout with a
unique `trace_id`. Render is configured with `PYTHONUNBUFFERED=1`, so these
events appear immediately in the service's Application Logs. Search for the
exact field `trace_id=<id>` to follow one request across routing, retrieval,
generation, forwarding, saving, and response return.

Message and conversation-history content is never logged. Setting
`DEBUG_PIPELINE_LOGS=true` adds redacted, truncated previews of retrieved chunks,
fixed prompt instructions, the model candidate, and the forwarded final answer,
along with character counts and non-reversible SHA-256 fingerprints. It never
logs complete prompts or documents. The local configuration enables it for
pipeline analysis; production deployments can disable it after diagnosis.

Check the connection:

```text
http://127.0.0.1:8000/api/db/status
```

## UNC Charlotte account access

The deployed app can be limited to UNC Charlotte Google Workspace accounts. In
this mode, email/password registration is disabled and Google must return the
verified hosted-domain claim `charlotte.edu`.

Create a Google OAuth 2.0 **Web application** client and add these authorized
JavaScript origins:

```text
https://jamesonthehill.github.io
https://jamesonthehill.com
http://127.0.0.1:8001
http://localhost:8001
```

Configure these environment variables on the Render backend:

```text
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com
AUTH_MODE=school_google
ALLOWED_GOOGLE_DOMAINS=charlotte.edu
AUTH_SESSION_SECRET=A_LONG_RANDOM_SECRET
AUTH_SESSION_MINUTES=60
CORS_ALLOWED_ORIGINS=https://jamesonthehill.github.io,https://jamesonthehill.com
```

Generate `AUTH_SESSION_SECRET` with `openssl rand -hex 32`. Keep it only in
Render's environment settings or a local `.env`; never commit its value.

The GitHub Pages frontend reads the Render API address from
`frontend/config.js`. The backend verifies the Google ID token, issues a signed
session, and requires that session on chat, file, and conversation endpoints.

## Roles and one-time account setup

After the first successful school Google sign-in, a user completes one account
setup form with a Socratic-Chat username, matching password confirmation, and a
requested position. The password is stored as a salted PBKDF2 hash; it is never
stored as plain text. The setup form is shown only once. Afterward, returning
users may sign in with either Google or their Socratic-Chat ID and password.

The `users.authority_level` column controls backend authorization:

- `0` — administrator
- `1` — instructor
- `2` — student

Students become active immediately. Choosing instructor creates a pending
request while the account remains at student authority. An administrator can
approve or reject the request from the course dashboard. Users cannot grant
themselves instructor or administrator access.

The landing page keeps both authentication choices visible:

- School Google is required for first-time verification and account setup.
- Socratic-Chat ID/password is available only after Google verification and
  onboarding have been completed.

Control returning-user password login with:

```text
ALLOW_PASSWORD_LOGIN=true
```

Open registration remains disabled in `school_google` mode, so visitors cannot
create password-only accounts without first verifying a school Google account.

Set at least one administrator in the Render environment before deployment:

```text
ADMIN_EMAILS=admin-account@charlotte.edu
```

Multiple administrator emails may be separated with commas. The backend adds
the role and onboarding columns automatically during startup. Instructor-only
document APIs are also protected by the backend, not only hidden in the UI.

### Require both UNC Charlotte and GitHub

Create a GitHub OAuth App under **GitHub Settings → Developer settings → OAuth
Apps** with:

```text
Homepage URL: https://jamesonthehill.com/Socratic-Chat/
Authorization callback URL: https://socratic-chat-api.onrender.com/api/auth/github/callback
```

Add the generated credentials to Render and enable the requirement only after
both values are present:

```text
GITHUB_CLIENT_ID=YOUR_GITHUB_OAUTH_CLIENT_ID
GITHUB_CLIENT_SECRET=YOUR_GITHUB_OAUTH_CLIENT_SECRET
REQUIRE_GITHUB_ACCOUNT=true
GITHUB_CALLBACK_URL=https://socratic-chat-api.onrender.com/api/auth/github/callback
FRONTEND_URL=https://jamesonthehill.com/Socratic-Chat/
```

The user must first pass the `charlotte.edu` Google Workspace check and then
authorize GitHub. Each GitHub numeric user ID can be linked to only one school
account. The app requests no repository access. Until both identities are
present, protected chatbot APIs return 403.

## Keeping a teaching example consistent

The tutor keeps the first explicit scenario (for example, an opening beginning
with “Imagine” or “Suppose”) from the saved conversation available to generation
and answer evaluation, alongside the recent eight-message exchange. It recovers
that example even after it leaves the recent-message window or a chat is resumed.
An explicit request such as “use a different example” resets the example.

Hints and corrections simplify the same people, objects, and goal. Evaluated
misconceptions trigger a counterexample within that situation; partial answers
lead to a missing connection. Scores below 80 continue the guided exchange in
the same scenario. A strong assessed answer ends the teaching sequence and
opens the summary and Submit assignment button. A claim such as “I understand”
still needs demonstrated evidence before it can receive a score.

The tutor is strongly encouraged to keep each response within 40 words. This is a writing
preference, not a hard rejection threshold: the complete model response is displayed even
when it is longer or contains multiple questions.

Scenario continuity is a model instruction supported by retained context and
retrieved course material; it is not a guarantee that every generated response will stay on
topic. Requests without relevant course material are still stopped before generation.
