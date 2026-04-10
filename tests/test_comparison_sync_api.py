import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from uac_grades.infrastructure.config import Settings
from uac_grades.interfaces.api import create_comparison_app


class ComparisonSyncApiTests(unittest.TestCase):
    def test_first_sync_claims_name_and_returns_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                root = Path(temp_dir)
                invites_path = root / "comparison_claim_invites.json"
                invites_path.write_text(json.dumps({"Martin A.": "invite-123"}), encoding="utf-8")
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
                settings = Settings.load(dotenv_path)
                client = TestClient(create_comparison_app(settings))

                response = client.post(
                    "/api/comparison/sync",
                    json={
                        "participant_name": "Martin A.",
                        "claim_code": "invite-123",
                        "courses": [],
                    },
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "linked")
        self.assertTrue(body["issued_sync_token"])
        self.assertTrue(body["synced_at"])
