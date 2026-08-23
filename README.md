# Socratic-Chat

A clean personal workspace for a retrieval-augmented chatbot.

The backend indexes local Markdown/text notes, retrieves relevant chunks, and answers questions. If `OPENAI_API_KEY` is set, it uses OpenAI for generation. If not, it still returns a grounded extractive answer from your documents.

## Setup

```bash
cd Socratic-Chat
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
```

Add an OpenAI key to `.env` if you want generated answers.

## Add Documents

Put `.txt` or `.md` files in:

```text
backend/data/raw_docs/
```

Then start the backend and press **Scan documents** in the UI.

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

The chatbot can save every user and assistant message in PostgreSQL.

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
