import json
import unittest
from datetime import datetime, timezone

from uac_grades.application.services import build_dashboard_context
from uac_grades.domain.models import AcademicHistory, AcademicLevel, AcademicTerm, Course, GradeSnapshot


def _course(code: str, title: str, grade: str | None) -> Course:
    return Course(
        course_id=None,
        nrc=None,
        code=code,
        section=None,
        title=title,
        grade=grade,
        final_grade=grade,
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


class DashboardAnalyticsTests(unittest.TestCase):
    def test_build_dashboard_context(self) -> None:
        history = AcademicHistory(
            generated_at="2026-04-03T12:00:00+00:00",
            snapshots=[
                GradeSnapshot(
                    term=AcademicTerm(code="202310", description="Primer Semestre - 2023"),
                    level=AcademicLevel(code="PR", description="Pregrado"),
                    courses=[_course("MAT101", "Calculo", "5,5"), _course("QUI100", "Quimica", "3,7")],
                ),
                GradeSnapshot(
                    term=AcademicTerm(code="202320", description="Segundo Semestre - 2023"),
                    level=AcademicLevel(code="PR", description="Pregrado"),
                    courses=[_course("FIS101", "Fisica", "6,1")],
                ),
                GradeSnapshot(
                    term=AcademicTerm(code="202410", description="Primer Semestre - 2024"),
                    level=AcademicLevel(code="PR", description="Pregrado"),
                    courses=[_course("INF200", "Arquitectura", None)],
                ),
            ],
        )

        context = build_dashboard_context(
            history,
            reference_time=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(context["cards"]["terms"], 3)
        self.assertEqual(context["cards"]["courses"], 4)
        self.assertEqual(context["cards"]["graded_courses"], 3)
        self.assertEqual(context["cards"]["passed_courses"], 2)
        self.assertEqual(context["cards"]["failed_courses"], 1)
        self.assertEqual(context["cards"]["overall_average"], "5.10")
        self.assertEqual(len(context["term_summaries"]), 3)
        self.assertEqual(context["generated_at_relative"], "hace 2 dias")
        self.assertEqual(context["latest_term_label"], "Primer Semestre - 2024 | Pregrado")
        self.assertEqual(json.loads(context["chart_data"]["term_averages_json"]), [4.6, 6.1, None])
        self.assertEqual(json.loads(context["chart_data"]["best_labels_json"])[0], "Fisica")
        self.assertEqual(json.loads(context["chart_data"]["worst_labels_json"])[0], "Quimica")
        self.assertEqual(context["term_summaries"][-1]["pending_count"], 1)
        self.assertEqual(context["courses"][0]["status"], "Sin nota")


if __name__ == "__main__":
    unittest.main()
