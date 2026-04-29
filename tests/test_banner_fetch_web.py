import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from uac_grades.domain.models import (
    AcademicHistory,
    AcademicLevel,
    AcademicTerm,
    Course,
    GradeComponent,
    GradeSnapshot,
)
from uac_grades.infrastructure.config import Settings
from uac_grades.interfaces.api.app import create_app
from uac_grades.interfaces.banner_fetch import (
    BannerFetchResult,
    detect_new_grades,
)


def _component(name: str, grade: str | None) -> GradeComponent:
    return GradeComponent(
        component_id=name.casefold().replace(" ", "-"),
        name=name,
        code=name,
        description=None,
        weight="50",
        score=None,
        total_score=None,
        score_text=None,
        grade=grade,
        percentage=None,
        must_pass=False,
        stage=None,
        is_main_component=True,
        has_subcomponents=False,
    )


def _history(component_grade: str | None) -> AcademicHistory:
    return AcademicHistory(
        generated_at="2026-04-29T18:00:00+00:00",
        snapshots=[
            GradeSnapshot(
                term=AcademicTerm(code="202610", description="Primer Semestre - 2026"),
                level=AcademicLevel(code="PR", description="Pregrado"),
                courses=[
                    Course(
                        course_id="course-1",
                        nrc="12345",
                        code="MAT 101",
                        section=None,
                        title="Matematicas",
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
                        components_available=True,
                        components=[_component("Prueba 1", component_grade)],
                    )
                ],
            )
        ],
    )


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


class _FakeHistoryStore:
    database_path = Path("/tmp/local.sqlite3")

    def __init__(self, history: AcademicHistory | None = None):
        self.history = history

    def load_latest(self):
        return self.history


class BannerFetchWebTests(unittest.TestCase):
    def test_detect_new_grades_reports_course_and_grade(self) -> None:
        previous = _history(None)
        current = _history("6.1")

        new_grades = detect_new_grades(previous, current)

        self.assertEqual(len(new_grades), 1)
        self.assertEqual(new_grades[0].course_title, "Matematicas")
        self.assertEqual(new_grades[0].evaluation, "Prueba 1")
        self.assertEqual(new_grades[0].grade, "6.1")

    def test_detect_new_grades_reports_updated_grade(self) -> None:
        previous = _history("5.2")
        current = _history("6.1")

        new_grades = detect_new_grades(previous, current)

        self.assertEqual(len(new_grades), 1)
        self.assertEqual(new_grades[0].previous_grade, "5.2")
        self.assertEqual(new_grades[0].grade, "6.1")

    def test_fetch_endpoint_returns_result_and_enforces_cooldown(self) -> None:
        async def fake_banner_fetcher():
            return BannerFetchResult(
                history=_history("6.1"),
                first_fetch=True,
                full_refresh=False,
                new_grades=[],
                json_path=Path("/tmp/history.json"),
                database_path=Path("/tmp/local.sqlite3"),
                run_id=7,
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(),
                    banner_fetcher=fake_banner_fetcher,
                )
            )

            response = client.post("/api/fetch")
            cooldown_response = client.post("/api/fetch")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Notas cargadas.")
        self.assertEqual(response.json()["cooldown_seconds"], 60)
        self.assertEqual(cooldown_response.status_code, 429)

    def test_fetch_endpoint_allows_retry_after_error(self) -> None:
        calls = {"count": 0}

        async def flaky_banner_fetcher():
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("Banner no respondio")
            return BannerFetchResult(
                history=_history("6.1"),
                first_fetch=False,
                full_refresh=False,
                new_grades=detect_new_grades(_history(None), _history("6.1")),
                json_path=Path("/tmp/history.json"),
                database_path=Path("/tmp/local.sqlite3"),
                run_id=8,
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            client = TestClient(
                create_app(
                    settings,
                    history_store=_FakeHistoryStore(_history(None)),
                    banner_fetcher=flaky_banner_fetcher,
                )
            )

            error_response = client.post("/api/fetch")
            retry_response = client.post("/api/fetch")

        self.assertEqual(error_response.status_code, 500)
        self.assertEqual(error_response.json(), {"detail": "Banner no respondio"})
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.json()["new_grades_count"], 1)


if __name__ == "__main__":
    unittest.main()
