import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from uac_grades.domain.models import (
    AcademicHistory,
    AcademicLevel,
    AcademicTerm,
    AttendanceSnapshot,
    Course,
    GradeSnapshot,
)
from uac_grades.infrastructure.config import Settings
from uac_grades.interfaces.api.app import create_app
from uac_grades.interfaces.attendance_fetch import AttendanceFetchResult


class _FakeHistoryStore:
    def __init__(self, history: AcademicHistory | None):
        self._history = history
        self.database_path = Path("/tmp/local.sqlite3")

    def load_latest(self):
        return self._history


class _FakeAttendanceStore:
    def __init__(self, snapshot: AttendanceSnapshot | None = None):
        self._snapshot = snapshot
        self.database_path = Path("/tmp/local.sqlite3")

    def load_latest(self):
        return self._snapshot

    def save(self, snapshot: AttendanceSnapshot) -> int:
        self._snapshot = snapshot
        return 1


def _settings(root: Path) -> Settings:
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
    return Settings.load(dotenv_path)


def _history() -> AcademicHistory:
    course = Course(
        course_id=None,
        nrc="20824",
        code="CINF 00701",
        section="P04",
        title="Ingeniería de Software",
        grade=None,
        final_grade=None,
        midterm_grade=None,
        term_description=None,
        level_description=None,
        campus=None,
        study_path=None,
        attempted_hours=None,
        earned_hours=None,
        gpa_hours=None,
        quality_points=None,
        components_available=False,
        components=[],
    )
    return AcademicHistory(
        snapshots=[
            GradeSnapshot(
                term=AcademicTerm(code="202610", description="Primer Semestre - 2026"),
                level=AcademicLevel(code="PR", description="Pregrado"),
                courses=[course],
            )
        ]
    )


class AttendanceRoutesTests(unittest.TestCase):
    def test_dashboard_shows_attendance_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(_history()),
                    attendance_store=_FakeAttendanceStore(),
                )
            )

            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Actualizar asistencia", response.text)
        self.assertIn("Sin asistencia cargada", response.text)

    def test_attendance_api_returns_empty_context_without_attendance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(_history()),
                    attendance_store=_FakeAttendanceStore(),
                )
            )

            response = client.get("/api/attendance")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])

    def test_attendance_fetch_requires_grade_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(None),
                    attendance_store=_FakeAttendanceStore(),
                )
            )

            response = client.post("/api/attendance/fetch")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Primero debes cargar notas")

    def test_attendance_fetch_returns_payload_and_sets_cooldown(self) -> None:
        async def fake_fetcher() -> AttendanceFetchResult:
            return AttendanceFetchResult(
                snapshot=AttendanceSnapshot(term_code="202610", sections=[]),
                first_fetch=True,
                run_id=7,
                database_path=Path("/tmp/local.sqlite3"),
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(_history()),
                    attendance_store=_FakeAttendanceStore(),
                    attendance_fetcher=fake_fetcher,
                )
            )

            response = client.post("/api/attendance/fetch")
            cooldown_response = client.post("/api/attendance/fetch")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Asistencia cargada.")
        self.assertEqual(response.json()["run_id"], 7)
        self.assertEqual(cooldown_response.status_code, 429)
        self.assertGreater(cooldown_response.json()["detail"]["cooldown_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
