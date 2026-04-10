import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence.comparison_sqlite_store import ComparisonSqliteStore
from uac_grades.interfaces.api import create_comparison_app


class ComparisonSyncApiTests(unittest.TestCase):
    def _write_settings(self, root: Path, *, invites_contents: str) -> Settings:
        invites_path = root / "comparison_claim_invites.json"
        invites_path.write_text(invites_contents, encoding="utf-8")
        dotenv_path = root / ".env"
        dotenv_path.write_text(
            "\n".join(
                [
                    "UA_USUARIO=test@cloud.uautonoma.cl",
                    "UA_CONTRASENA=secret",
                    "UA_TOTP_SECRET=totp-secret",
                    f"UA_COMPARISON_SQLITE_PATH={root / 'comparison.sqlite3'}",
                    f"UA_COMPARISON_INVITES_PATH={invites_path}",
                ]
            ),
            encoding="utf-8",
        )
        return Settings.load(dotenv_path)

    def test_first_sync_claims_name_and_returns_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                root = Path(temp_dir)
                settings = self._write_settings(root, invites_contents=json.dumps({"Martin A.": "invite-123"}))
                client = TestClient(create_comparison_app(settings))

                response = client.post(
                    "/api/comparison/sync",
                    json={
                        "participant_name": "Martin A.",
                        "claim_code": "invite-123",
                        "courses": [],
                    },
                )

                with sqlite3.connect(root / "comparison.sqlite3") as connection:
                    synced_at = connection.execute(
                        "SELECT latest_synced_at FROM participants WHERE display_name = ?",
                        ("Martin A.",),
                    ).fetchone()[0]

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "linked")
        self.assertTrue(body["issued_sync_token"])
        self.assertEqual(body["synced_at"], synced_at)

    def test_malformed_sync_payload_returns_client_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                root = Path(temp_dir)
                settings = self._write_settings(root, invites_contents=json.dumps({"Martin A.": "invite-123"}))
                client = TestClient(create_comparison_app(settings))

                response = client.post(
                    "/api/comparison/sync",
                    json={
                        "participant_name": "Martin A.",
                        "claim_code": "invite-123",
                        "courses": "not-a-list",
                    },
                )

        self.assertEqual(response.status_code, 422)

    def test_failed_first_sync_does_not_consume_invite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                root = Path(temp_dir)
                settings = self._write_settings(root, invites_contents=json.dumps({"Martin A.": "invite-123"}))
                client = TestClient(create_comparison_app(settings), raise_server_exceptions=False)

                with patch.object(ComparisonSqliteStore, "_replace_snapshot", side_effect=RuntimeError("boom")):
                    failed_response = client.post(
                        "/api/comparison/sync",
                        json={
                            "participant_name": "Martin A.",
                            "claim_code": "invite-123",
                            "courses": [],
                        },
                    )

                retry_response = client.post(
                    "/api/comparison/sync",
                    json={
                        "participant_name": "Martin A.",
                        "claim_code": "invite-123",
                        "courses": [],
                    },
                )

        self.assertEqual(failed_response.status_code, 500)
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.json()["state"], "linked")

    def test_invalid_invite_file_fails_with_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                root = Path(temp_dir)
                settings = self._write_settings(root, invites_contents="not-json")

                with self.assertRaisesRegex(RuntimeError, "comparison invite"):
                    create_comparison_app(settings)
