"""Database-free tests for password validation and forced-change access."""

import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from starlette.requests import Request

from app.core.security import make_token, password_hasher, user_id_from_token
from app.db import connection as db_connection
from app.dependencies.auth import get_current_user
from app.modules.auth.schemas import ChangePasswordPayload
from app.modules.auth.schemas import LoginPayload
from app.modules.auth import service as auth_service
from app.modules.users import service as users_service


class PasswordPayloadTests(unittest.TestCase):
    def test_accepts_valid_password_and_matching_confirmation(self):
        payload = ChangePasswordPayload(
            current_password="OldPass123456",
            new_password="NewPass123456",
            confirm_password="NewPass123456",
        )
        self.assertEqual(payload.new_password, "NewPass123456")

    def test_rejects_confirmation_mismatch(self):
        with self.assertRaises(ValidationError):
            ChangePasswordPayload(
                current_password="OldPass123456",
                new_password="NewPass123456",
                confirm_password="OtherPass1234",
            )

    def test_rejects_short_password(self):
        with self.assertRaises(ValidationError):
            ChangePasswordPayload(
                current_password="OldPass123456",
                new_password="short1",
                confirm_password="short1",
            )

    def test_rejects_password_without_number(self):
        with self.assertRaises(ValidationError):
            ChangePasswordPayload(
                current_password="OldPass123456",
                new_password="LongEnoughPassword",
                confirm_password="LongEnoughPassword",
            )


class TokenVersionTests(unittest.TestCase):
    def test_token_contains_auth_version(self):
        token = make_token({"user_id": 41}, auth_version=7)
        self.assertEqual(user_id_from_token(token), (41, 7))


class DatabaseConfigurationTests(unittest.TestCase):
    def test_blank_whitespace_credentials_use_windows_authentication(self):
        with patch.object(db_connection, "DB_USER", "  "), patch.object(
            db_connection, "DB_PASSWORD", " \t "
        ), patch.object(db_connection.pyodbc, "connect", return_value=object()) as connect:
            db_connection.get_connection()
        connection_string = connect.call_args.args[0]
        self.assertIn("Trusted_Connection=yes;", connection_string)
        self.assertNotIn("UID=", connection_string)


class ForcedChangeAccessTests(unittest.TestCase):
    @staticmethod
    def request(path, method="GET"):
        return Request({"type": "http", "method": method, "path": path, "headers": []})

    def call_dependency(self, request):
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test")
        with patch("app.dependencies.auth.user_id_from_token", return_value=(5, 2)), patch(
            "app.dependencies.auth.get_authenticated_user",
            return_value={"user_id": 5, "must_change_password": True},
        ):
            return get_current_user(request, credentials)

    def test_forced_user_can_read_me(self):
        user = self.call_dependency(self.request("/api/v1/auth/me"))
        self.assertEqual(user["user_id"], 5)

    def test_forced_user_can_change_password(self):
        user = self.call_dependency(self.request("/api/v1/auth/change-password", "POST"))
        self.assertEqual(user["user_id"], 5)

    def test_forced_user_cannot_access_dashboard(self):
        with self.assertRaises(HTTPException) as raised:
            self.call_dependency(self.request("/api/v1/dashboard"))
        self.assertEqual(raised.exception.status_code, 403)


class FakeConnection:
    committed = False

    def commit(self):
        self.committed = True


class PasswordServiceTests(unittest.TestCase):
    def test_expired_temporary_password_is_rejected_at_login(self):
        row = (
            5, "worker", "Worker", "worker@example.com", "WORKER", "ACTIVE",
            password_hasher.hash("TemporaryPass123"), 2, "ACTIVE", 1, True, 4,
            datetime.utcnow() - timedelta(hours=1),
        )
        with patch("app.modules.auth.service.database_connection", return_value=nullcontext(FakeConnection())), patch(
            "app.modules.auth.service.database_cursor", return_value=nullcontext(object())
        ), patch("app.modules.auth.service.repository.get_login_user_by_username", return_value=row):
            with self.assertRaises(HTTPException) as raised:
                auth_service.login(LoginPayload(username="worker", password="TemporaryPass123"))
        self.assertEqual(raised.exception.status_code, 403)
        self.assertIn("expired", raised.exception.detail)

    def test_successful_password_change_updates_existing_user_and_audits(self):
        connection = FakeConnection()
        payload = ChangePasswordPayload(
            current_password="OldPass123456",
            new_password="NewPass123456",
            confirm_password="NewPass123456",
        )
        old_hash = password_hasher.hash("OldPass123456")
        with patch("app.modules.auth.service.database_connection", return_value=nullcontext(connection)), patch(
            "app.modules.auth.service.database_cursor", return_value=nullcontext(object())
        ), patch("app.modules.auth.service.repository.get_password_credentials", return_value=(old_hash, 0, 3)), patch(
            "app.modules.auth.service.repository.update_own_password", return_value=type("Result", (), {"rowcount": 1})()
        ) as update, patch("app.modules.auth.service.repository.insert_password_audit") as audit:
            result = auth_service.change_password({"user_id": 9}, payload, "127.0.0.1")

        self.assertTrue(connection.committed)
        self.assertEqual(result["password_changed"], True)
        self.assertEqual(update.call_args.args[1:3], (9, 3))
        password_hasher.verify(update.call_args.args[3], "NewPass123456")
        self.assertEqual(audit.call_args.args[1:4], (9, 9, "PASSWORD_CHANGED"))

    def test_company_admin_cannot_reset_own_password_administratively(self):
        actor = {"user_id": 9, "company_id": 1, "role_name": "COMPANY_ADMIN"}
        with patch("app.modules.users.service._company_for_actor", return_value=1), patch(
            "app.modules.users.service._require"
        ):
            with self.assertRaises(HTTPException) as raised:
                users_service.reset_company_user_password(actor, 1, 9)
        self.assertEqual(raised.exception.status_code, 400)

    def test_company_admin_cannot_reset_platform_super_admin(self):
        actor = {"user_id": 9, "company_id": 1, "role_name": "COMPANY_ADMIN"}
        connection = FakeConnection()
        with patch("app.modules.users.service._company_for_actor", return_value=1), patch(
            "app.modules.users.service._require"
        ), patch("app.modules.users.service.database_connection", return_value=nullcontext(connection)), patch(
            "app.modules.users.service.database_cursor", return_value=nullcontext(object())
        ), patch("app.modules.users.service.repository.get_company_user", return_value=(2, "root", "Root", "root@example.com", "SUPER_ADMIN")), patch(
            "app.modules.users.service.generate_temporary_password"
        ) as generate:
            with self.assertRaises(HTTPException) as raised:
                users_service.reset_company_user_password(actor, 1, 2)
        self.assertEqual(raised.exception.status_code, 403)
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
