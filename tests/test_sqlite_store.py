import tempfile
import unittest
from pathlib import Path

from uac_grades.domain.models import AcademicHistory, AcademicLevel, AcademicTerm, Course, GradeSnapshot
from uac_grades.infrastructure.persistence import SqliteHistoryStore


def _sample_history() -> AcademicHistory:
    return AcademicHistory(
        generated_at="2026-04-03T13:00:00+00:00",
        snapshots=[
            GradeSnapshot(
                term=AcademicTerm(code="202410", description="Primer Semestre - 2024"),
                level=AcademicLevel(code="PR", description="Pregrado"),
                courses=[
                    Course(
                        course_id=None,
                        nrc=None,
                        code="INF200",
                        section=None,
                        title="Arquitectura",
                        grade="5,8",
                        final_grade="5,8",
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
                    )
                ],
            )
        ],
    )


class SqliteHistoryStoreTests(unittest.TestCase):
    def test_save_and_load_latest_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "ua_grades.sqlite3"
            store = SqliteHistoryStore(database_path)

            run_id = store.save(_sample_history())
            loaded = store.load_latest()

            self.assertGreater(run_id, 0)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.generated_at, "2026-04-03T13:00:00+00:00")
            self.assertEqual(loaded.courses_count, 1)
            self.assertEqual(store.runs_count(), 1)


if __name__ == "__main__":
    unittest.main()
