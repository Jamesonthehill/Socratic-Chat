from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from contextlib import contextmanager
from typing import Iterator

from app import settings
from app.schemas import ChatMessage


@contextmanager
def get_connection() -> Iterator[object]:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    import psycopg

    with psycopg.connect(settings.DATABASE_URL) as conn:
        yield conn


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex(), digest.hex()


def _password_matches(password: str, salt_hex: str, expected_hash: str) -> bool:
    _, candidate_hash = _hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate_hash, expected_hash)


def is_enabled() -> bool:
    return bool(settings.DATABASE_URL)


def init_db() -> None:
    if not is_enabled():
        return

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id UUID PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            cur.execute(
                """
                ALTER TABLE conversations
                ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_user_id_updated_at
                ON conversations(user_id, updated_at DESC)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id
                ON conversation_messages(conversation_id, created_at, id)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_state (
                    conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
                    pending_type TEXT NOT NULL,
                    original_question TEXT NOT NULL,
                    missing_target TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_files (
                    id UUID PRIMARY KEY,
                    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                    file_size BIGINT NOT NULL,
                    content BYTEA NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE rag_files
                ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_files_created_at
                ON rag_files(created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_files_conversation_id
                ON rag_files(conversation_id, created_at DESC)
                """
            )
        conn.commit()


def check_status() -> tuple[bool, str]:
    if not is_enabled():
        return False, "DATABASE_URL is not configured."

    try:
        init_db()
        return True, "Connected to PostgreSQL."
    except Exception as exc:
        return False, str(exc)


def ensure_conversation(conversation_id: str | None, title: str = "New conversation", user_id: str | None = None) -> str:
    init_db()
    resolved_id = conversation_id or str(uuid.uuid4())

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (id, title, user_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    updated_at = NOW(),
                    user_id = COALESCE(conversations.user_id, EXCLUDED.user_id)
                """,
                (resolved_id, title[:120] or "New conversation", user_id),
            )
        conn.commit()

    return resolved_id


def add_message(conversation_id: str, role: str, content: str) -> None:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content)
                VALUES (%s, %s, %s)
                """,
                (conversation_id, role, content),
            )
            cur.execute(
                """
                UPDATE conversations
                SET updated_at = NOW()
                WHERE id = %s
                """,
                (conversation_id,),
            )
        conn.commit()


def get_messages(conversation_id: str, limit: int = 50) -> list[ChatMessage]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (conversation_id, limit),
            )
            rows = cur.fetchall()

    return [ChatMessage(role=role, content=content) for role, content in reversed(rows)]


def list_conversations(limit: int = 50, user_id: str | None = None) -> list[dict[str, object]]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    """
                    SELECT
                        c.id::text,
                        c.title,
                        c.created_at::text,
                        c.updated_at::text,
                        COUNT(m.id)::int AS message_count
                    FROM conversations c
                    LEFT JOIN conversation_messages m ON m.conversation_id = c.id
                    WHERE c.user_id = %s
                    GROUP BY c.id, c.title, c.created_at, c.updated_at
                    HAVING COUNT(m.id) > 0
                    ORDER BY c.updated_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        c.id::text,
                        c.title,
                        c.created_at::text,
                        c.updated_at::text,
                        COUNT(m.id)::int AS message_count
                    FROM conversations c
                    LEFT JOIN conversation_messages m ON m.conversation_id = c.id
                    GROUP BY c.id, c.title, c.created_at, c.updated_at
                    HAVING COUNT(m.id) > 0
                    ORDER BY c.updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()

    return [
        {
            "conversation_id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "message_count": row[4],
        }
        for row in rows
    ]


def delete_conversation(conversation_id: str) -> bool:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rag_files WHERE conversation_id = %s", (conversation_id,))
            cur.execute(
                """
                DELETE FROM conversations
                WHERE id = %s
                """,
                (conversation_id,),
            )
            deleted = cur.rowcount > 0
        conn.commit()

    return deleted


def save_rag_file(filename: str, content_type: str, content: bytes, conversation_id: str | None = None) -> str | None:
    if not is_enabled():
        return None

    init_db()
    file_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_files (id, conversation_id, filename, content_type, file_size, content)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (file_id, conversation_id, filename, content_type or "application/octet-stream", len(content), content),
            )
        conn.commit()

    return file_id


def list_rag_files(limit: int = 50, conversation_id: str | None = None) -> list[dict[str, object]]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            if conversation_id:
                cur.execute(
                    """
                    SELECT id::text, filename, content_type, file_size, created_at::text
                    FROM rag_files
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (conversation_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id::text, filename, content_type, file_size, created_at::text
                    FROM rag_files
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()

    return [
        {
            "file_id": row[0],
            "filename": row[1],
            "content_type": row[2],
            "file_size": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]



def conversation_belongs_to(conversation_id: str, user_id: str | None) -> bool:
    if not user_id:
        return True
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM conversations
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )
            return cur.fetchone() is not None


def create_user(username: str, email: str, password: str) -> dict[str, str]:
    init_db()
    user_id = str(uuid.uuid4())
    salt, password_hash = _hash_password(password)
    normalized_email = email.strip().lower()
    normalized_username = username.strip()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, username, email, password_salt, password_hash)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, normalized_username, normalized_email, salt, password_hash),
            )
        conn.commit()

    return {"user_id": user_id, "username": normalized_username, "email": normalized_email}


def authenticate_user(identifier: str, password: str) -> dict[str, str] | None:
    init_db()
    normalized = identifier.strip().lower()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, username, email, password_salt, password_hash
                FROM users
                WHERE lower(email) = %s OR lower(username) = %s
                """,
                (normalized, normalized),
            )
            row = cur.fetchone()

    if row is None:
        return None
    if not _password_matches(password, row[3], row[4]):
        return None
    return {"user_id": row[0], "username": row[1], "email": row[2]}


def set_pending_clarification(conversation_id: str, original_question: str, missing_target: str | None = None) -> None:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_state (conversation_id, pending_type, original_question, missing_target)
                VALUES (%s, 'clarification', %s, %s)
                ON CONFLICT (conversation_id) DO UPDATE SET
                    pending_type = EXCLUDED.pending_type,
                    original_question = EXCLUDED.original_question,
                    missing_target = EXCLUDED.missing_target,
                    created_at = NOW()
                """,
                (conversation_id, original_question, missing_target),
            )
        conn.commit()


def get_pending_clarification(conversation_id: str) -> dict[str, str | None] | None:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT original_question, missing_target
                FROM conversation_state
                WHERE conversation_id = %s
                  AND pending_type = 'clarification'
                """,
                (conversation_id,),
            )
            row = cur.fetchone()

    if row is None:
        return None
    return {"original_question": row[0], "missing_target": row[1]}


def clear_pending_clarification(conversation_id: str) -> None:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM conversation_state
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
        conn.commit()
