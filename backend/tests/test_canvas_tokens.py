from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from platform_app import canvas_tokens


class Result:
    def __init__(self, row=None, rowcount=0):
        self.row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.record = None

    def execute(self, statement, parameters=()):
        sql = " ".join(statement.split()).upper()
        if sql.startswith("INSERT INTO"):
            now = datetime.now(timezone.utc)
            self.record = {
                "user_id": parameters[0],
                "origin": parameters[1],
                "nonce": parameters[2],
                "ciphertext": parameters[3],
                "connected_at": now,
                "verified_at": now,
            }
            return Result(rowcount=1)
        if "SELECT CANVAS_ORIGIN, TOKEN_NONCE, TOKEN_CIPHERTEXT, CONNECTED_AT" in sql:
            row = None
            if self.record and self.record["user_id"] == parameters[0]:
                row = (
                    self.record["origin"],
                    self.record["nonce"],
                    self.record["ciphertext"],
                    self.record["connected_at"],
                    self.record["verified_at"],
                )
            return Result(row)
        if "SELECT CANVAS_ORIGIN, TOKEN_NONCE, TOKEN_CIPHERTEXT" in sql:
            row = None
            if self.record and self.record["user_id"] == parameters[0]:
                row = (
                    self.record["origin"],
                    self.record["nonce"],
                    self.record["ciphertext"],
                )
            return Result(row)
        if sql.startswith("UPDATE"):
            if self.record:
                self.record["verified_at"] = datetime.now(timezone.utc)
            return Result(rowcount=1 if self.record else 0)
        if sql.startswith("DELETE"):
            deleted = bool(self.record and self.record["user_id"] == parameters[0])
            if deleted:
                self.record = None
            return Result(rowcount=int(deleted))
        raise AssertionError(f"Unexpected SQL: {sql}")


def test_canvas_token_is_encrypted_and_reused_without_exposure(monkeypatch):
    connection = Connection()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setenv("CANVAS_TOKEN_ENCRYPTION_KEY", "a" * 48)
    monkeypatch.setattr(canvas_tokens.db, "get_connection", get_connection)

    canvas_tokens.save("professor-id", "canvas-personal-token")

    assert b"canvas-personal-token" not in connection.record["ciphertext"]
    assert canvas_tokens.load("professor-id") == "canvas-personal-token"
    status = canvas_tokens.status("professor-id")
    assert status["connected"] is True
    assert "token" not in status

    assert canvas_tokens.delete("professor-id") is True
    assert canvas_tokens.status("professor-id")["connected"] is False


def test_canvas_token_storage_requires_a_dedicated_secret(monkeypatch):
    monkeypatch.delenv("CANVAS_TOKEN_ENCRYPTION_KEY", raising=False)
    assert canvas_tokens.is_configured() is False

    monkeypatch.setenv(
        "CANVAS_TOKEN_ENCRYPTION_KEY",
        "generate-a-different-random-value-of-at-least-32-characters",
    )
    assert canvas_tokens.is_configured() is False


def test_corrupted_canvas_token_requires_reconnection(monkeypatch):
    connection = Connection()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setenv("CANVAS_TOKEN_ENCRYPTION_KEY", "a" * 48)
    monkeypatch.setattr(canvas_tokens.db, "get_connection", get_connection)
    canvas_tokens.save("professor-id", "canvas-personal-token")

    ciphertext = connection.record["ciphertext"]
    connection.record["ciphertext"] = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]

    with pytest.raises(canvas_tokens.CanvasTokenReconnectRequired):
        canvas_tokens.load("professor-id")
    assert canvas_tokens.status("professor-id") == {
        "connected": False,
        "encryption_configured": True,
        "reconnect_required": True,
    }


def test_canvas_token_is_bound_to_its_professor(monkeypatch):
    connection = Connection()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setenv("CANVAS_TOKEN_ENCRYPTION_KEY", "a" * 48)
    monkeypatch.setattr(canvas_tokens.db, "get_connection", get_connection)
    canvas_tokens.save("first-professor", "canvas-personal-token")

    connection.record["user_id"] = "second-professor"
    with pytest.raises(canvas_tokens.CanvasTokenReconnectRequired):
        canvas_tokens.load("second-professor")
