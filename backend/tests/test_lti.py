"""Canvas LTI 1.3 launch tests; database flows use only a disposable schema."""
from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import auth, db, lti, main, settings


def _lti_settings() -> dict[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return {
        "LTI_CANVAS_ISSUER": "https://canvas.instructure.com",
        "LTI_CLIENT_ID": "canvas-client-123",
        "LTI_DEPLOYMENT_ID": "deployment-456",
        "LTI_PLATFORM_JWKS_URL": "https://sso.canvaslms.com/api/lti/security/jwks",
        "LTI_AUTHORIZATION_URL": "https://sso.canvaslms.com/api/lti/authorize_redirect",
        "LTI_PUBLIC_BASE_URL": "https://socratic.example",
        "LTI_TOOL_PRIVATE_KEY_B64": base64.b64encode(pem).decode(),
        "LTI_TOOL_KEY_ID": "socratic-test-key",
        "FRONTEND_URL": "https://frontend.example/Socratic-Chat/",
    }


def launch_claims(subject: str, context_id: str, role: str) -> dict[str, object]:
    return {
        "iss": settings.LTI_CANVAS_ISSUER,
        "sub": subject,
        "email": f"{subject}@charlotte.edu",
        "name": subject.replace("-", " ").title(),
        lti.DEPLOYMENT_CLAIM: settings.LTI_DEPLOYMENT_ID,
        lti.MESSAGE_TYPE_CLAIM: "LtiResourceLinkRequest",
        lti.VERSION_CLAIM: "1.3.0",
        lti.ROLES_CLAIM: [f"http://purl.imsglobal.org/vocab/lis/v2/membership#{role}"],
        lti.CONTEXT_CLAIM: {"id": context_id, "label": "ITCS 3155", "title": "Software Engineering"},
    }


class LTIConfiguredTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for name, value in _lti_settings().items():
            replacement = patch.object(settings, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.client = TestClient(main.app)

    def start_login(self) -> tuple[str, str]:
        response = self.client.post(
            "/api/lti/login",
            data={
                "iss": settings.LTI_CANVAS_ISSUER,
                "client_id": settings.LTI_CLIENT_ID,
                "login_hint": "canvas-login-hint",
                "lti_message_hint": "canvas-message-hint",
                "target_link_uri": f"{settings.LTI_PUBLIC_BASE_URL}/api/lti/launch",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302, response.text)
        location = urlparse(response.headers["location"])
        self.assertEqual(
            f"{location.scheme}://{location.netloc}{location.path}",
            "https://sso.canvaslms.com/api/lti/authorize_redirect",
        )
        query = parse_qs(location.query)
        self.assertEqual(query["redirect_uri"], [f"{settings.LTI_PUBLIC_BASE_URL}/api/lti/launch"])
        self.assertEqual(query["lti_message_hint"], ["canvas-message-hint"])
        return query["state"][0], query["nonce"][0]


class LTIConfigurationTests(LTIConfiguredTestCase):
    def test_status_reports_ready_configuration(self) -> None:
        response = self.client.get("/api/lti/status")
        self.assertEqual(response.json(), {"tool_configuration_ready": True, "launch_configured": True})

    def test_status_requires_https_public_url(self) -> None:
        with patch.object(settings, "LTI_PUBLIC_BASE_URL", "http://localhost:8001"):
            response = self.client.get("/api/lti/status")
        self.assertEqual(response.json(), {"tool_configuration_ready": False, "launch_configured": False})

    def test_exposes_canvas_course_navigation_configuration(self) -> None:
        response = self.client.get("/api/lti/canvas-config")
        self.assertEqual(response.status_code, 200)
        config = response.json()
        self.assertEqual(config["title"], "Socratic-Chat")
        self.assertEqual(config["oidc_initiation_url"], "https://socratic.example/api/lti/login")
        self.assertEqual(config["public_jwk_url"], "https://socratic.example/api/lti/jwks")
        self.assertEqual(
            config["extensions"][0]["settings"]["placements"],
            [
                {
                    "placement": "course_navigation",
                    "message_type": "LtiResourceLinkRequest",
                    "target_link_uri": "https://socratic.example/api/lti/launch",
                    "text": "Socratic-Chat",
                    "enabled": True,
                }
            ],
        )
        key = self.client.get("/api/lti/jwks").json()["keys"][0]
        self.assertEqual(key["kid"], "socratic-test-key")
        self.assertEqual(key["kty"], "RSA")
        self.assertNotIn("d", key)

    def test_unconfigured_server_rejects_launch_endpoints(self) -> None:
        with patch.object(settings, "LTI_CLIENT_ID", ""):
            response = self.client.get("/api/lti/login", params={"iss": settings.LTI_CANVAS_ISSUER})
        self.assertEqual(response.status_code, 503)

    def test_rejects_untrusted_issuer_client_and_launch_url(self) -> None:
        base = {
            "iss": settings.LTI_CANVAS_ISSUER,
            "client_id": settings.LTI_CLIENT_ID,
            "login_hint": "hint",
        }
        for override in (
            {"iss": "https://attacker.example"},
            {"client_id": "other-client"},
            {"target_link_uri": "https://attacker.example/api/lti/launch"},
        ):
            response = self.client.get("/api/lti/login", params={**base, **override}, follow_redirects=False)
            self.assertEqual(response.status_code, 400, override)

    def test_maps_canvas_roles(self) -> None:
        self.assertEqual(lti._lti_role(launch_claims("a", "c", "Instructor")), "instructor")
        self.assertEqual(lti._lti_role(launch_claims("a", "c", "TeachingAssistant")), "instructor")
        self.assertEqual(lti._lti_role(launch_claims("a", "c", "Learner")), "student")
        with self.assertRaises(HTTPException):
            lti._lti_role(launch_claims("a", "c", "Mentor"))

    def test_launch_verification_rejects_signature_nonce_and_deployment(self) -> None:
        class SigningKey:
            key = object()

        class JWKClient:
            def __init__(self, *args, **kwargs):
                pass

            def get_signing_key_from_jwt(self, token):
                return SigningKey()

        expected = {
            "nonce": "expected-nonce",
            "issuer": settings.LTI_CANVAS_ISSUER,
            "client_id": settings.LTI_CLIENT_ID,
        }
        claims = launch_claims("verified-user", "verified-course", "Learner")
        claims["nonce"] = "wrong-nonce"
        with patch.object(lti.jwt, "PyJWKClient", JWKClient), patch.object(
            lti.jwt, "decode", lambda *args, **kwargs: claims
        ):
            with self.assertRaisesRegex(HTTPException, "nonce"):
                lti._verify_launch_token("token", expected)
            claims["nonce"] = "expected-nonce"
            claims[lti.DEPLOYMENT_CLAIM] = "untrusted-deployment"
            with self.assertRaisesRegex(HTTPException, "deployment"):
                lti._verify_launch_token("token", expected)

        def invalid_signature(*args, **kwargs):
            raise jwt.InvalidSignatureError()

        with patch.object(lti.jwt, "PyJWKClient", JWKClient), patch.object(lti.jwt, "decode", invalid_signature):
            with self.assertRaisesRegex(HTTPException, "signature"):
                lti._verify_launch_token("token", expected)

    @patch("app.main.db.user_has_github", return_value=False)
    @patch("app.main.db.get_user_by_id", return_value={"onboarding_complete": True, "canvas_connected": True})
    def test_canvas_identity_satisfies_github_requirement(self, _get_user, _has_github) -> None:
        token, _ = auth.issue_session("canvas-user-1")
        request = main.Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        })
        with patch.object(settings, "REQUIRE_GITHUB_ACCOUNT", True):
            self.assertEqual(main._current_user_id(request), "canvas-user-1")


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL for PostgreSQL coverage.")
class LTIDatabaseTests(LTIConfiguredTestCase):
    def setUp(self) -> None:
        import psycopg
        from psycopg import sql

        dsn = os.environ["TEST_DATABASE_URL"]
        schema = "lti_test_" + uuid4().hex
        connection = psycopg.connect(dsn, autocommit=True)
        self.addCleanup(connection.close)
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        self.addCleanup(connection.execute, sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        for name, value in (
            ("DATABASE_URL", dsn),
            ("PLATFORM_DB_SCHEMA", schema),
            ("SOCRATIC_DB_SCHEMA", schema),
            ("OPENAI_API_KEY", ""),
            ("AUTH_SESSION_SECRET", "test-only-lti-session-secret"),
        ):
            replacement = patch.object(settings, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        super().setUp()
        db.init_db()

    def launch(self, claims: dict[str, object]):
        state, _nonce = self.start_login()
        with patch.object(lti, "_verify_launch_token", lambda token, expected: claims):
            return self.client.post(
                "/api/lti/launch",
                data={"state": state, "id_token": "signed-canvas-token"},
                follow_redirects=False,
            )

    def exchange(self, launch_response) -> dict[str, object]:
        self.assertEqual(launch_response.status_code, 303, launch_response.text)
        location = urlparse(launch_response.headers["location"])
        self.assertEqual(f"{location.scheme}://{location.netloc}{location.path}", settings.FRONTEND_URL)
        redirect = parse_qs(location.query)
        self.assertEqual(redirect["lti"], ["verified"])
        response = self.client.post("/api/lti/exchange", json={"code": redirect["code"][0]})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["course_id"], redirect["course"][0])
        body["code"] = redirect["code"][0]
        return body

    def test_instructor_then_student_launch_share_course_and_open_chat_access(self) -> None:
        instructor = self.exchange(self.launch(launch_claims("canvas-instructor", "course-101", "Instructor")))
        self.assertEqual(instructor["user"]["authority_level"], 1)
        self.assertTrue(instructor["user"]["onboarding_complete"])
        self.assertTrue(instructor["user"]["canvas_connected"])

        student = self.exchange(self.launch(launch_claims("canvas-student", "course-101", "Learner")))
        self.assertEqual(student["course_id"], instructor["course_id"])
        self.assertEqual(student["user"]["authority_level"], 2)
        self.assertTrue(db.user_can_access_course(student["course_id"], student["user"]["user_id"]))

        with patch.object(settings, "REQUIRE_GITHUB_ACCOUNT", True):
            courses = self.client.get(
                "/api/courses",
                headers={"Authorization": f"Bearer {student['access_token']}"},
            )
        self.assertEqual(courses.status_code, 200, courses.text)
        launched = [c for c in courses.json()["courses"] if c["course_id"] == student["course_id"]]
        self.assertEqual(launched[0]["membership_status"], "approved")

        replay = self.client.post("/api/lti/exchange", json={"code": instructor["code"]})
        self.assertEqual(replay.status_code, 401)

    def test_repeat_launch_reuses_identity(self) -> None:
        first = self.exchange(self.launch(launch_claims("repeat-instructor", "course-202", "Instructor")))
        second = self.exchange(self.launch(launch_claims("repeat-instructor", "course-202", "Instructor")))
        self.assertEqual(first["user"]["user_id"], second["user"]["user_id"])
        self.assertEqual(first["course_id"], second["course_id"])

    def test_student_cannot_create_course_before_instructor_launch(self) -> None:
        response = self.launch(launch_claims("early-student", "new-course", "Learner"))
        self.assertEqual(response.status_code, 409)
        self.assertIn("instructor must launch", response.json()["detail"].lower())

    def test_rejects_replayed_state(self) -> None:
        state, _nonce = self.start_login()
        claims = launch_claims("replay-instructor", "replay-course", "Instructor")
        with patch.object(lti, "_verify_launch_token", lambda token, expected: claims):
            first = self.client.post(
                "/api/lti/launch", data={"state": state, "id_token": "token"}, follow_redirects=False,
            )
            replay = self.client.post(
                "/api/lti/launch", data={"state": state, "id_token": "token"}, follow_redirects=False,
            )
        self.assertEqual(first.status_code, 303)
        self.assertEqual(replay.status_code, 401)


if __name__ == "__main__":
    unittest.main()
