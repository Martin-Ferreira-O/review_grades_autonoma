from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from uac_grades.domain.models import AcademicHistory, Course, GradeSnapshot

PASSING_GRADE = 4.0


def _course_grade_value(course: Course) -> float | None:
    for candidate in (course.final_grade, course.grade, course.midterm_grade):
        if candidate in (None, ""):
            continue

        match = re.search(r"-?\d+(?:[\.,]\d+)?", str(candidate))
        if match is None:
            continue

        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            continue

    return None


def _format_grade(grade: float | None) -> str:
    if grade is None:
        return "s/d"
    return f"{grade:.2f}"


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed


def _format_relative_datetime(value: str, *, reference_time: datetime | None = None) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return value

    reference = reference_time or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    seconds = max(0, int((reference - parsed).total_seconds()))
    if seconds < 60:
        return "hace unos segundos"

    minutes = seconds // 60
    if minutes < 60:
        return f"hace {minutes} minuto" if minutes == 1 else f"hace {minutes} minutos"

    hours = minutes // 60
    if hours < 24:
        return f"hace {hours} hora" if hours == 1 else f"hace {hours} horas"

    days = hours // 24
    if days < 7:
        return f"hace {days} dia" if days == 1 else f"hace {days} dias"

    weeks = days // 7
    if weeks < 5:
        return f"hace {weeks} semana" if weeks == 1 else f"hace {weeks} semanas"

    return parsed.astimezone(reference.tzinfo).strftime("%d/%m/%Y %H:%M")


def _format_exact_datetime(value: str) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return value
    return parsed.strftime("%d/%m/%Y %H:%M %Z").strip()


def _course_status(grade: float | None) -> tuple[str, str]:
    if grade is None:
        return "Sin nota", "muted"
    if grade >= PASSING_GRADE:
        return "Aprobado", "success"
    return "Bajo 4.0", "warning"


def _term_summary(snapshot: GradeSnapshot) -> dict:
    rows = []
    grade_values = []
    for course in snapshot.courses:
        grade_value = _course_grade_value(course)
        status, status_variant = _course_status(grade_value)
        if grade_value is not None:
            grade_values.append(grade_value)

        rows.append(
            {
                "code": course.code,
                "title": course.title,
                "term_label": snapshot.label,
                "term_description": snapshot.term.description,
                "level_description": snapshot.level.description,
                "term_code": snapshot.term.code,
                "level_code": snapshot.level.code,
                "grade_value": grade_value,
                "grade_text": _format_grade(grade_value),
                "status": status,
                "status_variant": status_variant,
            }
        )

    average = sum(grade_values) / len(grade_values) if grade_values else None
    return {
        "label": snapshot.label,
        "term_description": snapshot.term.description,
        "level_description": snapshot.level.description,
        "term_code": snapshot.term.code,
        "level_code": snapshot.level.code,
        "courses_count": len(snapshot.courses),
        "graded_courses_count": len(grade_values),
        "average_value": average,
        "average_text": _format_grade(average),
        "passed_count": sum(1 for grade in grade_values if grade >= PASSING_GRADE),
        "failed_count": sum(1 for grade in grade_values if grade < PASSING_GRADE),
        "pending_count": sum(1 for course in rows if course["grade_value"] is None),
        "courses": rows,
    }


def build_dashboard_context(history: AcademicHistory, *, reference_time: datetime | None = None) -> dict:
    term_summaries = [_term_summary(snapshot) for snapshot in history.snapshots]
    course_rows = [course for summary in term_summaries for course in summary["courses"]]
    graded_courses = [course for course in course_rows if course["grade_value"] is not None]

    overall_average_value = None
    if graded_courses:
        overall_average_value = sum(course["grade_value"] for course in graded_courses) / len(graded_courses)

    best_courses = sorted(graded_courses, key=lambda course: course["grade_value"], reverse=True)[:5]
    worst_courses = sorted(graded_courses, key=lambda course: course["grade_value"])[:5]

    latest_term_label = term_summaries[-1]["label"] if term_summaries else "Sin datos"
    single_level = len({summary["level_description"] for summary in term_summaries}) <= 1
    term_labels = [summary["term_description"] if single_level else summary["label"] for summary in term_summaries]
    term_averages = [
        round(summary["average_value"], 2) if summary["average_value"] is not None else None
        for summary in term_summaries
    ]
    best_labels = [course["title"] for course in best_courses]
    best_values = [round(course["grade_value"], 2) for course in best_courses]
    worst_labels = [course["title"] for course in worst_courses]
    worst_values = [round(course["grade_value"], 2) for course in worst_courses]

    return {
        "generated_at": history.generated_at,
        "generated_at_relative": _format_relative_datetime(history.generated_at, reference_time=reference_time),
        "generated_at_exact": _format_exact_datetime(history.generated_at),
        "latest_term_label": latest_term_label,
        "history_json": history.to_dict(),
        "term_summaries": term_summaries,
        "courses": sorted(
            course_rows,
            key=lambda course: (
                course["term_code"],
                course["level_code"],
                course["grade_value"] if course["grade_value"] is not None else -1,
                course["title"],
            ),
            reverse=True,
        ),
        "cards": {
            "terms": len(term_summaries),
            "courses": history.courses_count,
            "graded_courses": len(graded_courses),
            "overall_average": _format_grade(overall_average_value),
            "passed_courses": sum(1 for course in graded_courses if course["grade_value"] >= PASSING_GRADE),
            "failed_courses": sum(1 for course in graded_courses if course["grade_value"] < PASSING_GRADE),
        },
        "chart_data": {
            "term_labels_json": json.dumps(term_labels, ensure_ascii=False),
            "term_averages_json": json.dumps(term_averages),
            "best_labels_json": json.dumps(best_labels, ensure_ascii=False),
            "best_values_json": json.dumps(best_values),
            "worst_labels_json": json.dumps(worst_labels, ensure_ascii=False),
            "worst_values_json": json.dumps(worst_values),
        },
    }
