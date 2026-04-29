from __future__ import annotations

import math
import re
from datetime import datetime

from uac_grades.domain.models import AttendanceSection, AttendanceSnapshot, Course, GradeComponent, GradeSnapshot

from .analytics import _format_exact_datetime, _format_relative_datetime

SEMESTER_WEEKS = 18
_DAY_LABELS = ["Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"]


def _parse_number(value) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r"-?\d+(?:[\.,]\d+)?", str(value))
    if match is None:
        return None

    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _format_percentage(value: float | None) -> str:
    if value is None:
        return "s/d"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}%"
    return f"{value:.1f}%"


def _format_int(value: int | None) -> str:
    return "s/d" if value is None else str(value)


def _format_time(value: str | None) -> str:
    if value is None:
        return "s/d"
    text = str(value).strip()
    if len(text) == 4 and text.isdigit():
        return f"{text[:2]}:{text[2:]}"
    return text or "s/d"


def _schedule_days(schedule: list[str]) -> list[str]:
    days = []
    for index, value in enumerate(schedule[: len(_DAY_LABELS)]):
        if str(value).strip().lower() not in {"", "false", "none", "null"}:
            days.append(_DAY_LABELS[index])
    return days


def _course_key_from_code(code: str) -> str:
    return re.sub(r"\s+", " ", code.strip()).casefold()


def _course_key_from_section(section: AttendanceSection) -> str:
    return _course_key_from_code(section.course_code)


def _flatten_components(components: list[GradeComponent]) -> list[GradeComponent]:
    flattened: list[GradeComponent] = []
    for component in components:
        flattened.append(component)
        flattened.extend(_flatten_components(component.subcomponents))
    return flattened


def _attendance_requirement_value(course: Course) -> float | None:
    for component in _flatten_components(course.components):
        text = " ".join(
            part
            for part in (component.name, component.code, component.description)
            if part
        )
        if not component.must_pass or "asistencia" not in text.casefold():
            continue

        match = re.search(r"(\d+(?:[\.,]\d+)?)\s*%", text)
        if match is not None:
            return _parse_number(match.group(1))

    return None


def _section_sessions_held(section: AttendanceSection) -> int | None:
    if section.sessions_attended is None:
        return None
    return section.sessions_attended + section.missed


def _current_percentage(sections: list[AttendanceSection]) -> float | None:
    attended = sum(section.sessions_attended or 0 for section in sections)
    held = sum(_section_sessions_held(section) or 0 for section in sections)
    if held > 0:
        return attended / held * 100.0

    percentages = [section.percentage for section in sections if section.percentage is not None]
    if percentages:
        return sum(percentages) / len(percentages)
    return None


def _status_for_budget(minimum: float | None, classes_can_miss: int | None) -> tuple[str, str, int]:
    if minimum is None or classes_can_miss is None:
        return "Sin requisito detectado", "muted", 0
    if classes_can_miss < 0:
        return "Bajo el minimo", "warning", 4
    if classes_can_miss == 0:
        return "No faltes mas", "warning", 3
    if classes_can_miss <= 1:
        return "Ajustado", "info", 2
    return "Con margen", "success", 1


def _absence_sort_key(absence: dict) -> datetime:
    raw_date = str(absence.get("meeting_date") or "")
    try:
        return datetime.strptime(raw_date, "%d-%b-%Y")
    except ValueError:
        return datetime.min


def _section_row(section: AttendanceSection) -> dict:
    days = _schedule_days(section.schedule)
    return {
        "course_reference_number": section.course_reference_number or "s/d",
        "section": section.section or "s/d",
        "session_indicator": section.session_indicator or "s/d",
        "days": days,
        "days_text": ", ".join(days) if days else "s/d",
        "time": section.time,
        "time_text": _format_time(section.time),
        "missed": section.missed,
        "percentage_value": section.percentage,
        "percentage_text": _format_percentage(section.percentage),
        "registered_sessions": section.total_sessions,
        "registered_sessions_text": _format_int(section.total_sessions),
        "sessions_attended": section.sessions_attended,
        "sessions_attended_text": _format_int(section.sessions_attended),
        "class_cancelled": section.class_cancelled,
        "class_cancelled_text": _format_int(section.class_cancelled),
        "absence_notified_count": section.absence_notified_count,
        "absence_notified_count_text": _format_int(section.absence_notified_count),
    }


def _build_course_attendance(course: Course, sections: list[AttendanceSection]) -> dict:
    minimum = _attendance_requirement_value(course)
    sections_count = len(sections)
    total_classes = SEMESTER_WEEKS * sections_count
    cancelled = sum(section.class_cancelled or 0 for section in sections)
    effective_total_classes = max(total_classes - cancelled, 0)
    current_absences = sum(section.missed for section in sections)
    max_absences = (
        math.floor(effective_total_classes * (1.0 - minimum / 100.0))
        if minimum is not None
        else None
    )
    classes_can_miss = (
        max_absences - current_absences if max_absences is not None else None
    )
    status, status_variant, status_priority = _status_for_budget(minimum, classes_can_miss)
    registered_sessions = sum(section.total_sessions or 0 for section in sections)
    attended_sessions = sum(section.sessions_attended or 0 for section in sections)
    current_percentage = _current_percentage(sections)
    absences = []

    for section in sections:
        for absence in section.absences:
            absences.append(
                {
                    "meeting_date": absence.meeting_date,
                    "hours": absence.hours or "s/d",
                    "status": absence.status or "s/d",
                    "course_reference_number": section.course_reference_number or "s/d",
                    "section": section.section or "s/d",
                    "time_text": _format_time(section.time),
                }
            )

    recent_absences = sorted(absences, key=_absence_sort_key, reverse=True)[:3]

    return {
        "code": course.code,
        "title": course.title,
        "minimum_percentage_value": minimum,
        "minimum_percentage_text": _format_percentage(minimum),
        "current_percentage_value": current_percentage,
        "current_percentage_text": _format_percentage(current_percentage),
        "sections_count": sections_count,
        "total_classes": total_classes,
        "effective_total_classes": effective_total_classes,
        "registered_sessions": registered_sessions,
        "attended_sessions": attended_sessions,
        "current_absences": current_absences,
        "cancelled_classes": cancelled,
        "max_absences": max_absences,
        "max_absences_text": _format_int(max_absences),
        "classes_can_miss": classes_can_miss,
        "classes_can_miss_text": _format_int(classes_can_miss),
        "status": status,
        "status_variant": status_variant,
        "status_priority": status_priority,
        "sections": [_section_row(section) for section in sections],
        "recent_absences": recent_absences,
    }


def build_attendance_dashboard_context(
    current_snapshot: GradeSnapshot | None,
    attendance_snapshot: AttendanceSnapshot | None,
    *,
    reference_time: datetime | None = None,
) -> dict | None:
    if current_snapshot is None:
        return None

    if attendance_snapshot is None:
        return {
            "available": False,
            "term_code": current_snapshot.term.code,
            "term_label": current_snapshot.label,
            "courses": [],
        }

    if attendance_snapshot.term_code != current_snapshot.term.code:
        return {
            "available": False,
            "term_code": current_snapshot.term.code,
            "term_label": current_snapshot.label,
            "courses": [],
        }

    sections_by_course: dict[str, list[AttendanceSection]] = {}
    for section in attendance_snapshot.sections:
        if section.term_code != current_snapshot.term.code:
            continue
        sections_by_course.setdefault(_course_key_from_section(section), []).append(section)

    courses = []
    for course in current_snapshot.courses:
        sections = sections_by_course.get(_course_key_from_code(course.code), [])
        if not sections:
            continue
        courses.append(_build_course_attendance(course, sections))

    courses = sorted(
        courses,
        key=lambda course: (
            -course["status_priority"],
            course["classes_can_miss"] if course["classes_can_miss"] is not None else 999,
            course["title"],
        ),
    )

    return {
        "available": True,
        "generated_at": attendance_snapshot.generated_at,
        "generated_at_relative": _format_relative_datetime(
            attendance_snapshot.generated_at, reference_time=reference_time
        ),
        "generated_at_exact": _format_exact_datetime(attendance_snapshot.generated_at),
        "term_code": current_snapshot.term.code,
        "term_label": current_snapshot.label,
        "courses_count": len(courses),
        "sections_count": sum(course["sections_count"] for course in courses),
        "margin_count": sum(1 for course in courses if course["status"] == "Con margen"),
        "tight_count": sum(1 for course in courses if course["status"] == "Ajustado"),
        "no_more_count": sum(1 for course in courses if course["status"] == "No faltes mas"),
        "below_count": sum(1 for course in courses if course["status"] == "Bajo el minimo"),
        "unknown_count": sum(1 for course in courses if course["status"] == "Sin requisito detectado"),
        "courses": courses,
    }
