from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app import auth, settings
from app.main import _verify_google_credential


class SessionTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_secret = settings.AUTH_SESSION_SECRET
        self.original_minutes = settings.AUTH_SESSION_MINUTES
        settings.AUTH_SESSION_SECRET = "test-secret-that-is-not-used-outside-tests"
        settings.AUTH_SESSION_MINUTES = 60

    def tearDown(self) -> None:
        settings.AUTH_SESSION_SECRET = self.original_secret
        settings.AUTH_SESSION_MINUTES = self.original_minutes

    def test_issued_session_verifies_user(self) -> None:
        token, expires_in = auth.issue_session("user-123")
        self.assertEqual(auth.verify_session(token)["sub"], "user-123")
        self.assertEqual(expires_in, 3600)

    def test_modified_session_is_rejected(self) -> None:
        token, _ = auth.issue_session("user-123")
        payload, signature = token.split(".", 1)
        modified = f"{payload}x.{signature}"
        with self.assertRaises(HTTPException) as context:
            auth.verify_session(modified)
        self.assertEqual(context.exception.status_code, 401)


class SchoolGoogleAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_client_id = settings.GOOGLE_CLIENT_ID
        self.original_enabled = settings.SCHOOL_GOOGLE_AUTH_ENABLED
        self.original_domains = settings.ALLOWED_GOOGLE_DOMAINS
        settings.GOOGLE_CLIENT_ID = "client.apps.googleusercontent.com"
        settings.SCHOOL_GOOGLE_AUTH_ENABLED = True
        settings.ALLOWED_GOOGLE_DOMAINS = {"charlotte.edu"}

    def tearDown(self) -> None:
        settings.GOOGLE_CLIENT_ID = self.original_client_id
        settings.SCHOOL_GOOGLE_AUTH_ENABLED = self.original_enabled
        settings.ALLOWED_GOOGLE_DOMAINS = self.original_domains

    @patch("app.main.google_id_token.verify_oauth2_token")
    def test_charlotte_workspace_account_is_allowed(self, verify_token) -> None:
        verify_token.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-user-1",
            "email": "student@charlotte.edu",
            "email_verified": True,
            "hd": "charlotte.edu",
        }
        profile = _verify_google_credential("credential")
        self.assertEqual(profile["email"], "student@charlotte.edu")

    @patch("app.main.google_id_token.verify_oauth2_token")
    def test_personal_google_account_is_rejected(self, verify_token) -> None:
        verify_token.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-user-2",
            "email": "student@gmail.com",
            "email_verified": True,
        }
        with self.assertRaises(HTTPException) as context:
            _verify_google_credential("credential")
        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
