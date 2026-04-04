import json
import unittest
from datetime import datetime, timezone

from uac_grades.application.services import build_dashboard_context
from uac_grades.domain.models import AcademicHistory, AcademicLevel, AcademicTerm, Course, GradeComponent, GradeSnapshot


def _component(name: str, weight: str, grade: str | None, *, must_pass: bool = False) -> GradeComponent:
    return GradeComponent(
        component_id=None,
        name=name,
        code=None,
        description=None,
        weight=weight,
        score=None,
        total_score=None,
        score_text=None,
        grade=grade,
        percentage=None,
        must_pass=must_pass,
        stage="Final",
        is_main_component=True,
        has_subcomponents=False,
        subcomponents=[],
    )


def _component_with_subcomponents(
    name: str,
    weight: str,
    subcomponents: list[GradeComponent],
) -> GradeComponent:
    return GradeComponent(
        component_id=None,
        name=name,
        code=None,
        description=None,
        weight=weight,
        score=None,
        total_score=None,
        score_text=None,
        grade=None,
        percentage=None,
        must_pass=False,
        stage="Final",
        is_main_component=True,
        has_subcomponents=True,
        subcomponents=subcomponents,
    )


def _course(
    code: str,
    title: str,
    grade: str | None,
    *,
    components: list[GradeComponent] | None = None,
) -> Course:
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
        components_available=bool(components),
        components=components or [],
    )


class DashboardAnalyticsTests(unittest.TestCase):
    def test_build_dashboard_context(self) -> None:
        latest_courses = [
            _course(
                "INF301",
                "Software",
                None,
                components=[
                    _component_with_subcomponents(
                        "C1",
                        "30",
                        [
                            _component("S1", "50", "4,0"),
                            _component("S2", "50", "6,0"),
                        ],
                    ),
                    _component("C2", "30", None),
                    _component("C3", "40", None),
                    _component("Asistencia", "0", None, must_pass=True),
                ],
            ),
            _course(
                "INF302",
                "Bases",
                None,
                components=[
                    _component("C1", "60", "6,5"),
                    _component("C2", "40", None),
                ],
            ),
            _course(
                "INF303",
                "Analitica",
                None,
                components=[
                    _component("C1", "50", None),
                    _component("C2", "50", None),
                ],
            ),
        ]

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
                    courses=latest_courses,
                ),
            ],
        )

        context = build_dashboard_context(
            history,
            reference_time=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(context["cards"]["terms"], 3)
        self.assertEqual(context["cards"]["courses"], 6)
        self.assertEqual(context["cards"]["graded_courses"], 3)
        self.assertEqual(context["cards"]["passed_courses"], 2)
        self.assertEqual(context["cards"]["failed_courses"], 1)
        self.assertEqual(context["cards"]["overall_average"], "5.10")
        self.assertEqual(context["generated_at_relative"], "hace 2 dias")
        self.assertEqual(context["latest_term_label"], "Primer Semestre - 2024 | Pregrado")
        self.assertEqual(json.loads(context["chart_data"]["term_averages_json"]), [4.6, 6.1, None])
        self.assertEqual(json.loads(context["chart_data"]["best_labels_json"])[0], "Fisica")
        self.assertEqual(json.loads(context["chart_data"]["worst_labels_json"])[0], "Quimica")

        current_term = context["current_term"]
        self.assertIsNotNone(current_term)
        self.assertEqual(current_term["courses_count"], 3)
        self.assertEqual(current_term["courses_with_data_count"], 2)
        self.assertEqual(current_term["attention_count"], 0)
        self.assertEqual(current_term["watch_count"], 1)
        self.assertEqual(current_term["relaxed_count"], 1)
        self.assertEqual(current_term["no_data_count"], 1)
        self.assertEqual(current_term["graded_components_count"], 3)
        self.assertEqual(current_term["total_components_count"], 8)
        self.assertEqual(current_term["current_average_text"], "6.00")
        self.assertEqual(current_term["weighted_progress_text"], "30%")

        first_course = current_term["courses"][0]
        self.assertEqual(first_course["title"], "Software")
        self.assertEqual(first_course["attention_label"], "Vigilancia")
        self.assertEqual(first_course["current_average_text"], "5.00")
        self.assertEqual(first_course["required_to_pass"]["text"], "3.57")
        self.assertEqual(first_course["required_to_comfort"]["text"], "5.71")
        self.assertEqual(first_course["projected_final_text"], "5.00")
        self.assertEqual(first_course["graded_components_count"], 2)
        self.assertEqual(first_course["weighted_components_count"], 4)
        self.assertIn("requisito obligatorio pendiente", first_course["summary_message"].lower())

        second_course = current_term["courses"][1]
        self.assertEqual(second_course["title"], "Analitica")
        self.assertEqual(second_course["attention_label"], "Sin datos")
        self.assertEqual(second_course["required_to_pass"]["text"], "4.00")
        self.assertEqual(second_course["required_to_comfort"]["text"], "5.50")

        third_course = current_term["courses"][2]
        self.assertEqual(third_course["title"], "Bases")
        self.assertEqual(third_course["attention_label"], "Puedes relajarte")
        self.assertEqual(third_course["required_to_pass"]["text"], "Cumplido")
        self.assertEqual(third_course["required_to_comfort"]["text"], "4.00")


if __name__ == "__main__":
    unittest.main()
