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


_DEVELOPMENT_SESSION_SECRET = secrets.token_urlsafe(48).encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _session_secret() -> bytes:
    if not settings.AUTH_SESSION_SECRET:
        if not settings.RESTRICTED_SCHOOL_AUTH_ENABLED:
            return _DEVELOPMENT_SESSION_SECRET
        raise HTTPException(status_code=503, detail="AUTH_SESSION_SECRET is not configured.")
    return settings.AUTH_SESSION_SECRET.encode("utf-8")


def issue_session(user_id: str, *, canvas_course_id: str | None = None) -> tuple[str, int]:
    now = int(time.time())
    expires_in_seconds = max(1, settings.AUTH_SESSION_MINUTES) * 60
    payload = {
        "typ": "session",
        "sub": user_id,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    if canvas_course_id is not None:
        payload["canvas_course_id"] = canvas_course_id
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(_session_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_encode(signature)}", expires_in_seconds


def verify_session(token: str) -> dict[str, Any]:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        actual_signature = _decode(encoded_signature)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Session token is invalid.") from None

    expected_signature = hmac.new(
        _session_secret(), encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise HTTPException(status_code=401, detail="Session token is invalid.")

    try:
        payload = json.loads(_decode(encoded_payload))
        token_type = str(payload["typ"])
        user_id = str(payload["sub"]).strip()
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Session token is invalid.") from None

    if token_type != "session" or not user_id or expires_at <= int(time.time()):
        raise HTTPException(status_code=401, detail="Session has expired.")
    return payload


def request_session(request: Request) -> dict[str, Any] | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return verify_session(token)
    return None


def account_for_session(account: dict[str, Any], session: dict[str, Any] | None) -> dict[str, Any]:
    course_id = (session or {}).get("canvas_course_id")
    if not course_id:
        return account

    from app import db

    membership = db.get_course_membership(course_id, str(account["user_id"]))
    if not membership or membership["status"] != "approved":
        raise HTTPException(status_code=403, detail="Your Canvas course access is no longer approved.")
    if membership["course_role"] == "student":
        return {**account, "authority_level": 2, "role": "student"}
    return account


def current_user_id(request: Request, required: bool = True) -> str | None:
    session = request_session(request)
    if session:
        return str(session["sub"])

    # Backward compatibility is available only while the app is not in its
    # restricted school-account mode.
    if not settings.RESTRICTED_SCHOOL_AUTH_ENABLED:
        legacy_user_id = request.headers.get("x-user-id", "").strip()
        if legacy_user_id:
            return legacy_user_id

    if required:
        raise HTTPException(status_code=401, detail="Please sign in with your verified school account.")
    return None
