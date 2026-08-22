from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
RAW_DOCS_DIR = BACKEND_DIR / "data" / "raw_docs"
STORAGE_DIR = BACKEND_DIR / "storage"
INDEX_PATH = STORAGE_DIR / "rag_index.json"

load_dotenv(ROOT_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
RAG_MODEL = os.getenv("RAG_MODEL", "gpt-4o-mini")
RAG_TEMPERATURE = float(os.getenv("RAG_TEMPERATURE", "0.2"))


DATABASE_URL = os.getenv("DATABASE_URL", "")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
