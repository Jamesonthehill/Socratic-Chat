# ClubALL learning platform

A course-scoped instructor assignment studio and student workspace using the existing CourseLab design. Activity choices are **Socratic Chat**, **Reflections**, **Self Directed Learning**, **Debate**, and **AIducate** (draft only). See [UI rework and service setup](docs/platform-ui-rework.md) for the current flow, dependencies, and verification limits.

## Run with Docker

```bash
cp .env.example .env
# Edit .env: set independent AUTH_SESSION_SECRET and PLATFORM_SERVICE_TOKEN values,
# and the model-provider keys needed by the tools you use.
docker compose up --build
```

Open **http://localhost:8000**. Login and account setup use the existing Socratic authentication flow, then redirect to `/platform/`.

Compose starts the public platform, private Reflections and SDL services, and uses `DOCKER_DATABASE_URL` for PostgreSQL/pgvector. Only the platform exposes a host port. The legacy Tutor is optional with the `legacy-tutor` profile. The `isolated-db` profile supplies an optional local PostgreSQL service; it is not enabled by default.

Set a valid provider key for embeddings, lesson generation and live replies. Reflections may download its existing embedding model on the first milestone request. See the [setup guide](docs/platform-ui-rework.md) before applying the shared RAG migration to an existing deployment.

## Socratic questioning pipeline

Socratic assignments use the same end-to-end teaching pipeline as the standalone Socratic Chat application:

1. Classify the learner's intent, target concept, dialogue state, and requested action.
2. Retrieve relevant passages with dense embeddings and PostgreSQL full-text search.
3. Evaluate substantive learner answers against the retrieved course evidence.
4. Track per-concept evidence and move learners through emerging, developing, verification-ready, and mastered states.
5. Select a Socratic strategy and disclosure level based on the learner's current understanding and prior turns.
6. Generate and validate one grounded response, or produce a safe pause/close transition.
7. Record privacy-safe stage logs for diagnosis without logging raw learner messages by default.

Publishing an assignment stores an immutable copy of the selected document chunks and their embeddings. Later document edits or deletions therefore do not change an already-published assignment. PostgreSQL uses the `pgvector` image because document ingestion and hybrid retrieval require the vector extension.

## Accounts and courses

- For an institutional deployment, use `AUTH_MODE=school_google`, configure `GOOGLE_CLIENT_ID`, allowed domains and the application origin, and set `ADMIN_EMAILS`. Existing Google verification, instructor approvals, and optional GitHub linking are preserved.
- With `AUTH_MODE=open`, register local accounts at `/`. When
  `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and `GITHUB_CALLBACK_URL` are
  configured, the same login form also offers GitHub authentication using a
  verified GitHub email; it requests no repository access. Registration
  produces student accounts. To bootstrap a professor/admin, use the explicit
  database administration command below after registering:

```bash
docker compose exec platform python scripts/set_role.py professor@example.edu instructor
```

For a local Python installation, use `.venv/bin/python scripts/set_role.py professor@example.edu instructor` instead.

Course context is supplied by the Canvas launch (`?course=<platform-course-UUID>`). For local testing only, set `PLATFORM_LOCAL_COURSE_CODE` to an existing course code; approved membership is still required. There is no course picker or course-management landing in this interface.

## Professor workflow

1. Open **All assignments** and select **Create New Activity**.
2. Enter the activity title, due date and description.
3. Select indexed course documents, upload new documents, or use both.
4. Choose one of the five activity types and configure its settings below.
5. Save a draft, review the activity, or publish. SDL review generates its lesson and exposes quiz questions, answers, examples and practice rubrics.
6. Reopen a draft to continue editing; open a published activity to see **At a glance** and assignment details. **Detailed Insights** opens the Analytics placeholder.

### Add ClubALL from Canvas Course Settings (LTI 1.1)

LTI 1.1 opens the full ClubALL platform using a signed Canvas identity and course
role. Configure `LTI_PUBLIC_BASE_URL`, `LTI_CANVAS_ISSUER`,
`LTI11_CONSUMER_KEY`, and `LTI11_SHARED_SECRET`, then install through
**Settings → Apps → View App Configurations → + App → By URL** using
`https://YOUR_CLUBALL_HOST/api/lti/canvas-config.xml`.

See [the LTI 1.1 setup guide](docs/canvas-lti11.md) for deployment, credentials,
installation, and verification. An instructor must launch first to create the
linked private course. Students then enter the shared ClubALL assignment
workflow. LTI 1.1 requires no Canvas Developer Key or personal API token.

### Add ClubALL as a Canvas External App (LTI 1.3)

The personal-token importer above and the LTI integration serve different
purposes. The importer copies existing Canvas assignments into ClubALL. LTI lets
Canvas users open ClubALL from course navigation with a signed Canvas identity
and course context, without entering another password or pasting an API token.

The first LTI milestone supports **Course Navigation**:

- Canvas validates the configured ClubALL public key.
- ClubALL validates the Canvas launch signature, issuer, client ID, deployment
  ID, nonce, and one-time state.
- The first instructor launch creates a private linked ClubALL course.
- Later instructor and student launches create or link accounts by the signed
  Canvas identity and approve the matching course membership.
- Students are added to published whole-course assignments when they first
  launch from Canvas.

ClubALL must be available at a stable public HTTPS origin. `localhost` cannot be
used for an institutional Canvas installation.

1. Generate a dedicated RSA key outside the repository:

   ```bash
   openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out cluball-lti-private.pem
   base64 < cluball-lti-private.pem | tr -d '\n'
   ```

2. Store the Base64 output only in the deployment environment and initially
   configure:

   ```dotenv
   LTI_PUBLIC_BASE_URL=https://cluball.example.edu
   LTI_TOOL_PRIVATE_KEY_B64=<base64-private-key>
   LTI_TOOL_KEY_ID=cluball-lti-1
   ```

3. Ask a UNC Charlotte Canvas administrator to create an **LTI Developer Key**.
   Canvas can import the JSON served at
   `https://cluball.example.edu/api/lti/canvas-config`, or the administrator can
   enter its OIDC initiation, launch, and public JWKS URLs manually. Enable the
   Developer Key and copy its Client ID.
4. In the target Canvas account or course, open **Settings → Apps → View App
   Configurations → + App**, choose **By Client ID**, enter the Client ID, and
   install ClubALL. Copy the resulting Deployment ID.
5. Complete the deployment environment and restart ClubALL:

   ```dotenv
   LTI_CANVAS_ISSUER=https://instructure.charlotte.edu
   LTI_CLIENT_ID=<canvas-developer-key-client-id>
   LTI_DEPLOYMENT_ID=<installed-app-deployment-id>
   LTI_PLATFORM_JWKS_URL=https://sso.canvaslms.com/api/lti/security/jwks
   ```

6. Verify `/api/lti/status` reports both
   `tool_configuration_ready: true` and `launch_configured: true`. An instructor
   must launch ClubALL once from the Canvas course before students launch it.

Never commit the RSA private key, Client ID/deployment configuration for a
private institution deployment, or other Canvas administrator credentials.
Assignment deep linking, roster synchronization (NRPS), and grade return (AGS)
are intentionally deferred until the course-navigation launch is approved and
tested by the institution.

Published settings are immutable. Socratic snapshots the selected indexed document content; Reflections creates a private assignment module; Tutor stores a complete topic snapshot. Editing or deleting source materials does not alter published work. **Duplicate as draft** creates a new editable assignment; **Archive** removes student access while retaining results for the professor.

The progress view lists each recipient's status and available results. A
whole-course assignment can be published before any students enroll. Its
recipients are the approved students enrolled **at publication time**, so later
manual enrollments are not added automatically. A verified LTI student launch
does add that student to already-published whole-course assignments for the
linked Canvas course. Revoking enrollment immediately removes assignment
access. Due dates are informational; late work remains allowed.

## Student workflow

The student dashboard stacks **New**, **In progress**, **Completed**, and **All assignments** sections. Icon-only controls switch between cards and the compact list, remembering the browser's preference. Students open the instructor-assigned chat without choosing its configuration.

- Socratic uses the selected, frozen course chunks and its existing questioning pipeline.
- Debate uses the configured scenario and live AI provider; completion requires the configured message count.
- SDL opens inside the platform and resumes the existing adaptive lesson, including study, diagnostic questions, practice and reflection. Its workflow remains owned by the SDL service; it does not use the common Debate attempt table.
- Reflections retains its existing student UI and private backend adapter.
- AIducate supports draft storage only.

For Reflections, **Start assignment** (or **Resume assignment** / **View reflection results**) opens the original Reflections student interface in a new tab. The tab uses the signed-in platform account and published assignment settings automatically, including the topic chat, timer, evaluation, or milestone reflection and similar experiences. Returning to the assignment tab refreshes its progress. Build the platform frontend to bundle both interfaces; no separate Reflections frontend server is needed. The private Reflections backend and its configured model provider must still be running.

## Local development

Python 3.12, Node 22+, and PostgreSQL are suitable for this workspace. The projects run in separate Python processes because both Socratic and Reflections use the package name `app`.

The repository-root `.python-version` pins Python 3.12 for native deployments
such as Render. Keep the Render service root at the repository root when
deploying the unified platform; its build command is
`pip install -r requirements.txt && cd platform_frontend && npm ci && npm run build`,
and its start command is
`python -m uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-10000}`.
The root `render.yaml` records these settings for Blueprint deployments. For an
existing manually configured Render service, copy these commands into
**Settings → Build & Deploy**; do not use Render's placeholder
`gunicorn your_application.wsgi` command because ClubALL is a FastAPI ASGI
application. Enter the command without surrounding quotation marks. The
`platform_app` module is available only when Render's **Root Directory** is
blank (the repository root), not `Socratic-Chat/backend`.

### Render Blueprint (recommended)

Use the root `render.yaml` for the complete public platform plus token-protected Reflections
and SDL free web services. See [the Blueprint deployment guide](docs/render-blueprint.md)
for required secrets, free-tier limits, existing-service migration, and validation.
The manual instructions below describe the older public Reflections setup.

### Reflections on Render

The platform service alone cannot generate sub-topics or run Reflections
assignments. Deploy the separate `cluball-reflections` web service defined in
`render.yaml`, with its **Root Directory** blank. It installs
`reflections-app/backend/requirements.txt` and starts the backend from that
directory to avoid colliding with Socratic's Python `app` package.

For an existing manual deployment:

1. Create a Python web service from this repository. Build command:
   `pip install -r reflections-app/backend/requirements.txt`. Start command:
   `cd reflections-app/backend && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}`.
   Set its health check to `/health`.
2. Copy the platform's `DATABASE_URL` and `PLATFORM_SERVICE_TOKEN` into the
   Reflections service. Both services must use the same values. Set
   `PLATFORM_DB_SCHEMA=platform` and `REFLECTIONS_DB_SCHEMA=reflections_app`.
   Deploy the platform first so its shared database tables exist.
3. Configure `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and
   `GROQ_MODEL=openai/gpt-oss-120b` on the Reflections service, or configure the
   provider and matching key/model for your chosen provider.
4. Set `REFLECTIONS_URL` on the platform to the Reflections service's actual
   public HTTPS URL from Render (without `/health`), then redeploy the platform.
   Free Render web services cannot receive private network requests, so use
   the public URL. The service token protects backend requests.
5. Confirm the Reflections `/health` returns `{"status":"ok"}`, then sign in
   as a professor and retry **Generate sub-topics**.

The error “The reflections engine is unavailable. Please retry shortly.”
means the platform encountered a transport error or an invalid JSON response
from this backend. Check `REFLECTIONS_URL` and the Reflections startup logs;
the default `127.0.0.1:8002` only works with the local multi-process runner.
Separate AI key errors indicate that the backend was reached but its provider
credentials need attention. Blueprint deployments share the database URL and
service token automatically; supply `REFLECTIONS_URL` and `GROQ_API_KEY`
when creating the Blueprint.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt

python3.12 -m venv reflections-app/.venv
reflections-app/.venv/bin/python -m pip install -r reflections-app/backend/requirements.txt
python3.12 -m venv student-agent-bot/.venv
student-agent-bot/.venv/bin/python -m pip install -r student-agent-bot/requirements.txt

cd platform_frontend
npm ci
npm run build
cd ..

cp .env.example .env
# Create the two databases and configure their URLs/secrets/provider keys in .env.
REFLECTIONS_PYTHON="$PWD/reflections-app/.venv/bin/python" \
TUTOR_PYTHON="$PWD/student-agent-bot/.venv/bin/python" \
  .venv/bin/python scripts/run_local.py
```

Open http://127.0.0.1:8000. The runner starts the gateway on 8000, Reflections on 8002, and Tutor on 8003, all bound to loopback. Stopping it stops all three. Install dependencies first and use absolute paths for the optional interpreter overrides.

### Docker Compose

The Compose deployment starts the platform gateway, Reflections, and SDL using the PostgreSQL/pgvector database configured in `DOCKER_DATABASE_URL`:

```bash
docker compose -f compose.yaml up --build
```

The gateway is available at http://127.0.0.1:8000. The containerized services use `DOCKER_DATABASE_URL` from `.env` to reach the host database on port 5434 and `host.docker.internal` to reach Ollama running on the host at port 11434. This means native and Docker runs share accounts, courses, documents, and evaluations. Stop the stack with:

```bash
docker compose -f compose.yaml down
```

To remove the Docker database and other persisted service data as well, use `docker compose -f compose.yaml down -v`.

The isolated PostgreSQL service remains available only for explicit experiments with `docker compose --profile isolated-db ...`; it is not used by the main Docker deployment.

For frontend iteration with shared authentication, run `npm run build -- --watch` in `platform_frontend` and refresh the gateway page after changes. This keeps login and the UI on one origin. The optional Vite development server proxies API requests, but using it on another port requires a same-origin login proxy because browser sessions are stored per origin.

## Structure and integration boundaries

```text
platform_app/             Shared assignment API, authorization, engine adapters
  migrations/            Versioned platform schema migrations
platform_frontend/       Shared React UI and separate tool configuration screens
Socratic-Chat/            Existing identity, courses, documents, RAG engine
reflections-app/          Existing reflection graphs, analytics and recommendations
adaptive-learning-app/   SDL engine, shared ingestion pipeline and embedded lesson UI
student-agent-bot/        Historical tutor (optional legacy-tutor Compose profile)
scripts/                 Local runner, role bootstrap, database initialization
platform_tests/          Assignment integration tests
compose.yaml             One public origin and private learning services
```

The shared backend reuses Socratic's authentication and course APIs. PostgreSQL is divided into explicit namespaces:

- `platform`: shared identity, course, enrollment, assignment, recipient, and attempt tables. Every table ends in `_platform`.
- `socratic_chat`: Socratic conversations, messages, progress, assessments, files, and document chunks. Every table ends in `_socratic_chat`; user and course foreign keys point into `platform`.
- `reflections_app`: reflection modules, configurations, conversations, analytics, and LangGraph checkpoints. Every table ends in `_reflections_app`; new platform sessions reference `platform.users_platform` and `platform.courses_platform` directly. The legacy student table remains only to preserve historical standalone Reflections sessions.

Tutor uses a persistent SQLite file configured with `TUTOR_SESSION_DB`. Platform, Socratic Chat, Reflections, and SDL use the single PostgreSQL connection in `DATABASE_URL`; their schemas isolate service-owned data. Configure `PLATFORM_DB_SCHEMA`, `SOCRATIC_DB_SCHEMA`, `SHARED_RAG_DB_SCHEMA`, `SELF_DIRECTED_LEARNING_DB_SCHEMA`, and `REFLECTIONS_DB_SCHEMA` when using non-default schema names. The bundled PostgreSQL container is available only through the optional `isolated-db` Compose profile; the default Docker stack uses the host database configured by `DOCKER_DATABASE_URL`.

The browser calls `/api/platform/...`; the gateway chooses the appropriate engine and derives student/session identity from the signed account session. Internal service calls require `X-Platform-Service`, using the common `PLATFORM_SERVICE_TOKEN`. Internal endpoints are unavailable without a token, even in standalone mode. Public platform APIs reject the old `X-User-Id` shortcut.

Platform migrations run once on gateway startup under a database migration lock. Existing Socratic accounts/courses can be reused by setting `DATABASE_URL` to their database. Existing reflection modules and tutor topic files remain available in their original applications; they are not automatically converted into assignments or matched to student identities. Import a topic or configure a new assignment for the shared platform. This avoids guessing recipients or publishing historical content.

## Verification

The PostgreSQL tests create and drop uniquely named schemas. Set `TEST_DATABASE_URL` to an available development/test database whose user can create schemas. They do not alter existing application tables and do not call paid model APIs.

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  .venv/bin/python -m pytest platform_tests -q

# Run each engine suite separately to avoid their conflicting `app` module names.
# Install pytest and httpx in the corresponding virtual environments first.
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  reflections-app/.venv/bin/python -m pytest reflections-app/backend/tests -q
student-agent-bot/.venv/bin/python -m pytest student-agent-bot/tests -q
PYTHONPATH=Socratic-Chat/backend .venv/bin/python -m pytest Socratic-Chat/backend/tests -q

cd platform_frontend
npm test
npm run build
```

Tests cover assignment ownership and visibility, publication rollback, frozen content, recipient/enrollment rules, start races, message retry deduplication, completion, service authentication, engine restart recovery, tool selection, student routing, and frontend failure/retry behavior. Model calls are simulated in engine tests; live provider quality and deployment-specific Google sign-in require configured credentials.

### Reflections provider configuration

If Reflections reports a missing or invalid AI provider key, update `GROQ_API_KEY` or `OPENAI_API_KEY` (matching `LLM_PROVIDER` and any role overrides) in the **root `.env`**. Root Docker Compose does not load `reflections-app/backend/.env`; configure the corresponding `GROQ_MODEL` or `OPENAI_MODEL` in the root file too. Apply environment changes with `docker compose up -d --force-recreate reflections` rather than `docker compose restart`, then retry the assignment. Existing checkpointed sessions are retained.
