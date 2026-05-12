# My RAG Chatbot

A clean personal workspace for a retrieval-augmented chatbot.

The backend indexes local Markdown/text notes, retrieves relevant chunks, and answers questions. If `OPENAI_API_KEY` is set, it uses OpenAI for generation. If not, it still returns a grounded extractive answer from your documents.

## Setup

```bash
cd my-rag-chatbot
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
# RAG_Chatbot
