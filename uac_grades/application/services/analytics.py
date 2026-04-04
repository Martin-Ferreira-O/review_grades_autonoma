from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from uac_grades.domain.models import AcademicHistory, Course, GradeComponent, GradeSnapshot

PASSING_GRADE = 4.0
COMFORTABLE_GRADE = 5.5
MIN_GRADE = 1.0
MAX_GRADE = 7.0
MANDATORY_PERCENTAGE_THRESHOLD = 60.0


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


def _course_grade_value(course: Course) -> float | None:
    for candidate in (course.final_grade, course.grade, course.midterm_grade):
        numeric = _parse_number(candidate)
        if numeric is not None:
            return numeric
    return None


def _component_grade_value(component: GradeComponent) -> float | None:
    return _parse_number(component.grade)


def _component_weight_value(component: GradeComponent) -> float:
    return _parse_number(component.weight) or 0.0


def _format_grade(grade: float | None) -> str:
    if grade is None:
        return "s/d"
    return f"{grade:.2f}"


def _format_weight(weight: float) -> str:
    if abs(weight - round(weight)) < 1e-9:
        return f"{int(round(weight))}%"
    return f"{weight:.1f}%"


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


def _requirement_for_target(target: float, *, points_earned: float, remaining_weight: float, total_weight: float) -> dict:
    target_points = target * total_weight

    if remaining_weight <= 0:
        if points_earned >= target_points - 1e-9:
            return {
                "target": target,
                "state": "achieved",
                "value": None,
                "text": "Cumplido",
            }
        return {
            "target": target,
            "state": "impossible",
            "value": None,
            "text": "No alcanza",
        }

    needed = (target_points - points_earned) / remaining_weight
    if needed <= MIN_GRADE:
        return {
            "target": target,
            "state": "achieved",
            "value": needed,
            "text": "Cumplido",
        }
    if needed > MAX_GRADE:
        return {
            "target": target,
            "state": "impossible",
            "value": needed,
            "text": "No alcanza",
        }
    return {
        "target": target,
        "state": "needed",
        "value": needed,
        "text": f"{needed:.2f}",
    }


def _mandatory_component_state(component: GradeComponent) -> tuple[str, str]:
    percentage = _parse_number(component.percentage)
    grade = _component_grade_value(component)
    raw_grade = str(component.grade).strip() if component.grade not in (None, "") else ""

    if percentage is not None:
        if percentage >= MANDATORY_PERCENTAGE_THRESHOLD:
            return "ok", f"{component.name}: requisito cumplido ({percentage:.0f}%)."
        return "risk", f"{component.name}: requisito obligatorio bajo {MANDATORY_PERCENTAGE_THRESHOLD:.0f}% ({percentage:.0f}%)."

    if grade is not None:
        if grade >= PASSING_GRADE:
            return "ok", f"{component.name}: requisito cumplido ({grade:.2f})."
        return "risk", f"{component.name}: requisito obligatorio en riesgo ({grade:.2f})."

    if raw_grade:
        return "ok", f"{component.name}: requisito registrado ({raw_grade})."

    return "pending", f"{component.name}: requisito obligatorio pendiente."


def _component_display_grade(component: GradeComponent) -> tuple[str, float | None]:
    numeric_grade = _component_grade_value(component)
    if numeric_grade is not None:
        return _format_grade(numeric_grade), numeric_grade

    if component.grade not in (None, ""):
        return str(component.grade), None
    if component.score_text not in (None, ""):
        return str(component.score_text), None
    if component.percentage not in (None, ""):
        return f"{component.percentage}%", None
    return "Pendiente", None


def _component_to_row(component: GradeComponent) -> dict:
    weight = _component_weight_value(component)
    grade_text, numeric_grade = _component_display_grade(component)
    raw_recorded = any(value not in (None, "") for value in (component.grade, component.score, component.score_text, component.percentage))
    mandatory_state = None
    mandatory_message = None
    if component.must_pass:
        mandatory_state, mandatory_message = _mandatory_component_state(component)

    if numeric_grade is None and mandatory_state == "risk":
        status_text = "Requisito en riesgo"
        status_variant = "warning"
    elif numeric_grade is None and mandatory_state == "pending":
        status_text = "Pendiente"
        status_variant = "muted"
    elif numeric_grade is None and raw_recorded:
        status_text = "Registrado"
        status_variant = "info"
    elif numeric_grade is None:
        status_text = "Pendiente"
        status_variant = "muted"
    elif numeric_grade >= PASSING_GRADE:
        status_text = "Con nota"
        status_variant = "success"
    else:
        status_text = "Con nota"
        status_variant = "warning"

    return {
        "name": component.name,
        "weight_value": weight,
        "weight_text": _format_weight(weight),
        "grade_value": numeric_grade,
        "grade_text": grade_text,
        "status_text": status_text,
        "status_variant": status_variant,
        "must_pass": component.must_pass,
        "must_pass_text": "Si" if component.must_pass else "No",
        "mandatory_state": mandatory_state,
        "mandatory_message": mandatory_message,
        "subcomponents": [_component_to_row(subcomponent) for subcomponent in component.subcomponents],
    }


def _flatten_weighted_components(component: GradeComponent, *, parent_scale: float = 1.0) -> list[dict]:
    component_weight = _component_weight_value(component)
    effective_weight = component_weight * parent_scale

    if component.subcomponents:
        subcomponent_rows: list[dict] = []
        for subcomponent in component.subcomponents:
            subcomponent_rows.extend(
                _flatten_weighted_components(subcomponent, parent_scale=effective_weight / 100.0)
            )
        return subcomponent_rows

    return [{"component": component, "effective_weight": effective_weight}]


def _weighted_component_entries(course: Course) -> list[dict]:
    entries: list[dict] = []
    for component in course.components:
        entries.extend(_flatten_weighted_components(component))
    return [entry for entry in entries if entry["effective_weight"] > 0]


def _build_term_summary(snapshot: GradeSnapshot) -> dict:
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


def _build_current_course_focus(course: Course) -> dict:
    weighted_entries = _weighted_component_entries(course)
    graded_weighted_entries = [
        entry for entry in weighted_entries if _component_grade_value(entry["component"]) is not None
    ]

    total_weight = sum(entry["effective_weight"] for entry in weighted_entries)
    evaluated_weight = sum(entry["effective_weight"] for entry in graded_weighted_entries)
    remaining_weight = max(total_weight - evaluated_weight, 0.0)
    points_earned = sum(
        (_component_grade_value(entry["component"]) or 0.0) * entry["effective_weight"]
        for entry in graded_weighted_entries
    )

    current_average = points_earned / evaluated_weight if evaluated_weight > 0 else None
    projected_final = None
    if total_weight > 0 and current_average is not None:
        projected_final = (points_earned + current_average * remaining_weight) / total_weight

    required_to_pass = _requirement_for_target(
        PASSING_GRADE,
        points_earned=points_earned,
        remaining_weight=remaining_weight,
        total_weight=total_weight or 100.0,
    )
    required_to_comfort = _requirement_for_target(
        COMFORTABLE_GRADE,
        points_earned=points_earned,
        remaining_weight=remaining_weight,
        total_weight=total_weight or 100.0,
    )

    mandatory_components = [component for component in course.components if component.must_pass]
    mandatory_states = [_mandatory_component_state(component) for component in mandatory_components]
    mandatory_risk = any(state == "risk" for state, _message in mandatory_states)
    mandatory_pending = any(state == "pending" for state, _message in mandatory_states)
    mandatory_messages = [message for _state, message in mandatory_states]

    if evaluated_weight <= 0:
        attention_label = "Sin datos"
        attention_variant = "muted"
        attention_priority = 2
    elif mandatory_risk or required_to_pass["state"] == "impossible":
        attention_label = "Mas atencion"
        attention_variant = "warning"
        attention_priority = 4
    elif required_to_pass["value"] is not None and required_to_pass["value"] > COMFORTABLE_GRADE:
        attention_label = "Mas atencion"
        attention_variant = "warning"
        attention_priority = 4
    elif projected_final is not None and projected_final < PASSING_GRADE:
        attention_label = "Mas atencion"
        attention_variant = "warning"
        attention_priority = 4
    elif mandatory_pending or required_to_comfort["state"] == "impossible":
        attention_label = "Vigilancia"
        attention_variant = "info"
        attention_priority = 3
    elif required_to_comfort["value"] is not None and required_to_comfort["value"] > COMFORTABLE_GRADE:
        attention_label = "Vigilancia"
        attention_variant = "info"
        attention_priority = 3
    elif projected_final is not None and projected_final < COMFORTABLE_GRADE:
        attention_label = "Vigilancia"
        attention_variant = "info"
        attention_priority = 3
    else:
        attention_label = "Puedes relajarte"
        attention_variant = "success"
        attention_priority = 1

    messages = []
    if evaluated_weight <= 0:
        messages.append("Aun no hay evaluaciones calificadas en este ramo.")
    else:
        if required_to_pass["state"] == "needed":
            messages.append(
                f"Necesitas promediar {required_to_pass['text']} en el {remaining_weight:.0f}% pendiente para llegar a 4.0."
            )
        elif required_to_pass["state"] == "achieved":
            messages.append("El 4.0 ya esta matematicamente encaminado.")
        else:
            messages.append("Aunque saques 7.0 en lo pendiente, no alcanzas 4.0.")

        if required_to_comfort["state"] == "needed":
            messages.append(
                f"Para cerrar tranquilo con 5.5 necesitas promediar {required_to_comfort['text']} en lo que falta."
            )
        elif required_to_comfort["state"] == "achieved":
            messages.append("El objetivo comodo de 5.5 ya esta encaminado.")
        else:
            messages.append("El 5.5 ya no alcanza con el peso pendiente.")

    if mandatory_messages:
        messages.append(mandatory_messages[0])

    pressure_score = 0.0
    if required_to_pass["state"] == "impossible":
        pressure_score = 999.0
    elif required_to_pass["value"] is not None:
        pressure_score = required_to_pass["value"]

    return {
        "code": course.code,
        "title": course.title,
        "current_average_value": current_average,
        "current_average_text": _format_grade(current_average),
        "projected_final_value": projected_final,
        "projected_final_text": _format_grade(projected_final),
        "evaluated_weight_value": evaluated_weight,
        "evaluated_weight_text": _format_weight(evaluated_weight),
        "remaining_weight_value": remaining_weight,
        "remaining_weight_text": _format_weight(remaining_weight),
        "total_weight_value": total_weight,
        "total_weight_text": _format_weight(total_weight),
        "weighted_components_count": len(weighted_entries),
        "graded_components_count": len(graded_weighted_entries),
        "pending_components_count": len(weighted_entries) - len(graded_weighted_entries),
        "required_to_pass": required_to_pass,
        "required_to_comfort": required_to_comfort,
        "attention_label": attention_label,
        "attention_variant": attention_variant,
        "attention_priority": attention_priority,
        "summary_message": " ".join(messages),
        "mandatory_risk": mandatory_risk,
        "mandatory_pending": mandatory_pending,
        "mandatory_messages": mandatory_messages,
        "pressure_score": pressure_score,
        "components": [_component_to_row(component) for component in course.components],
        "points_earned": points_earned,
    }


def _build_current_term_focus(snapshot: GradeSnapshot | None) -> dict | None:
    if snapshot is None:
        return None

    focus_courses = [_build_current_course_focus(course) for course in snapshot.courses]
    total_points_earned = sum(course["points_earned"] for course in focus_courses)
    total_evaluated_weight = sum(course["evaluated_weight_value"] for course in focus_courses)
    total_weight = sum(course["total_weight_value"] for course in focus_courses)
    weighted_progress = (total_evaluated_weight / total_weight * 100.0) if total_weight > 0 else None
    current_average = (total_points_earned / total_evaluated_weight) if total_evaluated_weight > 0 else None

    sorted_courses = sorted(
        focus_courses,
        key=lambda course: (-course["attention_priority"], -course["pressure_score"], course["title"]),
    )

    return {
        "label": snapshot.label,
        "term_description": snapshot.term.description,
        "level_description": snapshot.level.description,
        "courses_count": len(sorted_courses),
        "courses_with_data_count": sum(1 for course in sorted_courses if course["graded_components_count"] > 0),
        "attention_count": sum(1 for course in sorted_courses if course["attention_label"] == "Mas atencion"),
        "watch_count": sum(1 for course in sorted_courses if course["attention_label"] == "Vigilancia"),
        "relaxed_count": sum(1 for course in sorted_courses if course["attention_label"] == "Puedes relajarte"),
        "no_data_count": sum(1 for course in sorted_courses if course["attention_label"] == "Sin datos"),
        "graded_components_count": sum(course["graded_components_count"] for course in sorted_courses),
        "total_components_count": sum(course["weighted_components_count"] for course in sorted_courses),
        "current_average_value": current_average,
        "current_average_text": _format_grade(current_average),
        "weighted_progress_value": weighted_progress,
        "weighted_progress_text": _format_weight(weighted_progress or 0.0),
        "courses": sorted_courses,
    }


def build_dashboard_context(history: AcademicHistory, *, reference_time: datetime | None = None) -> dict:
    term_summaries = [_build_term_summary(snapshot) for snapshot in history.snapshots]
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
    current_term = _build_current_term_focus(history.snapshots[-1] if history.snapshots else None)

    return {
        "generated_at": history.generated_at,
        "generated_at_relative": _format_relative_datetime(history.generated_at, reference_time=reference_time),
        "generated_at_exact": _format_exact_datetime(history.generated_at),
        "latest_term_label": latest_term_label,
        "history_json": history.to_dict(),
        "current_term": current_term,
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
