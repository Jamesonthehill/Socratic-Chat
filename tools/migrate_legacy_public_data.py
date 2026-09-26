"""Copy legacy public Socratic-Chat data into the namespaced platform schema.

The migration is transactional and idempotent. Existing source tables and rows
remain untouched. Run from the repository root after backing up Supabase.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

PLATFORM = os.getenv("PLATFORM_DB_SCHEMA", "platform")
SOCRATIC = os.getenv("SOCRATIC_DB_SCHEMA", "socratic_chat")


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f'"{schema}"."{table}"',))
    return bool(cur.fetchone()[0])


def _require_tables(cur) -> None:
    required = (
        ("public", "users"),
        (PLATFORM, "users_platform"),
        (PLATFORM, "courses_platform"),
        (PLATFORM, "course_memberships_platform"),
        (SOCRATIC, "conversations_socratic_chat"),
        (SOCRATIC, "conversation_messages_socratic_chat"),
        (SOCRATIC, "rag_files_socratic_chat"),
        (SOCRATIC, "document_chunks_socratic_chat"),
    )
    missing = [f"{schema}.{table}" for schema, table in required if not _table_exists(cur, schema, table)]
    if missing:
        raise RuntimeError(f"Required migration tables are missing: {', '.join(missing)}")


def _qualified(schema: str, table: str):
    return sql.Identifier(schema, table)


def _build_identity_maps(cur) -> None:
    users = _qualified(PLATFORM, "users_platform")
    courses = _qualified(PLATFORM, "courses_platform")
    cur.execute("CREATE TEMP TABLE legacy_user_map (old_id UUID PRIMARY KEY, new_id UUID NOT NULL)")
    cur.execute(
        sql.SQL(
            """
            INSERT INTO legacy_user_map (old_id, new_id)
            SELECT legacy.id, COALESCE(
                (
                    SELECT current.id
                    FROM {users} current
                    WHERE current.id = legacy.id
                       OR lower(current.email) = lower(legacy.email)
                       OR (
                            legacy.github_id IS NOT NULL
                            AND current.github_id = legacy.github_id
                       )
                    ORDER BY (current.id = legacy.id) DESC
                    LIMIT 1
                ),
                legacy.id
            )
            FROM public.users legacy
            """
        ).format(users=users)
    )
    duplicate_users = cur.execute(
        """
        SELECT new_id
        FROM legacy_user_map
        GROUP BY new_id
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    if duplicate_users:
        raise RuntimeError("Multiple legacy users resolve to the same namespaced account.")

    cur.execute("CREATE TEMP TABLE legacy_course_map (old_id UUID PRIMARY KEY, new_id UUID NOT NULL)")
    if _table_exists(cur, "public", "courses"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO legacy_course_map (old_id, new_id)
                SELECT legacy.id, COALESCE(
                    (
                        SELECT current.id
                        FROM {courses} current
                        JOIN legacy_user_map instructor
                          ON instructor.old_id = legacy.instructor_id
                        WHERE current.id = legacy.id
                           OR (
                                current.instructor_id = instructor.new_id
                                AND lower(current.course_code) = lower(legacy.course_code)
                           )
                        ORDER BY (current.id = legacy.id) DESC
                        LIMIT 1
                    ),
                    legacy.id
                )
                FROM public.courses legacy
                """
            ).format(courses=courses)
        )


def _copy_platform_data(cur) -> None:
    users = _qualified(PLATFORM, "users_platform")
    courses = _qualified(PLATFORM, "courses_platform")
    memberships = _qualified(PLATFORM, "course_memberships_platform")

    cur.execute(
        sql.SQL(
            """
            INSERT INTO {users} (
                id, username, email, password_salt, password_hash, created_at,
                auth_provider, google_sub, github_id, github_username,
                github_linked_at, display_name, authority_level,
                requested_authority_level, onboarding_completed_at
            )
            SELECT map.new_id, legacy.username, legacy.email, legacy.password_salt,
                   legacy.password_hash, legacy.created_at, legacy.auth_provider,
                   legacy.google_sub, legacy.github_id, legacy.github_username,
                   legacy.github_linked_at, legacy.display_name,
                   legacy.authority_level, legacy.requested_authority_level,
                   legacy.onboarding_completed_at
            FROM public.users legacy
            JOIN legacy_user_map map ON map.old_id = legacy.id
            WHERE NOT EXISTS (SELECT 1 FROM {users} current WHERE current.id = map.new_id)
            """
        ).format(users=users)
    )
    cur.execute(
        sql.SQL(
            """
            UPDATE {users} current
            SET username = legacy.username,
                email = legacy.email,
                password_salt = legacy.password_salt,
                password_hash = legacy.password_hash,
                created_at = LEAST(current.created_at, legacy.created_at),
                auth_provider = legacy.auth_provider,
                google_sub = COALESCE(current.google_sub, legacy.google_sub),
                github_id = COALESCE(current.github_id, legacy.github_id),
                github_username = COALESCE(current.github_username, legacy.github_username),
                github_linked_at = COALESCE(current.github_linked_at, legacy.github_linked_at),
                display_name = COALESCE(legacy.display_name, current.display_name),
                authority_level = LEAST(current.authority_level, legacy.authority_level),
                requested_authority_level = legacy.requested_authority_level,
                onboarding_completed_at = COALESCE(
                    legacy.onboarding_completed_at,
                    current.onboarding_completed_at
                )
            FROM public.users legacy
            JOIN legacy_user_map map ON map.old_id = legacy.id
            WHERE current.id = map.new_id
            """
        ).format(users=users)
    )

    if _table_exists(cur, "public", "courses"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {courses} (
                    id, course_code, title, description, instructor_id,
                    is_discoverable, created_at, updated_at
                )
                SELECT course_map.new_id, legacy.course_code, legacy.title,
                       legacy.description, user_map.new_id, legacy.is_discoverable,
                       legacy.created_at, legacy.updated_at
                FROM public.courses legacy
                JOIN legacy_course_map course_map ON course_map.old_id = legacy.id
                JOIN legacy_user_map user_map ON user_map.old_id = legacy.instructor_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM {courses} current WHERE current.id = course_map.new_id
                )
                """
            ).format(courses=courses)
        )

    if _table_exists(cur, "public", "course_memberships"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {memberships} (
                    id, course_id, user_id, course_role, status, requested_at,
                    reviewed_at, reviewed_by, rejection_reason
                )
                SELECT legacy.id, course_map.new_id, user_map.new_id,
                       legacy.course_role, legacy.status, legacy.requested_at,
                       legacy.reviewed_at, reviewer.new_id, legacy.rejection_reason
                FROM public.course_memberships legacy
                JOIN legacy_course_map course_map ON course_map.old_id = legacy.course_id
                JOIN legacy_user_map user_map ON user_map.old_id = legacy.user_id
                LEFT JOIN legacy_user_map reviewer ON reviewer.old_id = legacy.reviewed_by
                ON CONFLICT (course_id, user_id) DO UPDATE
                SET course_role = EXCLUDED.course_role,
                    status = EXCLUDED.status,
                    requested_at = EXCLUDED.requested_at,
                    reviewed_at = EXCLUDED.reviewed_at,
                    reviewed_by = EXCLUDED.reviewed_by,
                    rejection_reason = EXCLUDED.rejection_reason
                """
            ).format(memberships=memberships)
        )


def _copy_socratic_data(cur) -> None:
    conversations = _qualified(SOCRATIC, "conversations_socratic_chat")
    messages = _qualified(SOCRATIC, "conversation_messages_socratic_chat")
    states = _qualified(SOCRATIC, "conversation_state_socratic_chat")
    files = _qualified(SOCRATIC, "rag_files_socratic_chat")
    chunks = _qualified(SOCRATIC, "document_chunks_socratic_chat")
    progress = _qualified(SOCRATIC, "student_concept_progress_socratic_chat")
    assessments = _qualified(SOCRATIC, "mastery_assessments_socratic_chat")

    if _table_exists(cur, "public", "conversations"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {conversations} (
                    id, title, created_at, updated_at, user_id, course_id,
                    conversation_status, last_dialogue_status, active_concept,
                    completed_at, understanding_level, support_level
                )
                SELECT legacy.id, legacy.title, legacy.created_at, legacy.updated_at,
                       user_map.new_id, course_map.new_id, legacy.conversation_status,
                       legacy.last_dialogue_status, legacy.active_concept,
                       legacy.completed_at, legacy.understanding_level,
                       legacy.support_level
                FROM public.conversations legacy
                LEFT JOIN legacy_user_map user_map ON user_map.old_id = legacy.user_id
                LEFT JOIN legacy_course_map course_map ON course_map.old_id = legacy.course_id
                ON CONFLICT (id) DO NOTHING
                """
            ).format(conversations=conversations)
        )

    if _table_exists(cur, "public", "conversation_messages"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {messages} (id, conversation_id, role, content, created_at)
                SELECT id, conversation_id, role, content, created_at
                FROM public.conversation_messages
                ON CONFLICT (id) DO NOTHING
                """
            ).format(messages=messages)
        )

    if _table_exists(cur, "public", "conversation_state"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {states} (
                    conversation_id, pending_type, original_question,
                    missing_target, created_at
                )
                SELECT conversation_id, pending_type, original_question,
                       missing_target, created_at
                FROM public.conversation_state
                ON CONFLICT (conversation_id) DO NOTHING
                """
            ).format(states=states)
        )

    if _table_exists(cur, "public", "rag_files"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {files} (
                    id, conversation_id, filename, content_type, file_size,
                    content, created_at, user_id, course_id, document_id,
                    is_published
                )
                SELECT legacy.id, legacy.conversation_id, legacy.filename,
                       legacy.content_type, legacy.file_size, legacy.content,
                       legacy.created_at, user_map.new_id, course_map.new_id,
                       legacy.document_id, legacy.is_published
                FROM public.rag_files legacy
                LEFT JOIN legacy_user_map user_map ON user_map.old_id = legacy.user_id
                LEFT JOIN legacy_course_map course_map ON course_map.old_id = legacy.course_id
                ON CONFLICT (id) DO NOTHING
                """
            ).format(files=files)
        )

    if _table_exists(cur, "public", "document_chunks"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {chunks} (
                    id, file_id, document_id, conversation_id, course_id,
                    chunk_index, page_number, title, chunk_text, metadata,
                    embedding_model, embedding, created_at
                )
                SELECT legacy.id, legacy.file_id, legacy.document_id,
                       legacy.conversation_id, course_map.new_id,
                       legacy.chunk_index, legacy.page_number, legacy.title,
                       legacy.chunk_text, legacy.metadata, legacy.embedding_model,
                       legacy.embedding, legacy.created_at
                FROM public.document_chunks legacy
                LEFT JOIN legacy_course_map course_map ON course_map.old_id = legacy.course_id
                ON CONFLICT (id) DO NOTHING
                """
            ).format(chunks=chunks)
        )

    if _table_exists(cur, "public", "student_concept_progress"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {progress} (
                    user_id, course_id, concept, estimated_mastery,
                    evidence_count, status, critical_misconception,
                    last_assessed_at
                )
                SELECT user_map.new_id, course_map.new_id, legacy.concept,
                       legacy.estimated_mastery, legacy.evidence_count,
                       legacy.status, legacy.critical_misconception,
                       legacy.last_assessed_at
                FROM public.student_concept_progress legacy
                JOIN legacy_user_map user_map ON user_map.old_id = legacy.user_id
                JOIN legacy_course_map course_map ON course_map.old_id = legacy.course_id
                ON CONFLICT (user_id, course_id, concept) DO UPDATE
                SET estimated_mastery = EXCLUDED.estimated_mastery,
                    evidence_count = EXCLUDED.evidence_count,
                    status = EXCLUDED.status,
                    critical_misconception = EXCLUDED.critical_misconception,
                    last_assessed_at = EXCLUDED.last_assessed_at
                """
            ).format(progress=progress)
        )

    if _table_exists(cur, "public", "mastery_assessments"):
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {assessments} (
                    id, conversation_id, student_message_id, user_id, course_id,
                    concept, keyword_coverage, semantic_alignment, rubric_score,
                    total_score, correctness, completeness, reasoning,
                    application, understanding_improved, critical_misconception,
                    evaluation, created_at
                )
                SELECT legacy.id, legacy.conversation_id, legacy.student_message_id,
                       user_map.new_id, course_map.new_id, legacy.concept,
                       legacy.keyword_coverage, legacy.semantic_alignment,
                       legacy.rubric_score, legacy.total_score, legacy.correctness,
                       legacy.completeness, legacy.reasoning, legacy.application,
                       legacy.understanding_improved, legacy.critical_misconception,
                       legacy.evaluation, legacy.created_at
                FROM public.mastery_assessments legacy
                JOIN legacy_user_map user_map ON user_map.old_id = legacy.user_id
                JOIN legacy_course_map course_map ON course_map.old_id = legacy.course_id
                ON CONFLICT (id) DO NOTHING
                """
            ).format(assessments=assessments)
        )

    cur.execute(
        sql.SQL(
            """
            SELECT setval(
                pg_get_serial_sequence(%s, 'id'),
                GREATEST(COALESCE((SELECT MAX(id) FROM {messages}), 1),
                         COALESCE((SELECT last_value FROM {sequence}), 1)),
                EXISTS (SELECT 1 FROM {messages})
            )
            """
        ).format(
            messages=messages,
            sequence=sql.Identifier(SOCRATIC, "conversation_messages_socratic_chat_id_seq"),
        ),
        (f"{SOCRATIC}.conversation_messages_socratic_chat",),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="execute and validate the complete migration, then roll it back",
    )
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    with psycopg.connect(database_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(716340024)")
            _require_tables(cur)
            _build_identity_maps(cur)
            _copy_platform_data(cur)
            _copy_socratic_data(cur)
            counts = cur.execute(
                sql.SQL(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM {users}),
                        (SELECT COUNT(*) FROM {courses}),
                        (SELECT COUNT(*) FROM {conversations}),
                        (SELECT COUNT(*) FROM {messages}),
                        (SELECT COUNT(*) FROM {files}),
                        (SELECT COUNT(*) FROM {chunks})
                    """
                ).format(
                    users=_qualified(PLATFORM, "users_platform"),
                    courses=_qualified(PLATFORM, "courses_platform"),
                    conversations=_qualified(SOCRATIC, "conversations_socratic_chat"),
                    messages=_qualified(SOCRATIC, "conversation_messages_socratic_chat"),
                    files=_qualified(SOCRATIC, "rag_files_socratic_chat"),
                    chunks=_qualified(SOCRATIC, "document_chunks_socratic_chat"),
                )
            ).fetchone()

        if args.dry_run:
            conn.rollback()
            action = "Dry run validated"
        else:
            conn.commit()
            action = "Migration completed"

    print(
        f"{action}: users={counts[0]}, courses={counts[1]}, "
        f"conversations={counts[2]}, messages={counts[3]}, "
        f"files={counts[4]}, chunks={counts[5]}"
    )


if __name__ == "__main__":
    main()
