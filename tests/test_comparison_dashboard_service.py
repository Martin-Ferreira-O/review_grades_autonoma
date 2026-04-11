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


if __name__ == "__main__":
    unittest.main()
