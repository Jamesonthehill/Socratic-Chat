from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]  # Project folder containing .env.
BACKEND_DIR = ROOT_DIR / "backend"  # API and local document workspace.
FRONTEND_DIR = ROOT_DIR / "frontend"  # Browser application files.
RAW_DOCS_DIR = BACKEND_DIR / "data" / "raw_docs"  # Disk copies used during extraction.

load_dotenv(ROOT_DIR / ".env")  # Local defaults; deployed environment can override them.

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # Used if OpenAI chat or embeddings are selected.
OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")  # OpenAI endpoint.
RAG_MODEL = os.getenv("RAG_MODEL", "gpt-4.1-mini")  # Default OpenAI chat model.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()  # Chat provider for the three LLM roles.
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
OLLAMA_API_BASE_URL = os.getenv("OLLAMA_API_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b-q4_K_M")  # Local fallback for all chat roles.
OLLAMA_CLASSIFIER_MODEL = os.getenv("OLLAMA_CLASSIFIER_MODEL", "").strip()  # Optional classifier override.
OLLAMA_ANSWER_EVALUATION_MODEL = os.getenv("OLLAMA_ANSWER_EVALUATION_MODEL", "").strip()  # Optional evaluator override.
OLLAMA_GENERATION_MAX_TOKENS = int(os.getenv("OLLAMA_GENERATION_MAX_TOKENS", "600"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_BASE_URL = os.getenv("GROQ_API_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")  # Hosted chat default when Groq is selected.
GROQ_CLASSIFIER_MODEL = os.getenv("GROQ_CLASSIFIER_MODEL", "").strip()  # Optional classifier override.
GROQ_ANSWER_EVALUATION_MODEL = os.getenv("GROQ_ANSWER_EVALUATION_MODEL", "").strip()  # Optional evaluator override.
RAG_TEMPERATURE = float(os.getenv("RAG_TEMPERATURE", "0.2"))
CLASSIFIER_ENABLED = os.getenv("CLASSIFIER_ENABLED", "true").lower() in {"1", "true", "yes"}  # Allow LLM intent detection.
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "").strip()
CLASSIFIER_TEMPERATURE = float(os.getenv("CLASSIFIER_TEMPERATURE", "0"))
CLASSIFIER_MAX_TOKENS = int(os.getenv("CLASSIFIER_MAX_TOKENS", "900"))
CLASSIFIER_MAX_HISTORY = int(os.getenv("CLASSIFIER_MAX_HISTORY", "6"))  # Recent turns given to classifier.
ANSWER_EVALUATION_ENABLED = os.getenv("ANSWER_EVALUATION_ENABLED", "true").lower() in {"1", "true", "yes"}  # Conditional scoring.
ANSWER_EVALUATION_MODEL = os.getenv("ANSWER_EVALUATION_MODEL", "").strip()
ANSWER_EVALUATION_MAX_TOKENS = int(os.getenv("ANSWER_EVALUATION_MAX_TOKENS", "1600"))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama").strip().lower()  # Independent of chat provider.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")  # OpenAI vector model if selected.
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b")  # Local vector model.
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))  # Must match DB vector column/model output.
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))  # Number of chunks per embedding call.
RAG_MIN_DENSE_SIMILARITY = float(os.getenv("RAG_MIN_DENSE_SIMILARITY", "0.42"))  # Semantic relevance gate.
RAG_MIN_SPARSE_SCORE = float(os.getenv("RAG_MIN_SPARSE_SCORE", "0.05"))  # Exact-word relevance gate.
DEBUG_PIPELINE_LOGS = os.getenv("DEBUG_PIPELINE_LOGS", "false").lower() in {"1", "true", "yes"}
_pipeline_log_file = os.getenv("PIPELINE_LOG_FILE", "backend/storage/pipeline.log").strip()
PIPELINE_LOG_FILE = (
    Path(_pipeline_log_file)
    if not _pipeline_log_file or Path(_pipeline_log_file).is_absolute()
    else ROOT_DIR / _pipeline_log_file
)
LOG_FULL_PROMPTS = os.getenv("LOG_FULL_PROMPTS", "false").lower() in {"1", "true", "yes"}
_pipeline_prompt_dir = os.getenv("PIPELINE_PROMPT_DIR", "backend/storage/pipeline_prompts").strip()
PIPELINE_PROMPT_DIR = (
    Path(_pipeline_prompt_dir)
    if not _pipeline_prompt_dir or Path(_pipeline_prompt_dir).is_absolute()
    else ROOT_DIR / _pipeline_prompt_dir
)


def llm_client_config(role: str = "generation") -> tuple[str, str, str, str] | None:
    """Select the chat endpoint/model; embedding provider is configured separately."""
    if LLM_PROVIDER in {"local", "ollama"}:
        role_model = {
            "classifier": OLLAMA_CLASSIFIER_MODEL,
            "evaluation": OLLAMA_ANSWER_EVALUATION_MODEL,
        }.get(role, "")
        return "Ollama", OLLAMA_API_KEY or "ollama", OLLAMA_API_BASE_URL, role_model or OLLAMA_MODEL
    if LLM_PROVIDER == "groq":
        if not GROQ_API_KEY:
            return None
        role_model = {
            "classifier": GROQ_CLASSIFIER_MODEL,
            "evaluation": GROQ_ANSWER_EVALUATION_MODEL,
        }.get(role, "")
        return "Groq", GROQ_API_KEY, GROQ_API_BASE_URL, role_model or GROQ_MODEL
    if LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            return None
        role_model = {
            "classifier": CLASSIFIER_MODEL,
            "evaluation": ANSWER_EVALUATION_MODEL,
        }.get(role, "")
        return "OpenAI", OPENAI_API_KEY, OPENAI_API_BASE_URL, role_model or RAG_MODEL
    return None


def completion_token_parameters(provider: str, limit: int) -> dict[str, int | str]:
    """Use provider-compatible output limits and keep local responses visible."""
    if provider == "Ollama":
        return {"max_tokens": limit, "reasoning_effort": "none"}
    return {"max_completion_tokens": limit}


def embedding_client_config() -> tuple[str, str, str, str] | None:
    """Return the configured embedding endpoint and model."""
    if EMBEDDING_PROVIDER in {"local", "ollama"}:
        return "Ollama", OLLAMA_API_KEY or "ollama", OLLAMA_API_BASE_URL, OLLAMA_EMBEDDING_MODEL
    if EMBEDDING_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            return None
        return "OpenAI", OPENAI_API_KEY, OPENAI_API_BASE_URL, EMBEDDING_MODEL
    return None


def embedding_model_name() -> str:
    config = embedding_client_config()
    return config[3] if config else OLLAMA_EMBEDDING_MODEL


DATABASE_URL = os.getenv("DATABASE_URL", "")

REQUIRE_EMAIL_VERIFICATION = os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() in {"1", "true", "yes"}
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
EMAIL_CODE_EXPIRY_MINUTES = int(os.getenv("EMAIL_CODE_EXPIRY_MINUTES", "10"))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

AUTH_MODE = os.getenv("AUTH_MODE", "open").strip().lower()
SCHOOL_GOOGLE_AUTH_ENABLED = AUTH_MODE == "school_google"
ALLOWED_GOOGLE_DOMAINS = {
    domain.strip().lower()
    for domain in os.getenv("ALLOWED_GOOGLE_DOMAINS", "").split(",")
    if domain.strip()
}
AUTH_SESSION_SECRET = os.getenv("AUTH_SESSION_SECRET", "")
AUTH_SESSION_MINUTES = int(os.getenv("AUTH_SESSION_MINUTES", "60"))
ALLOW_PASSWORD_LOGIN = os.getenv("ALLOW_PASSWORD_LOGIN", "true").lower() in {"1", "true", "yes"}
CORS_ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
}

REQUIRE_GITHUB_ACCOUNT = os.getenv("REQUIRE_GITHUB_ACCOUNT", "false").lower() in {"1", "true", "yes"}
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_CALLBACK_URL = os.getenv("GITHUB_CALLBACK_URL", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://jamesonthehill.com/Socratic-Chat/")
