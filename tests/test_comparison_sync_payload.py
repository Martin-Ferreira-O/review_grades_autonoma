import unittest

from uac_grades.application.services.comparison_sync import build_comparison_sync_payload
from uac_grades.domain.models import AcademicHistory, AcademicLevel, AcademicTerm, Course, GradeComponent, GradeSnapshot


class ComparisonSyncPayloadTests(unittest.TestCase):
    def test_builds_payload_with_course_and_assessments(self) -> None:
        snapshot = GradeSnapshot(
            term=AcademicTerm(code="202510", description="Primer Semestre - 2025"),
            level=AcademicLevel(code="PR", description="Pregrado"),
            courses=[
                Course(
                    course_id="1",
                    nrc="1001",
                    code="MAT 101",
                    section="1",
                    title="Calculo I",
                    grade="5.4",
                    final_grade="5.4",
                    midterm_grade="5.1",
                    term_description="Primer Semestre - 2025",
                    level_description="Pregrado",
                    campus=None,
                    study_path=None,
                    attempted_hours=None,
                    earned_hours=None,
                    gpa_hours=None,
                    quality_points=None,
                    components_available=True,
                    components=[
                        GradeComponent(
                            component_id="c1",
                            name="Solemnes",
                            code=None,
                            description=None,
                            weight="30",
                            score=None,
                            total_score=None,
                            score_text=None,
                            grade=None,
                            percentage=None,
                            must_pass=False,
                            stage=None,
                            is_main_component=True,
                            has_subcomponents=True,
                            subcomponents=[
                                GradeComponent(
                                    component_id="c1-1",
                                    name="Solemne 1",
                                    code=None,
                                    description=None,
                                    weight="15",
                                    score=None,
                                    total_score=None,
                                    score_text="18/20",
                                    grade=None,
                                    percentage=None,
                                    must_pass=False,
                                    stage=None,
                                    is_main_component=False,
                                    has_subcomponents=False,
                                ),
                                GradeComponent(
                                    component_id="c1-2",
                                    name="Solemne 2",
                                    code=None,
                                    description=None,
                                    weight="15",
                                    score=None,
                                    total_score=None,
                                    score_text=None,
                                    grade=None,
                                    percentage="40%",
                                    must_pass=False,
                                    stage=None,
                                    is_main_component=False,
                                    has_subcomponents=False,
                                ),
                            ],
                        )
                    ],
                )
            ],
        )
        history = AcademicHistory(snapshots=[snapshot])

        payload = build_comparison_sync_payload(history, participant_name="Martin A.", claim_code="invite-123")

        self.assertEqual(payload.participant_name, "Martin A.")
        self.assertEqual(payload.claim_code, "invite-123")
        self.assertEqual(len(payload.courses), 1)
        self.assertEqual(payload.courses[0].canonical_course_key, "MAT101")
        self.assertEqual(payload.courses[0].comparison_grade, 5.4)
        self.assertEqual(len(payload.courses[0].assessments), 2)
        self.assertEqual(payload.courses[0].assessments[0].canonical_assessment_key, "solemne-1")
        self.assertEqual(payload.courses[0].assessments[0].grade_text, "18/20")
        self.assertEqual(payload.courses[0].assessments[1].canonical_assessment_key, "solemne-2")
        self.assertEqual(payload.courses[0].assessments[1].grade_text, "40%")

    def test_scales_nested_assessment_weights_to_effective_course_weight(self) -> None:
        snapshot = GradeSnapshot(
            term=AcademicTerm(code="202510", description="Primer Semestre - 2025"),
            level=AcademicLevel(code="PR", description="Pregrado"),
            courses=[
                Course(
                    course_id="1",
                    nrc="1001",
                    code="MAT 101",
                    section="1",
                    title="Calculo I",
                    grade="5.4",
                    final_grade="5.4",
                    midterm_grade="5.1",
                    term_description="Primer Semestre - 2025",
                    level_description="Pregrado",
                    campus=None,
                    study_path=None,
                    attempted_hours=None,
                    earned_hours=None,
                    gpa_hours=None,
                    quality_points=None,
                    components_available=True,
                    components=[
                        GradeComponent(
                            component_id="c1",
                            name="Solemnes",
                            code=None,
                            description=None,
                            weight="30%",
                            score=None,
                            total_score=None,
                            score_text=None,
                            grade=None,
                            percentage=None,
                            must_pass=False,
                            stage=None,
                            is_main_component=True,
                            has_subcomponents=True,
                            subcomponents=[
                                GradeComponent(
                                    component_id="c1-1",
                                    name="Solemne 1",
                                    code=None,
                                    description=None,
                                    weight="50%",
                                    score=None,
                                    total_score=None,
                                    score_text=None,
                                    grade="5.0",
                                    percentage=None,
                                    must_pass=False,
                                    stage=None,
                                    is_main_component=False,
                                    has_subcomponents=False,
                                ),
                                GradeComponent(
                                    component_id="c1-2",
                                    name="Solemne 2",
                                    code=None,
                                    description=None,
                                    weight="50%",
                                    score=None,
                                    total_score=None,
                                    score_text=None,
                                    grade="6.0",
                                    percentage=None,
                                    must_pass=False,
                                    stage=None,
                                    is_main_component=False,
                                    has_subcomponents=False,
                                ),
                            ],
                        )
                    ],
                )
            ],
        )

        payload = build_comparison_sync_payload(AcademicHistory(snapshots=[snapshot]), participant_name="Martin A.")

        self.assertEqual(payload.courses[0].assessments[0].weight, 15.0)
        self.assertEqual(payload.courses[0].assessments[1].weight, 15.0)
