import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from uac_grades.domain import ComparisonIdentity
from uac_grades.domain.models import AcademicHistory
from uac_grades.infrastructure.config import Settings
from uac_grades.interfaces.api.app import create_app


class _FakeHistoryStore:
    def __init__(self, history: AcademicHistory | None):
        self._history = history
        self.database_path = Path("/tmp/local.sqlite3")

    def load_latest(self):
        return self._history


class _FakeComparisonClient:
    async def sync(self, payload: dict) -> dict:
        return {
            "participant_name": payload["participant_name"],
            "state": "linked",
            "issued_sync_token": "issued-token",
            "synced_courses": len(payload["courses"]),
            "synced_assessments": 0,
            "synced_at": "2026-04-09T18:10:00+00:00",
        }


class _FakeRefreshComparisonClient:
    async def sync(self, payload: dict) -> dict:
        return {
            "participant_name": payload["participant_name"],
            "state": "updated",
            "issued_sync_token": None,
            "synced_courses": len(payload["courses"]),
            "synced_assessments": 0,
            "synced_at": "2026-04-10T09:30:00+00:00",
        }


class _FakeIdentityStore:
    def __init__(self):
        self.identity = None

    def load(self):
        return self.identity

    def save(self, *, display_name: str, sync_token: str, last_synced_at: str | None = None) -> None:
        self.identity = ComparisonIdentity(
            display_name=display_name,
            sync_token=sync_token,
            last_synced_at=last_synced_at,
        )


class LocalComparisonRoutesTests(unittest.TestCase):
    def test_dashboard_shows_comparison_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dotenv_path = root / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "UA_USUARIO=test@cloud.uautonoma.cl",
                        "UA_CONTRASENA=secret",
                        "UA_TOTP_SECRET=totp-secret",
                        "UA_COMPARISON_BASE_URL=http://127.0.0.1:9100",
                    ]
                ),
                encoding="utf-8",
            )
            settings = Settings.load(dotenv_path)
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(AcademicHistory(snapshots=[])),
                    comparison_client=_FakeComparisonClient(),
                    identity_store=_FakeIdentityStore(),
                )
            )

            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ir a dashboard de comparacion", response.text)
        self.assertIn("Subir mis datos / Sync", response.text)

    def test_local_sync_endpoint_persists_issued_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dotenv_path = root / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "UA_USUARIO=test@cloud.uautonoma.cl",
                        "UA_CONTRASENA=secret",
                        "UA_TOTP_SECRET=totp-secret",
                        "UA_COMPARISON_BASE_URL=http://127.0.0.1:9100",
                    ]
                ),
                encoding="utf-8",
            )
            settings = Settings.load(dotenv_path)
            identity_store = _FakeIdentityStore()
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(AcademicHistory(snapshots=[])),
                    comparison_client=_FakeComparisonClient(),
                    identity_store=identity_store,
                )
            )

            response = client.post(
                "/api/comparison/sync",
                json={"participant_name": "Martin A.", "claim_code": "invite-123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(identity_store.load().sync_token, "issued-token")

    def test_local_sync_endpoint_refreshes_last_synced_at_for_linked_user(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dotenv_path = root / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "UA_USUARIO=test@cloud.uautonoma.cl",
                        "UA_CONTRASENA=secret",
                        "UA_TOTP_SECRET=totp-secret",
                        "UA_COMPARISON_BASE_URL=http://127.0.0.1:9100",
                    ]
                ),
                encoding="utf-8",
            )
            settings = Settings.load(dotenv_path)
            identity_store = _FakeIdentityStore()
            identity_store.save(
                display_name="Martin A.",
                sync_token="existing-token",
                last_synced_at="2026-04-08T12:00:00+00:00",
            )
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(AcademicHistory(snapshots=[])),
                    comparison_client=_FakeRefreshComparisonClient(),
                    identity_store=identity_store,
                )
            )

            response = client.post("/api/comparison/sync", json={"participant_name": "Ignored value"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(identity_store.load().sync_token, "existing-token")
        self.assertEqual(identity_store.load().last_synced_at, "2026-04-10T09:30:00+00:00")
