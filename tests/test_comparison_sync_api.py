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

    def test_dashboard_data_endpoint_supports_query_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                root = Path(temp_dir)
                settings = self._write_settings(root, invites_contents=json.dumps({"Martin A.": "invite-123"}))
                client = TestClient(create_comparison_app(settings))

                claim_response = client.post(
                    "/api/comparison/sync",
                    json={
                        "participant_name": "Martin A.",
                        "claim_code": "invite-123",
                        "courses": [
                            {
                                "canonical_course_key": "PHY101",
                                "course_code": "PHY101",
                                "course_title": "Fisica I",
                                "term_code": "202410",
                                "term_label": "Segundo Semestre - 2024",
                                "section": "1",
                                "status": "closed",
                                "current_grade": 4.0,
                                "final_grade": 4.0,
                                "comparison_grade": 4.0,
                                "assessments": [
                                    {
                                        "assessment_name": "Laboratorio",
                                        "canonical_assessment_key": "lab-1",
                                        "weight": 30.0,
                                        "grade": 4.5,
                                        "grade_text": "4.5",
                                        "must_pass": False,
                                        "order_index": 1,
                                    }
                                ],
                            },
                            {
                                "canonical_course_key": "MAT101",
                                "course_code": "MAT101",
                                "course_title": "Calculo I",
                                "term_code": "202510",
                                "term_label": "Primer Semestre - 2025",
                                "section": "1",
                                "status": "closed",
                                "current_grade": 6.0,
                                "final_grade": 6.0,
                                "comparison_grade": 6.0,
                                "assessments": [
                                    {
                                        "assessment_name": "Solemne 2",
                                        "canonical_assessment_key": "solemne-2",
                                        "weight": 30.0,
                                        "grade": 5.8,
                                        "grade_text": "5.8",
                                        "must_pass": False,
                                        "order_index": 2,
                                    },
                                    {
                                        "assessment_name": "Solemne 1",
                                        "canonical_assessment_key": "solemne-1",
                                        "weight": 30.0,
                                        "grade": 6.2,
                                        "grade_text": "6.2",
                                        "must_pass": False,
                                        "order_index": 1,
                                    },
                                ],
                            },
                        ],
                    },
                )

                self.assertEqual(claim_response.status_code, 200)

                default_response = client.get("/api/comparison/dashboard")
                selected_response = client.get(
                    "/api/comparison/dashboard",
                    params={
                        "participant": "Martin A.",
                        "selected_course": "PHY101",
                        "selected_semester": "202410",
                        "selected_assessment": "Laboratorio",
                    },
                )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.json()["tabs"]["course"]["selected"], "MAT101")
        self.assertEqual(default_response.json()["tabs"]["semester"]["selected"], "202510")
        self.assertEqual(default_response.json()["tabs"]["course"]["selected_assessment"], "Solemne 1")
        self.assertEqual(selected_response.status_code, 200)
        self.assertEqual(selected_response.json()["tabs"]["course"]["selected"], "PHY101")
        self.assertEqual(selected_response.json()["tabs"]["semester"]["selected"], "202410")
        self.assertEqual(selected_response.json()["tabs"]["course"]["selected_assessment"], "Laboratorio")
