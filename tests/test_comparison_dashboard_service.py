import unittest

from uac_grades.application.services.comparison_dashboard import build_comparison_dashboard_context


class ComparisonDashboardServiceTests(unittest.TestCase):
    def test_builds_course_semester_and_historical_rankings(self) -> None:
        rows = [
            {
                "display_name": "Martin A.",
                "canonical_course_key": "MAT101",
                "course_title": "Calculo I",
                "term_code": "202510",
                "term_label": "Primer Semestre - 2025",
                "comparison_grade": 5.8,
                "assessment_name": "Solemne 1",
                "assessment_grade": 6.0,
            },
            {
                "display_name": "Camila R.",
                "canonical_course_key": "MAT101",
                "course_title": "Calculo I",
                "term_code": "202510",
                "term_label": "Primer Semestre - 2025",
                "comparison_grade": 5.2,
                "assessment_name": "Solemne 1",
                "assessment_grade": 5.0,
            },
        ]

        context = build_comparison_dashboard_context(rows, highlight_participant="Martin A.")

        self.assertEqual(context["tabs"]["course"]["ranking"][0]["display_name"], "Martin A.")
        self.assertEqual(context["tabs"]["course"]["assessment_ranking"][0]["display_name"], "Martin A.")
        self.assertEqual(context["tabs"]["course"]["ranking"][0]["gap_to_leader"], 0.0)
        self.assertEqual(context["tabs"]["semester"]["ranking"][0]["display_name"], "Martin A.")
        self.assertEqual(context["tabs"]["historical"]["ranking"][0]["display_name"], "Martin A.")
        self.assertEqual(context["summary"]["leaders"][0], "Martin A.")
        self.assertEqual(context["summary"]["selected_participant"]["display_name"], "Martin A.")

    def test_counts_each_course_attempt_once_outside_assessment_rankings(self) -> None:
        rows = [
            {
                "display_name": "Martin A.",
                "canonical_course_key": "MAT101",
                "course_title": "Calculo I",
                "term_code": "202510",
                "term_label": "Primer Semestre - 2025",
                "comparison_grade": 6.0,
                "assessment_name": "Solemne 1",
                "assessment_grade": 6.2,
            },
            {
                "display_name": "Martin A.",
                "canonical_course_key": "MAT101",
                "course_title": "Calculo I",
                "term_code": "202510",
                "term_label": "Primer Semestre - 2025",
                "comparison_grade": 6.0,
                "assessment_name": "Solemne 2",
                "assessment_grade": 5.8,
            },
            {
                "display_name": "Martin A.",
                "canonical_course_key": "MAT101",
                "course_title": "Calculo I",
                "term_code": "202410",
                "term_label": "Segundo Semestre - 2024",
                "comparison_grade": 4.0,
                "assessment_name": "Examen",
                "assessment_grade": 4.0,
            },
            {
                "display_name": "Camila R.",
                "canonical_course_key": "MAT101",
                "course_title": "Calculo I",
                "term_code": "202510",
                "term_label": "Primer Semestre - 2025",
                "comparison_grade": 5.0,
                "assessment_name": "Solemne 1",
                "assessment_grade": 5.0,
            },
            {
                "display_name": "Camila R.",
                "canonical_course_key": "MAT101",
                "course_title": "Calculo I",
                "term_code": "202410",
                "term_label": "Segundo Semestre - 2024",
                "comparison_grade": 5.0,
                "assessment_name": "Examen",
                "assessment_grade": 5.0,
            },
        ]

        context = build_comparison_dashboard_context(rows, highlight_participant="Martin A.")

        martin_course_row = next(
            row for row in context["tabs"]["course"]["ranking"] if row["display_name"] == "Martin A."
        )
        martin_historical_row = next(
            row for row in context["tabs"]["historical"]["ranking"] if row["display_name"] == "Martin A."
        )

        self.assertEqual(martin_course_row["average"], 5.0)
        self.assertEqual(martin_course_row["gap_to_leader"], 0.0)
        self.assertEqual(martin_historical_row["average"], 5.0)
        self.assertEqual(context["tabs"]["course"]["assessment_ranking"][0]["display_name"], "Martin A.")
        self.assertEqual(context["tabs"]["course"]["assessment_ranking"][0]["average"], 6.2)


if __name__ == "__main__":
    unittest.main()
