# EduMind AI Platform

EduMind is a full-stack platform for generating learning resources using retrieval augmented generation (RAG). It combines a Vue 3 client, an Express backend, a FastAPI microservice (LightRAG) and a MySQL database. Docker Compose orchestrates the entire stack for local development or deployment.

## Project layout

```
.
├── client/         # Vue frontend
├── server/         # Node/Express REST API
├── ml-service/     # Python FastAPI service running LightRAG
├── init_scripts/   # SQL for bootstrapping the database
├── docker-compose.yml
└── README.md
```

- **client/** – Single Page Application built with Vite. It talks to the backend via REST and manages authentication and chats.
- **server/** – Provides CRUD endpoints for users, projects, sessions, questions and more. Also proxies requests to the ML service.
- **ml-service/** – Runs LightRAG for indexing and querying documents, question generation and chat summarisation.
- **init_scripts/** – SQL script (`db_int.sql`) executed on first MySQL start to create tables and seed demo data.

## Prerequisites

- Docker and Docker Compose
- OpenAI API key (required by the ML components)

## Quick start

1. **Clone the repository**

   ```bash
   git clone https://github.com/jaltareyr/AI-ED-Tools.git
   cd AI-ED-Tools
   ```

2. **Create environment file**

   A root `.env` for all containers:

   ```env
   PROJECT_ID=DEFAULT
   HOST=0.0.0.0
   ML_PORT=9621
   WEBUI_TITLE='EduMind'
   WEBUI_DESCRIPTION="Simple and Fast Graph Based AQG Tool"
   OLLAMA_EMULATING_MODEL_TAG=latest
   WORKERS=3
   CORS_ORIGINS=http://localhost:3000,http://localhost:8080,http://localhost:5173
   
   OPENAI_API_KEY=sk-proj-<Your OpenAI API Key>
   
   GRAPHRAG_DEFAULT_INDEXING_MODEL=gpt-4o-mini-2024-07-18
   GRAPHRAG_DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
   
   OPENAI_TOPIC_SUMMARY_MODEL=gpt-4.1-nano-2025-04-14
   OPENAI_CHAT_MODEL=gpt-4.1-nano-2025-04-14
   OPENAI_QUERY_INTERPRETATION_MODEL=gpt-4o-mini-2024-07-18
   OPENAI_GENERATION_MODEL=o4-mini-2025-04-16
   OPENAI_TWEAK_MODEL=o4-mini-2025-04-16
   
   COMMUNITY_LEVEL=2
   MAX_TOKENS_CONTEXT=12000
   MAX_TOKENS_MAP=2000
   MAX_TOKENS_REDUCE=4000
   
   
   SUMMARY_LANGUAGE=English
   MAX_PARALLEL_INSERT=4
   CHUNK_SIZE=7000
   CHUNK_OVERLAP_SIZE=200
   ENABLE_LLM_CACHE=true
   ENABLE_LLM_CACHE_FOR_EXTRACT=true
   TIMEOUT=240
   TEMPERATURE=0.7
   MAX_ASYNC=10
   MAX_TOKENS=12000
   LLM_BINDING=openai
   LLM_MODEL=gpt-4o-mini-2024-07-18
   LLM_BINDING_HOST=https://api.openai.com/v1
   LLM_BINDING_API_KEY=sk-proj-<Your OpenAI API Key>
   
   EMBEDDING_BINDING=openai
   EMBEDDING_MODEL=text-embedding-3-small
   EMBEDDING_DIM=1536
   EMBEDDING_BINDING_API_KEY=sk-proj-<Your OpenAI API Key>
   EMBEDDING_BINDING_HOST=https://api.openai.com/v1
   EMBEDDING_FUNC_MAX_ASYNC=32
   
   GRAPHRAG_API_KEY=sk-proj-<Your OpenAI API Key>
   SERVER_PORT=3000
   MYSQL_HOST=mysql
   MYSQL_PORT=3306
   MYSQL_USER=myuser
   MYSQL_PASSWORD=mypassword
   MYSQL_DATABASE=edumind
   MYSQL_ROOT_PASSWORD=mypassword
   FILE_UPLOAD_PATH=/app/uploads
   ML_SERVICE_SERVER=http://ml-service:9621
   
   VITE_SERVER_URL=http://localhost:3000
   VITE_LIGHTRAG_SERVER=http://localhost:9621
   ```

3. **Start the stack**

   ```bash
   docker compose up --build
   ```

The web client will be available on <http://localhost:80> and the API on <http://localhost:3000>. The ML service listens on <http://localhost:9621>.

### Development mode

For live code reloading run Compose with the provided override file:

```bash
docker compose -f docker-compose.yml -f docker-compose.override.txt up --build
```

This uses the development Dockerfiles and exposes the Vite dev server on port 5173.

## Services

| Service       | Path          | Default port | Notes                                 |
|---------------|--------------|--------------|---------------------------------------|
| **frontend**  | `client/`    | 80 (or 5173) | Vue application served by Nginx       |
| **backend**   | `server/`    | 3000         | Express API, connects to MySQL & ML   |
| **ml-service**| `ml-service/`| 9621         | FastAPI with LightRAG                 |
| **mysql**     | container    | 3306         | Uses `init_scripts/db_int.sql` on boot|

Uploaded files and LightRAG indices are stored in the `file_storage` volume. Database data persists in the `edumind_database` volume.

## Useful commands

```bash
docker compose up -d        # start in background
docker compose down         # stop containers
docker compose logs -f      # view logs
```

## Security tips

- Do **not** commit real `.env` files.
- For production, place a reverse proxy in front of the services and secure secrets properly.

## License

MIT. See `LICENSE` for details.
