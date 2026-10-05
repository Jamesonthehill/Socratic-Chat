from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request

from app import settings


# Local-only fallback. Restricted school-account mode must supply a persistent
# AUTH_SESSION_SECRET so sessions survive server restarts and can be verified.
_DEVELOPMENT_SESSION_SECRET = secrets.token_urlsafe(48).encode("utf-8")


def _encode(value: bytes) -> str:
    # URL-safe Base64 lets the signed payload travel in an HTTP header.
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    # Restore omitted padding before decoding a token received from the client.
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _session_secret() -> bytes:
    # Never accept an ephemeral secret when restricted school login is active:
    # a restart would invalidate every session without an explicit setting.
    if not settings.AUTH_SESSION_SECRET:
        if not settings.SCHOOL_GOOGLE_AUTH_ENABLED:
            return _DEVELOPMENT_SESSION_SECRET
        raise HTTPException(status_code=503, detail="AUTH_SESSION_SECRET is not configured.")
    return settings.AUTH_SESSION_SECRET.encode("utf-8")


def issue_session(user_id: str) -> tuple[str, int]:
    # Store only the user's ID and a bounded lifetime in the signed session;
    # permissions are checked against the database on protected requests.
    now = int(time.time())
    expires_in_seconds = max(1, settings.AUTH_SESSION_MINUTES) * 60
    payload = {
        "typ": "session",
        "sub": user_id,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    # HMAC detects client-side changes to the user ID or expiration time.
    signature = hmac.new(_session_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_encode(signature)}", expires_in_seconds


def verify_session(token: str) -> dict[str, Any]:
    # A valid token needs both a well-formed payload and a matching signature.
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        actual_signature = _decode(encoded_signature)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Session token is invalid.") from None

    expected_signature = hmac.new(
        _session_secret(), encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()
    # Constant-time comparison avoids leaking signature information through
    # ordinary string-comparison timing differences.
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise HTTPException(status_code=401, detail="Session token is invalid.")

    try:
        payload = json.loads(_decode(encoded_payload))
        token_type = str(payload["typ"])
        user_id = str(payload["sub"]).strip()
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Session token is invalid.") from None

    # Even a correctly signed token cannot be used after its expiration.
    if token_type != "session" or not user_id or expires_at <= int(time.time()):
        raise HTTPException(status_code=401, detail="Session has expired.")
    return payload


def current_user_id(request: Request, required: bool = True) -> str | None:
    # Protected routes read the Bearer token rather than trusting an ID sent
    # freely by the browser.
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return str(verify_session(token)["sub"])

    # Backward compatibility is available only while the app is not in its
    # restricted school-account mode.
    if not settings.SCHOOL_GOOGLE_AUTH_ENABLED:
        legacy_user_id = request.headers.get("x-user-id", "").strip()
        if legacy_user_id:
            return legacy_user_id

    if required:
        raise HTTPException(status_code=401, detail="Please sign in with your school account.")
    return None
