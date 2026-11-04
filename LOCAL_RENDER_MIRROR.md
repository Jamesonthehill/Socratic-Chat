# Local copy of the Render BrainTutor app

This folder was cloned from `Jamesonthehill/Socratic-Chat` `main` at commit
`84ddfaa`. It contains the same BrainTutor platform and Socratic questioning
pipeline code used by the Render platform service. The older
`local-socratic-chat/Socratic-Chat` checkout was not changed.

Run from this folder:

```bash
bash run-local.sh
```

Open <http://127.0.0.1:8000/platform/>. The script starts the isolated local
PostgreSQL 17 database on `127.0.0.1:55433` if needed. Stop the app with
Ctrl+C. To stop the database too, run:

```bash
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D .local/postgres stop
```

The local `.env` is ignored by Git. It uses Ollama's locally installed
`gpt-oss:20b` for chat and `qwen3-embedding:0.6b` for retrieval, so no hosted
API keys or Supabase password are copied here. The questioning code is the
same; the inference provider and embedding dimensions differ from Render.
If you want the exact hosted providers, put your own `GROQ_API_KEY` and
`OPENAI_API_KEY` in this folder's `.env`, set `LLM_PROVIDER=groq`,
`EMBEDDING_PROVIDER=openai`, `EMBEDDING_MODEL=text-embedding-3-small`, and
`EMBEDDING_DIMENSIONS=1536`. Use a fresh local database when changing
embedding dimensions after documents have been indexed.

The local database starts empty. Register a local account, then promote the
instructor account with `scripts/set_role.py` as described in the root README.
Keep `DATABASE_URL` pointed at this local database; never use your hosted
Supabase URL for local testing. Changes in this folder stay local until you
explicitly commit and push them to GitHub.
