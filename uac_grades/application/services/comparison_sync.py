from __future__ import annotations

import re

from uac_grades.domain import (
    ComparisonAssessmentPayload,
    ComparisonCoursePayload,
    ComparisonSyncPayload,
)
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


def _canonical_course_key(course: Course) -> str:
    code = re.sub(r"[^A-Za-z0-9]+", "", course.code.strip())
    return code.upper() or _slug(course.title)


def _course_status(course: Course) -> str:
    return "closed" if _parse_grade(course.final_grade) is not None else "in_progress"


def _first_grade(*values: str | None) -> float | None:
    for value in values:
        parsed = _parse_grade(value)
        if parsed is not None:
            return parsed
    return None


def _comparison_grade(course: Course) -> float | None:
    return _first_grade(course.final_grade, course.grade, course.midterm_grade)


def _grade_text(component: GradeComponent) -> str:
    return str(
        component.grade or component.score_text or component.percentage or "Pendiente"
    )


def _effective_weight(component: GradeComponent, parent_scale: float) -> float:
    weight = _parse_grade(component.weight) or 0.0
    return parent_scale * weight / 100.0


def _leaf_components(
    components: list[GradeComponent], parent_scale: float = 100.0
) -> list[tuple[GradeComponent, float]]:
    leaves: list[tuple[GradeComponent, float]] = []
    for component in components:
        effective_weight = _effective_weight(component, parent_scale)
        if component.subcomponents:
            leaves.extend(_leaf_components(component.subcomponents, effective_weight))
            continue
        leaves.append((component, effective_weight))
    return leaves


def _assessment_payload(
    component: GradeComponent, effective_weight: float, order_index: int
) -> ComparisonAssessmentPayload:
    return ComparisonAssessmentPayload(
        assessment_name=component.name,
        canonical_assessment_key=_slug(component.name),
        weight=effective_weight,
        grade=_parse_grade(component.grade),
        grade_text=_grade_text(component),
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
            assessments = [
                _assessment_payload(component, effective_weight, index)
                for index, (component, effective_weight) in enumerate(
                    _leaf_components(course.components), start=1
                )
            ]
            courses.append(
                ComparisonCoursePayload(
                    canonical_course_key=_canonical_course_key(course),
                    course_code=course.code.strip(),
                    course_title=course.title.strip(),
                    term_code=snapshot.term.code,
                    term_label=snapshot.term.description,
                    section=course.section,
                    status=_course_status(course),
                    current_grade=_first_grade(course.grade, course.midterm_grade),
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
