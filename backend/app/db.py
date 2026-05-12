from __future__ import annotations

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


def is_enabled() -> bool:
    return bool(settings.DATABASE_URL)


def init_db() -> None:
    if not is_enabled():
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
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
                CREATE TABLE IF NOT EXISTS rag_files (
                    id UUID PRIMARY KEY,
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
                CREATE INDEX IF NOT EXISTS idx_rag_files_created_at
                ON rag_files(created_at DESC)
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


def ensure_conversation(conversation_id: str | None, title: str = "New conversation") -> str:
    init_db()
    resolved_id = conversation_id or str(uuid.uuid4())

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (id, title)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET updated_at = NOW()
                """,
                (resolved_id, title[:120] or "New conversation"),
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


def list_conversations(limit: int = 50) -> list[dict[str, object]]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
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


def save_rag_file(filename: str, content_type: str, content: bytes) -> str | None:
    if not is_enabled():
        return None

    init_db()
    file_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_files (id, filename, content_type, file_size, content)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (file_id, filename, content_type or "application/octet-stream", len(content), content),
            )
        conn.commit()

    return file_id


def list_rag_files(limit: int = 50) -> list[dict[str, object]]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
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
