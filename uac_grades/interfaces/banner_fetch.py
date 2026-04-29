from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from uac_grades.application.use_cases import FetchAcademicHistoryUseCase
from uac_grades.domain.models import AcademicHistory, Course, GradeComponent
from uac_grades.infrastructure.auth import MicrosoftAuthenticator, TotpCodeProvider
from uac_grades.infrastructure.banner import BannerGateway, BannerHttpClient
from uac_grades.infrastructure.banner.contract_capture import BannerHttpContractCapture
from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence import (
    DebugArtifactStore,
    JsonHistoryExporter,
    SessionStateStore,
    SqliteHistoryStore,
)


class HistoryStore(Protocol):
    database_path: Path

    def load_latest(self) -> AcademicHistory | None:
        ...

    def save(self, history: AcademicHistory) -> int:
        ...


@dataclass(frozen=True)
class NewGrade:
    term_label: str
    course_code: str
    course_title: str
    evaluation: str
    grade: str
    previous_grade: str | None = None

    def to_dict(self) -> dict:
        return {
            "term_label": self.term_label,
            "course_code": self.course_code,
            "course_title": self.course_title,
            "evaluation": self.evaluation,
            "grade": self.grade,
            "previous_grade": self.previous_grade,
        }


@dataclass(frozen=True)
class BannerFetchResult:
    history: AcademicHistory
    first_fetch: bool
    full_refresh: bool
    new_grades: list[NewGrade]
    json_path: Path
    database_path: Path
    run_id: int


def _clean_text(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _course_grade(course: Course) -> tuple[str, str] | None:
    for label, value in (
        ("Nota final", course.final_grade),
        ("Nota del ramo", course.grade),
        ("Nota parcial", course.midterm_grade),
    ):
        grade = _clean_text(value)
        if grade is not None:
            return label, grade
    return None


def _component_grade(component: GradeComponent) -> str | None:
    grade = _clean_text(component.grade)
    if grade is not None:
        return grade

    score_text = _clean_text(component.score_text)
    if score_text is not None:
        return score_text

    percentage = _clean_text(component.percentage)
    if percentage is not None:
        return f"{percentage}%"

    return None


def _course_key(course: Course) -> str:
    if course.course_id:
        return f"id:{course.course_id}"
    if course.nrc:
        return f"nrc:{course.nrc}"
    return "course:" + "|".join(
        part.casefold()
        for part in (course.code, course.section or "", course.title)
        if part
    )


def _component_key(component: GradeComponent, path: tuple[str, ...]) -> str:
    if component.component_id:
        return f"id:{component.component_id}"
    return "path:" + "/".join(path)


def _record_key(*parts: str) -> str:
    return "\x1f".join(parts)


def _component_records(
    *,
    term_code: str,
    level_code: str,
    term_label: str,
    course: Course,
    components: list[GradeComponent],
    path: tuple[str, ...] = (),
) -> dict[str, NewGrade]:
    records: dict[str, NewGrade] = {}
    course_key = _course_key(course)

    for index, component in enumerate(components):
        path_label = _clean_text(component.code) or component.name or f"componente-{index}"
        component_path = (*path, f"{index}:{path_label.casefold()}")
        child_records = _component_records(
            term_code=term_code,
            level_code=level_code,
            term_label=term_label,
            course=course,
            components=component.subcomponents,
            path=component_path,
        )
        if child_records:
            records.update(child_records)
            continue

        grade = _component_grade(component)
        if grade is None:
            continue

        key = _record_key(
            term_code,
            level_code,
            course_key,
            "component",
            _component_key(component, component_path),
        )
        records[key] = NewGrade(
            term_label=term_label,
            course_code=course.code,
            course_title=course.title,
            evaluation=component.name,
            grade=grade,
        )

    return records


def _grade_records(history: AcademicHistory) -> dict[str, NewGrade]:
    records: dict[str, NewGrade] = {}
    for snapshot in history.snapshots:
        term_code = snapshot.term.code
        level_code = snapshot.level.code
        for course in snapshot.courses:
            course_key = _course_key(course)
            course_grade = _course_grade(course)
            if course_grade is not None:
                label, grade = course_grade
                key = _record_key(term_code, level_code, course_key, "course-grade")
                records[key] = NewGrade(
                    term_label=snapshot.label,
                    course_code=course.code,
                    course_title=course.title,
                    evaluation=label,
                    grade=grade,
                )

            records.update(
                _component_records(
                    term_code=term_code,
                    level_code=level_code,
                    term_label=snapshot.label,
                    course=course,
                    components=course.components,
                )
            )

    return records


def detect_new_grades(
    previous_history: AcademicHistory, current_history: AcademicHistory
) -> list[NewGrade]:
    previous_records = _grade_records(previous_history)
    current_records = _grade_records(current_history)
    new_grades: list[NewGrade] = []

    for key, current_record in current_records.items():
        previous_record = previous_records.get(key)
        if previous_record is None:
            new_grades.append(current_record)
        elif previous_record.grade != current_record.grade:
            new_grades.append(
                replace(current_record, previous_grade=previous_record.grade)
            )

    return new_grades


async def fetch_banner_history(
    settings: Settings,
    *,
    history_store: HistoryStore | None = None,
    full_refresh: bool = False,
) -> BannerFetchResult:
    debug_store = DebugArtifactStore(settings.storage.output_dir)
    exporter = JsonHistoryExporter(settings.storage.output_dir)
    sqlite_store = history_store or SqliteHistoryStore(settings.storage.sqlite_path)
    session_store = SessionStateStore(settings.storage.storage_state_path)
    contract_capture = (
        BannerHttpContractCapture(debug_store)
        if settings.browser.capture_banner_contract
        else None
    )
    http_client = BannerHttpClient(
        settings, session_store, contract_capture=contract_capture
    )

    authenticator = MicrosoftAuthenticator(
        settings=settings,
        debug_store=debug_store,
        session_store=session_store,
        totp_provider=TotpCodeProvider(settings.credentials.totp_secret),
        http_client=http_client,
    )
    gateway = BannerGateway(
        settings=settings, debug_store=debug_store, http_client=http_client
    )
    use_case = FetchAcademicHistoryUseCase(auth=authenticator, grades=gateway)
    stored_history = sqlite_store.load_latest()
    previous_history = None if full_refresh else stored_history

    try:
        history = await use_case.execute(
            previous_history=previous_history, full_refresh=full_refresh
        )
        json_path = exporter.export(history)
        run_id = sqlite_store.save(history)
        new_grades = (
            [] if stored_history is None else detect_new_grades(stored_history, history)
        )

        return BannerFetchResult(
            history=history,
            first_fetch=stored_history is None,
            full_refresh=full_refresh,
            new_grades=new_grades,
            json_path=json_path,
            database_path=sqlite_store.database_path,
            run_id=run_id,
        )
    finally:
        if contract_capture is not None:
            await contract_capture.stop()
