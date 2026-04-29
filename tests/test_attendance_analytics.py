import unittest

from uac_grades.application.services import build_attendance_dashboard_context
from uac_grades.domain.models import (
    AcademicLevel,
    AcademicTerm,
    AttendanceAbsenceDetail,
    AttendanceSection,
    AttendanceSnapshot,
    Course,
    GradeComponent,
    GradeSnapshot,
)


def _attendance_component(name: str = "ATTRGRD - ASISTENCIA 60%") -> GradeComponent:
    return GradeComponent(
        component_id=None,
        name=name,
        code=None,
        description=None,
        weight="0",
        score=None,
        total_score=None,
        score_text=None,
        grade=None,
        percentage=None,
        must_pass=True,
        stage="Final",
        is_main_component=True,
        has_subcomponents=False,
        subcomponents=[],
    )


def _course(code: str, title: str, *, components: list[GradeComponent] | None = None) -> Course:
    return Course(
        course_id=None,
        nrc=None,
        code=code,
        section=None,
        title=title,
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
        components_available=bool(components),
        components=components or [],
    )


def _section(
    *,
    term_code: str = "202610",
    nrc: str = "20824",
    section: str = "P04",
    day: str = "R",
    time: str = "1400",
    missed: int = 0,
    attended: int = 8,
    total: int = 8,
    percentage: float = 100.0,
) -> AttendanceSection:
    return AttendanceSection(
        term_code=term_code,
        subject_code="CINF",
        course_number="00701",
        course_reference_number=nrc,
        section=section,
        session_indicator="01",
        section_title="Ingeniería de Software",
        subject_description="INGENIERÍA CIVIL INFORMÁTICA",
        schedule=["false", "false", "false", day, "false", "false", "false"],
        time=time,
        section_meeting_id=nrc,
        missed=missed,
        percentage=percentage,
        total_sessions=total,
        sessions_attended=attended,
        class_cancelled=0,
        absence_notified_count=0,
        absences=[
            AttendanceAbsenceDetail(
                meeting_date="23-Apr-2026",
                hours="01:20",
                status="Ausente",
            )
        ]
        if missed
        else [],
    )


class AttendanceAnalyticsTests(unittest.TestCase):
    def test_build_attendance_context_groups_sections_and_ignores_old_terms(self) -> None:
        current_snapshot = GradeSnapshot(
            term=AcademicTerm(code="202610", description="Primer Semestre - 2026"),
            level=AcademicLevel(code="PR", description="Pregrado"),
            courses=[
                _course("CINF 00701", "Ingeniería de Software", components=[_attendance_component()]),
            ],
        )
        attendance_snapshot = AttendanceSnapshot(
            term_code="202610",
            generated_at="2026-04-29T21:00:00+00:00",
            sections=[
                _section(nrc="20824", section="P04", day="R", time="1400", missed=2, attended=6, total=8, percentage=75.0),
                _section(nrc="20825", section="P05", day="W", time="1700", missed=1, attended=8, total=9, percentage=88.0),
                _section(term_code="202520", nrc="26068", missed=9, attended=0, total=9, percentage=0.0),
            ],
        )

        context = build_attendance_dashboard_context(current_snapshot, attendance_snapshot)

        self.assertIsNotNone(context)
        self.assertTrue(context["available"])
        self.assertEqual(context["courses_count"], 1)
        self.assertEqual(context["sections_count"], 2)
        course = context["courses"][0]
        self.assertEqual(course["title"], "Ingeniería de Software")
        self.assertEqual(course["minimum_percentage_text"], "60%")
        self.assertEqual(course["current_percentage_text"], "82.4%")
        self.assertEqual(course["total_classes"], 36)
        self.assertEqual(course["effective_total_classes"], 36)
        self.assertEqual(course["max_absences"], 14)
        self.assertEqual(course["current_absences"], 3)
        self.assertEqual(course["classes_can_miss"], 11)
        self.assertEqual(course["status"], "Con margen")
        self.assertEqual([section["course_reference_number"] for section in course["sections"]], ["20824", "20825"])
        self.assertEqual(course["sections"][0]["time_text"], "14:00")
        self.assertEqual(course["sections"][1]["days_text"], "Mie")
        self.assertEqual(len(course["recent_absences"]), 2)

    def test_course_without_requirement_is_marked_unknown(self) -> None:
        current_snapshot = GradeSnapshot(
            term=AcademicTerm(code="202610", description="Primer Semestre - 2026"),
            level=AcademicLevel(code="PR", description="Pregrado"),
            courses=[_course("CINF 00701", "Ingeniería de Software")],
        )
        attendance_snapshot = AttendanceSnapshot(
            term_code="202610",
            sections=[_section()],
        )

        context = build_attendance_dashboard_context(current_snapshot, attendance_snapshot)

        self.assertEqual(context["unknown_count"], 1)
        self.assertEqual(context["courses"][0]["status"], "Sin requisito detectado")
        self.assertEqual(context["courses"][0]["classes_can_miss_text"], "s/d")


if __name__ == "__main__":
    unittest.main()
