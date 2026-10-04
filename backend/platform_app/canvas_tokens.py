"""Encrypted, server-side storage for instructor Canvas API tokens."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app import db
from platform_app.canvas_lms import CANVAS_ORIGIN


AAD_PREFIX = b"socratic-chat:canvas-token:v1"
UNSAFE_EXAMPLE_SECRETS = {
    "generate-a-different-random-value-of-at-least-32-characters",
}


class CanvasTokenConfigurationError(RuntimeError):
    pass


class CanvasTokenReconnectRequired(RuntimeError):
    pass


def _secret() -> str:
    value = os.getenv("CANVAS_TOKEN_ENCRYPTION_KEY", "").strip()
    if len(value) < 32 or value in UNSAFE_EXAMPLE_SECRETS:
        raise CanvasTokenConfigurationError(
            "Canvas token storage is not configured on this server."
        )
    return value


def is_configured() -> bool:
    try:
        _secret()
    except CanvasTokenConfigurationError:
        return False
    return True


def _key() -> bytes:
    return hashlib.sha256(b"canvas-token-key\0" + _secret().encode("utf-8")).digest()


def _aad(user_id: str, canvas_origin: str) -> bytes:
    return b"\0".join(
        (AAD_PREFIX, str(user_id).encode("utf-8"), canvas_origin.encode("utf-8"))
    )


def _decrypt(user_id: str, canvas_origin: str, nonce: object, ciphertext: object) -> str:
    try:
        return AESGCM(_key()).decrypt(
            bytes(nonce),
            bytes(ciphertext),
            _aad(user_id, canvas_origin),
        ).decode("utf-8")
    except (InvalidTag, UnicodeDecodeError, ValueError) as error:
        raise CanvasTokenReconnectRequired(
            "Your saved Canvas connection can no longer be opened. Reconnect Canvas."
        ) from error


def save(user_id: str, access_token: str) -> None:
    nonce = os.urandom(12)
    encrypted = AESGCM(_key()).encrypt(
        nonce,
        access_token.encode("utf-8"),
        _aad(user_id, CANVAS_ORIGIN),
    )
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO canvas_api_connections_platform (
                user_id, canvas_origin, token_nonce, token_ciphertext,
                connected_at, updated_at, last_verified_at
            )
            VALUES (%s, %s, %s, %s, NOW(), NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                canvas_origin = EXCLUDED.canvas_origin,
                token_nonce = EXCLUDED.token_nonce,
                token_ciphertext = EXCLUDED.token_ciphertext,
                updated_at = NOW(),
                last_verified_at = NOW()
            """,
            (user_id, CANVAS_ORIGIN, nonce, encrypted),
        )


def load(user_id: str) -> str | None:
    _secret()
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT canvas_origin, token_nonce, token_ciphertext
            FROM canvas_api_connections_platform
            WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    canvas_origin = str(row[0])
    if canvas_origin != CANVAS_ORIGIN:
        raise CanvasTokenReconnectRequired(
            "Your saved Canvas connection belongs to a different Canvas server. Reconnect Canvas."
        )
    return _decrypt(user_id, canvas_origin, row[1], row[2])


def status(user_id: str) -> dict[str, object]:
    if not is_configured():
        return {"connected": False, "encryption_configured": False}
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT canvas_origin, token_nonce, token_ciphertext, connected_at, last_verified_at
            FROM canvas_api_connections_platform
            WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return {"connected": False, "encryption_configured": True}
    canvas_origin = str(row[0])
    if canvas_origin != CANVAS_ORIGIN:
        return {
            "connected": False,
            "encryption_configured": True,
            "reconnect_required": True,
        }
    try:
        _decrypt(user_id, canvas_origin, row[1], row[2])
    except CanvasTokenReconnectRequired:
        return {
            "connected": False,
            "encryption_configured": True,
            "reconnect_required": True,
        }
    return {
        "connected": True,
        "encryption_configured": True,
        "canvas_origin": canvas_origin,
        "connected_at": _isoformat(row[3]),
        "last_verified_at": _isoformat(row[4]),
    }


def mark_verified(user_id: str) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE canvas_api_connections_platform
            SET last_verified_at = NOW(), updated_at = NOW()
            WHERE user_id = %s AND canvas_origin = %s
            """,
            (user_id, CANVAS_ORIGIN),
        )


def delete(user_id: str) -> bool:
    with db.get_connection() as conn:
        result = conn.execute(
            """
            DELETE FROM canvas_api_connections_platform
            WHERE user_id = %s AND canvas_origin = %s
            """,
            (user_id, CANVAS_ORIGIN),
        )
        return result.rowcount > 0


def _isoformat(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
