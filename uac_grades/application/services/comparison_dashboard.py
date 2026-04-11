from __future__ import annotations

from collections import defaultdict


def _select_option(options: list[dict[str, str]], requested_value: str | None) -> str | None:
    values = {option["value"] for option in options}
    if requested_value in values:
        return requested_value
    if not options:
        return None
    return options[0]["value"]


def _average(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)


def _rank_with_points(entries: dict[str, list[float | None]]) -> list[dict]:
    ranking = [
        {
            "display_name": display_name,
            "average": _average(grades),
            "wins": 0,
            "podiums": 0,
            "points": 0,
        }
        for display_name, grades in entries.items()
    ]
    ranking.sort(key=lambda item: (item["average"] is not None, item["average"] or -1), reverse=True)
    leader_average = ranking[0]["average"] if ranking else None
    for index, row in enumerate(ranking[:3]):
        row["podiums"] += 1
        row["points"] += [3, 2, 1][index]
        if index == 0:
            row["wins"] += 1
    for row in ranking:
        row["gap_to_leader"] = 0.0 if leader_average is None or row["average"] is None else round(leader_average - row["average"], 2)
    return ranking


def build_comparison_dashboard_context(
    rows: list[dict],
    *,
    highlight_participant: str | None = None,
    selected_course: str | None = None,
    selected_semester: str | None = None,
    selected_assessment: str | None = None,
) -> dict:
    by_course: defaultdict[tuple[str, str], list[float | None]] = defaultdict(list)
    by_semester: defaultdict[tuple[str, str], list[float | None]] = defaultdict(list)
    by_historical: defaultdict[str, list[float | None]] = defaultdict(list)
    by_assessment: defaultdict[tuple[str, str, str], list[float | None]] = defaultdict(list)
    assessment_order: dict[tuple[str, str], tuple[int, str]] = {}
    course_labels: dict[str, str] = {}
    semester_labels: dict[str, str] = {}
    seen_attempts: set[tuple[str, str, str, str]] = set()

    for row in rows:
        display_name = row["display_name"]
        course_key = row["canonical_course_key"]
        term_code = row["term_code"]
        grade = row.get("comparison_grade")
        attempt_key = (display_name, course_key, term_code, row["term_label"])

        if attempt_key not in seen_attempts:
            seen_attempts.add(attempt_key)
            by_course[(course_key, display_name)].append(grade)
            by_semester[(term_code, display_name)].append(grade)
            by_historical[display_name].append(grade)
        if row.get("assessment_name") and row.get("assessment_grade") is not None:
            assessment_name = row["assessment_name"]
            by_assessment[(course_key, assessment_name, display_name)].append(row["assessment_grade"])
            order_index = row.get("assessment_order_index")
            sort_key = (order_index if isinstance(order_index, int) else 10**9, assessment_name)
            existing_sort_key = assessment_order.get((course_key, assessment_name))
            if existing_sort_key is None or sort_key < existing_sort_key:
                assessment_order[(course_key, assessment_name)] = sort_key
        course_labels[course_key] = row["course_title"]
        semester_labels[term_code] = row["term_label"]

    course_options = [
        {"value": key, "label": label}
        for key, label in sorted(course_labels.items(), key=lambda item: (item[1], item[0]))
    ]
    semester_options = [
        {"value": key, "label": label}
        for key, label in sorted(semester_labels.items(), key=lambda item: item[0], reverse=True)
    ]
    selected_course = _select_option(course_options, selected_course)
    selected_semester = _select_option(semester_options, selected_semester)
    assessment_options = [
        {"value": assessment_name, "label": assessment_name}
        for assessment_name in sorted(
            {assessment_name for course_key, assessment_name, _display_name in by_assessment if course_key == selected_course},
            key=lambda assessment_name: assessment_order.get((selected_course, assessment_name), (10**9, assessment_name)),
        )
    ]
    selected_assessment = _select_option(assessment_options, selected_assessment)

    course_ranking = _rank_with_points(
        {display_name: grades for (course_key, display_name), grades in by_course.items() if course_key == selected_course}
    )
    assessment_ranking = _rank_with_points(
        {
            display_name: grades
            for (course_key, assessment_name, display_name), grades in by_assessment.items()
            if course_key == selected_course and assessment_name == selected_assessment
        }
    )
    semester_ranking = _rank_with_points(
        {display_name: grades for (term_code, display_name), grades in by_semester.items() if term_code == selected_semester}
    )
    historical_ranking = _rank_with_points(dict(by_historical))
    selected_row = next((row for row in historical_ranking if row["display_name"] == highlight_participant), None)
    group_average = _average([row["average"] for row in historical_ranking if row["average"] is not None])

    return {
        "summary": {
            "leaders": [row["display_name"] for row in historical_ranking[:3]],
            "participants": len(by_historical),
            "group_average": group_average,
            "leader_points": historical_ranking[0]["points"] if historical_ranking else 0,
            "selected_participant": selected_row,
        },
        "tabs": {
            "course": {
                "selected": selected_course,
                "options": course_options,
                "ranking": course_ranking,
                "selected_assessment": selected_assessment,
                "assessment_options": assessment_options,
                "assessment_ranking": assessment_ranking,
            },
            "semester": {
                "selected": selected_semester,
                "options": semester_options,
                "ranking": semester_ranking,
            },
            "historical": {
                "ranking": historical_ranking,
            },
        },
    }
