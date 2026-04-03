from __future__ import annotations

import html
from typing import Optional

from uac_grades.domain.models import AcademicLevel, AcademicTerm, Course, GradeComponent, GradeSnapshot


def banner_flag_to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"Y", "TRUE", "1", "SI", "S"}


def normalize_text(value) -> str:
    return html.unescape(str(value)).strip().casefold()


def course_has_component_details(course: dict) -> bool:
    return course.get("hasComponent") == "Y" and course.get("gradeDetailDisplayInd") == "Y"


def build_course_label(course: dict) -> str:
    return " ".join(
        part
        for part in [
            str(course.get("subjectCode", "")).strip(),
            str(course.get("courseNumber", "")).strip(),
            str(course.get("courseReferenceNumber", "")).strip(),
        ]
        if part
    )


def pick_first_valid_option(options: list, description: str) -> dict:
    if not options:
        raise RuntimeError(f"Banner no devolvió opciones para {description}")

    invalid_codes = {"", "-1", "-2", "all"}
    for option in options:
        code = str(option.get("code", "")).strip()
        if code.lower() not in invalid_codes:
            return {
                "code": code,
                "description": html.unescape(str(option.get("description", "")).strip()),
            }

    raise RuntimeError(f"No se encontró una opción válida para {description}")


def describe_options(options: list) -> str:
    return "; ".join(
        f"{str(option.get('code', '')).strip()} | {html.unescape(str(option.get('description', '')).strip())}"
        for option in options
    )


def pick_target_option(
    options: list,
    description: str,
    *,
    target_code: Optional[str] = None,
    target_description: Optional[str] = None,
    fallback_first: bool = False,
) -> dict:
    if target_code:
        for option in options:
            code = str(option.get("code", "")).strip()
            if code == target_code:
                return pick_first_valid_option([option], description)

    if target_description:
        target_description_normalized = normalize_text(target_description)
        for option in options:
            option_description = normalize_text(option.get("description", ""))
            if option_description == target_description_normalized or target_description_normalized in option_description:
                return pick_first_valid_option([option], description)

    if fallback_first:
        return pick_first_valid_option(options, description)

    raise RuntimeError(
        f"No se encontró {description} objetivo. "
        f"Buscado: code={target_code!r}, description={target_description!r}. "
        f"Disponibles: {describe_options(options)}"
    )


def normalize_course_grade(course: dict) -> Optional[str]:
    for key in ("calculatedFinalGrade", "finalGrade", "historyFinalGrade", "midtermGrade"):
        value = course.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def normalize_stage(indicator: Optional[str]) -> Optional[str]:
    if indicator == "M":
        return "Parcial"
    if indicator == "F":
        return "Final"
    if indicator in (None, ""):
        return None
    return str(indicator)


def format_component_name(item: dict) -> str:
    parts = [
        html.unescape(str(item.get("name", "")).strip()),
        html.unescape(str(item.get("description", "")).strip()),
    ]
    return " - ".join(part for part in parts if part)


def format_score(item: dict) -> Optional[str]:
    score = item.get("score")
    total = item.get("totalScore")
    if score not in (None, "") and total not in (None, ""):
        return f"{score}/{total}"
    if score not in (None, ""):
        return str(score)
    return None


def map_component(item: dict) -> GradeComponent:
    subcomponents = [map_component(subcomponent) for subcomponent in item.get("subcomponents", [])]

    return GradeComponent(
        component_id=item.get("componentId"),
        name=format_component_name(item),
        code=html.unescape(str(item.get("name", "")).strip()) or None,
        description=html.unescape(str(item.get("description", "")).strip()) or None,
        weight=item.get("weight"),
        score=item.get("score"),
        total_score=item.get("totalScore"),
        score_text=format_score(item),
        grade=item.get("grade"),
        percentage=item.get("percentage"),
        must_pass=banner_flag_to_bool(item.get("mustPass")),
        stage=normalize_stage(item.get("inclusionIndicator")),
        is_main_component=banner_flag_to_bool(item.get("isComponent")),
        has_subcomponents=banner_flag_to_bool(item.get("hasSubComponents")) or bool(subcomponents),
        subcomponents=subcomponents,
    )


def map_course(course: dict) -> Course:
    return Course(
        course_id=course.get("id"),
        nrc=course.get("courseReferenceNumber"),
        code=" ".join(part for part in [course.get("subjectCode"), course.get("courseNumber")] if part),
        section=course.get("section"),
        title=html.unescape(str(course.get("courseTitle", "")).strip()),
        grade=normalize_course_grade(course),
        final_grade=course.get("calculatedFinalGrade") or course.get("finalGrade") or course.get("historyFinalGrade"),
        midterm_grade=course.get("midtermGrade"),
        term_description=course.get("termDescription"),
        level_description=course.get("levelDescription"),
        campus=course.get("campusCode"),
        study_path=course.get("studyPathName"),
        attempted_hours=course.get("hoursAttempted"),
        earned_hours=course.get("hoursEarned"),
        gpa_hours=course.get("gpaHours"),
        quality_points=course.get("qualityPoints"),
        components_available=course_has_component_details(course),
        components=[map_component(component) for component in course.get("components", [])],
    )


def build_snapshot(term_raw: dict, level_raw: dict, courses_raw: list) -> GradeSnapshot:
    return GradeSnapshot(
        term=AcademicTerm(code=term_raw["code"], description=term_raw["description"]),
        level=AcademicLevel(code=level_raw["code"], description=level_raw["description"]),
        courses=[map_course(course) for course in courses_raw],
    )
