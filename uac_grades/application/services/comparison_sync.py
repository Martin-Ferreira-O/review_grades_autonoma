from __future__ import annotations

import re

from uac_grades.domain import ComparisonAssessmentPayload, ComparisonCoursePayload, ComparisonSyncPayload
from uac_grades.domain.models import AcademicHistory, Course, GradeComponent


def _parse_grade(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:[\.,]\d+)?", str(value))
    if match is None:
        return None
    return float(match.group(0).replace(",", "."))


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return normalized.strip("-")


def _course_status(course: Course) -> str:
    return "closed" if _parse_grade(course.final_grade) is not None else "in_progress"


def _comparison_grade(course: Course) -> float | None:
    return _parse_grade(course.final_grade) or _parse_grade(course.grade) or _parse_grade(course.midterm_grade)


def _assessment_payload(component: GradeComponent, order_index: int) -> ComparisonAssessmentPayload:
    return ComparisonAssessmentPayload(
        assessment_name=component.name,
        canonical_assessment_key=_slug(component.name),
        weight=_parse_grade(component.weight) or 0.0,
        grade=_parse_grade(component.grade),
        grade_text=str(component.grade or "Pendiente"),
        must_pass=component.must_pass,
        order_index=order_index,
    )


def build_comparison_sync_payload(
    history: AcademicHistory,
    *,
    participant_name: str,
    claim_code: str | None = None,
    sync_token: str | None = None,
) -> ComparisonSyncPayload:
    courses: list[ComparisonCoursePayload] = []
    for snapshot in history.snapshots:
        for course in snapshot.courses:
            assessments = [_assessment_payload(component, index) for index, component in enumerate(course.components, start=1)]
            courses.append(
                ComparisonCoursePayload(
                    canonical_course_key=course.code.strip() or _slug(course.title),
                    course_code=course.code.strip(),
                    course_title=course.title.strip(),
                    term_code=snapshot.term.code,
                    term_label=snapshot.term.description,
                    section=course.section,
                    status=_course_status(course),
                    current_grade=_parse_grade(course.grade) or _parse_grade(course.midterm_grade),
                    final_grade=_parse_grade(course.final_grade),
                    comparison_grade=_comparison_grade(course),
                    assessments=assessments,
                )
            )

    return ComparisonSyncPayload(
        participant_name=participant_name,
        claim_code=claim_code,
        sync_token=sync_token,
        courses=courses,
    )
