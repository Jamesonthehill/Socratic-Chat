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
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS auth_provider TEXT NOT NULL DEFAULT 'password'
                """
            )
            cur.execute(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS google_sub TEXT UNIQUE
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS email_verification_codes (
                    id UUID PRIMARY KEY,
                    email TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    used_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_email_verification_codes_email_created_at
                ON email_verification_codes(email, created_at DESC)
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
                ALTER TABLE rag_files
                ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE
                """
            )
            cur.execute(
                """
                UPDATE rag_files rf
                SET user_id = c.user_id
                FROM conversations c
                WHERE rf.conversation_id = c.id
                  AND rf.user_id IS NULL
                  AND c.user_id IS NOT NULL
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
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_files_user_id_created_at
                ON rag_files(user_id, created_at DESC)
                """
            )
        conn.commit()


def _hash_email_code(email: str, code: str) -> str:
    normalized_email = email.strip().lower()
    normalized_code = code.strip()
    return hashlib.sha256(f"{normalized_email}:{normalized_code}".encode("utf-8")).hexdigest()


def save_email_verification_code(email: str, code: str, expires_in_minutes: int = 10) -> None:
    init_db()
    normalized_email = email.strip().lower()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_verification_codes (id, email, code_hash, expires_at)
                VALUES (%s, %s, %s, NOW() + (%s || ' minutes')::interval)
                """,
                (str(uuid.uuid4()), normalized_email, _hash_email_code(normalized_email, code), expires_in_minutes),
            )
        conn.commit()


def verify_email_code(email: str, code: str) -> bool:
    init_db()
    normalized_email = email.strip().lower()
    code_hash = _hash_email_code(normalized_email, code)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM email_verification_codes
                WHERE email = %s
                  AND code_hash = %s
                  AND used_at IS NULL
                  AND expires_at > NOW()
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (normalized_email, code_hash),
            )
            row = cur.fetchone()
            if row is None:
                return False

            cur.execute(
                """
                UPDATE email_verification_codes
                SET used_at = NOW()
                WHERE id = %s
                """,
                (row[0],),
            )
        conn.commit()

    return True


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


def set_conversation_title(conversation_id: str, title: str, user_id: str | None = None) -> None:
    init_db()
    clean_title = title.strip()[:120] or "New conversation"

    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    """
                    UPDATE conversations
                    SET title = %s,
                        updated_at = NOW()
                    WHERE id = %s
                      AND user_id = %s
                    """,
                    (clean_title, conversation_id, user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE conversations
                    SET title = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (clean_title, conversation_id),
                )
        conn.commit()


def rename_uploaded_document_chats() -> int:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH first_files AS (
                    SELECT DISTINCT ON (conversation_id)
                        conversation_id,
                        filename
                    FROM rag_files
                    WHERE conversation_id IS NOT NULL
                    ORDER BY conversation_id, created_at ASC
                )
                UPDATE conversations c
                SET title = LEFT(first_files.filename, 120),
                    updated_at = NOW()
                FROM first_files
                WHERE c.id = first_files.conversation_id
                  AND c.title IN ('New conversation', 'Uploaded documents')
                """
            )
            updated = cur.rowcount
        conn.commit()

    return updated


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


def save_rag_file(
    filename: str,
    content_type: str,
    content: bytes,
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> str | None:
    if not is_enabled():
        return None

    init_db()
    file_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_files (id, conversation_id, user_id, filename, content_type, file_size, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (file_id, conversation_id, user_id, filename, content_type or "application/octet-stream", len(content), content),
            )
        conn.commit()

    return file_id


def list_rag_files(
    limit: int = 50,
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, object]]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            conditions: list[str] = []
            params: list[object] = []

            if conversation_id:
                conditions.append("rf.conversation_id = %s")
                params.append(conversation_id)

            if user_id:
                conditions.append("(rf.user_id = %s OR c.user_id = %s)")
                params.extend([user_id, user_id])

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            cur.execute(
                f"""
                SELECT rf.id::text, rf.filename, rf.content_type, rf.file_size, rf.created_at::text
                FROM rag_files rf
                LEFT JOIN conversations c ON c.id = rf.conversation_id
                {where_clause}
                ORDER BY rf.created_at DESC
                LIMIT %s
                """,
                (*params, limit),
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


def get_rag_file(file_id: str, user_id: str | None = None) -> dict[str, object] | None:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            conditions = ["rf.id = %s"]
            params: list[object] = [file_id]

            if user_id:
                conditions.append("(rf.user_id = %s OR c.user_id = %s)")
                params.extend([user_id, user_id])

            where_clause = " AND ".join(conditions)
            cur.execute(
                f"""
                SELECT rf.id::text, rf.filename, rf.content_type, rf.file_size, rf.content
                FROM rag_files rf
                LEFT JOIN conversations c ON c.id = rf.conversation_id
                WHERE {where_clause}
                """,
                tuple(params),
            )
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "file_id": row[0],
        "filename": row[1],
        "content_type": row[2],
        "file_size": row[3],
        "content": bytes(row[4]),
    }


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


def get_user_by_email(email: str) -> dict[str, str] | None:
    init_db()
    normalized_email = email.strip().lower()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, username, email
                FROM users
                WHERE lower(email) = %s
                """,
                (normalized_email,),
            )
            row = cur.fetchone()

    if row is None:
        return None
    return {"user_id": row[0], "username": row[1], "email": row[2]}


def get_user_by_google_sub(google_sub: str) -> dict[str, str] | None:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, username, email
                FROM users
                WHERE google_sub = %s
                """,
                (google_sub,),
            )
            row = cur.fetchone()

    if row is None:
        return None
    return {"user_id": row[0], "username": row[1], "email": row[2]}


def _unique_username(cur: object, desired: str) -> str:
    base = "".join(ch for ch in desired.strip().lower() if ch.isalnum() or ch in {"_", "-", "."})
    base = (base or "google_user")[:60]
    candidate = base
    suffix = 1
    while True:
        cur.execute("SELECT 1 FROM users WHERE lower(username) = %s", (candidate.lower(),))
        if cur.fetchone() is None:
            return candidate
        suffix += 1
        candidate = f"{base[:54]}{suffix}"


def find_or_create_google_user(email: str, google_sub: str, name: str | None = None) -> dict[str, str]:
    init_db()
    normalized_email = email.strip().lower()

    existing = get_user_by_google_sub(google_sub) or get_user_by_email(normalized_email)
    if existing:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET google_sub = COALESCE(google_sub, %s),
                        auth_provider = CASE
                            WHEN auth_provider = 'password' THEN 'password_google'
                            ELSE auth_provider
                        END
                    WHERE id = %s
                    """,
                    (google_sub, existing["user_id"]),
                )
            conn.commit()
        return existing

    user_id = str(uuid.uuid4())
    salt, password_hash = _hash_password(secrets.token_urlsafe(32))
    desired_username = name or normalized_email.split("@", 1)[0]

    with get_connection() as conn:
        with conn.cursor() as cur:
            username = _unique_username(cur, desired_username)
            cur.execute(
                """
                INSERT INTO users (id, username, email, password_salt, password_hash, auth_provider, google_sub)
                VALUES (%s, %s, %s, %s, %s, 'google', %s)
                """,
                (user_id, username, normalized_email, salt, password_hash, google_sub),
            )
        conn.commit()

    return {"user_id": user_id, "username": username, "email": normalized_email}


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
