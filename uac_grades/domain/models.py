from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str
    totp_secret: str


@dataclass(frozen=True)
class AcademicTerm:
    code: str
    description: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AcademicTerm":
        return cls(
            code=str(payload.get("code") or payload.get("term_code") or "").strip(),
            description=str(payload.get("description") or payload.get("term_description") or "").strip(),
        )


@dataclass(frozen=True)
class AcademicLevel:
    code: str
    description: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AcademicLevel":
        return cls(
            code=str(payload.get("code") or payload.get("level_code") or "").strip(),
            description=str(payload.get("description") or payload.get("level_description") or "").strip(),
        )


@dataclass(frozen=True)
class GradeComponent:
    component_id: Optional[str]
    name: str
    code: Optional[str]
    description: Optional[str]
    weight: Optional[str]
    score: Optional[str]
    total_score: Optional[str]
    score_text: Optional[str]
    grade: Optional[str]
    percentage: Optional[str]
    must_pass: bool
    stage: Optional[str]
    is_main_component: bool
    has_subcomponents: bool
    subcomponents: list["GradeComponent"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "nombre": self.name,
            "codigo": self.code,
            "descripcion": self.description,
            "peso": self.weight,
            "puntaje": self.score,
            "puntaje_total": self.total_score,
            "puntaje_texto": self.score_text,
            "calificacion": self.grade,
            "porcentaje": self.percentage,
            "debe_aprobar": self.must_pass,
            "etapa": self.stage,
            "es_componente_principal": self.is_main_component,
            "tiene_subcomponentes": self.has_subcomponents,
            "subcomponentes": [subcomponent.to_dict() for subcomponent in self.subcomponents],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GradeComponent":
        return cls(
            component_id=payload.get("component_id"),
            name=str(payload.get("nombre") or payload.get("name") or "").strip(),
            code=payload.get("codigo") or payload.get("code"),
            description=payload.get("descripcion") or payload.get("description"),
            weight=payload.get("peso") or payload.get("weight"),
            score=payload.get("puntaje") or payload.get("score"),
            total_score=payload.get("puntaje_total") or payload.get("total_score"),
            score_text=payload.get("puntaje_texto") or payload.get("score_text"),
            grade=payload.get("calificacion") or payload.get("grade"),
            percentage=payload.get("porcentaje") or payload.get("percentage"),
            must_pass=bool(payload.get("debe_aprobar") if "debe_aprobar" in payload else payload.get("must_pass")),
            stage=payload.get("etapa") or payload.get("stage"),
            is_main_component=bool(
                payload.get("es_componente_principal")
                if "es_componente_principal" in payload
                else payload.get("is_main_component")
            ),
            has_subcomponents=bool(
                payload.get("tiene_subcomponentes")
                if "tiene_subcomponentes" in payload
                else payload.get("has_subcomponents")
            ),
            subcomponents=[
                cls.from_dict(subcomponent)
                for subcomponent in payload.get("subcomponentes") or payload.get("subcomponents") or []
            ],
        )


@dataclass(frozen=True)
class Course:
    course_id: Optional[str]
    nrc: Optional[str]
    code: str
    section: Optional[str]
    title: str
    grade: Optional[str]
    final_grade: Optional[str]
    midterm_grade: Optional[str]
    term_description: Optional[str]
    level_description: Optional[str]
    campus: Optional[str]
    study_path: Optional[str]
    attempted_hours: Optional[str]
    earned_hours: Optional[str]
    gpa_hours: Optional[str]
    quality_points: Optional[str]
    components_available: bool
    components: list[GradeComponent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.course_id,
            "nrc": self.nrc,
            "codigo": self.code,
            "seccion": self.section,
            "asignatura": self.title,
            "nota": self.grade,
            "nota_final": self.final_grade,
            "nota_parcial": self.midterm_grade,
            "periodo": self.term_description,
            "nivel": self.level_description,
            "campus": self.campus,
            "plan_estudios": self.study_path,
            "horas_intentadas": self.attempted_hours,
            "horas_ganadas": self.earned_hours,
            "horas_gpa": self.gpa_hours,
            "puntos_calidad": self.quality_points,
            "componentes_disponibles": self.components_available,
            "componentes": [component.to_dict() for component in self.components],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Course":
        return cls(
            course_id=payload.get("id") or payload.get("course_id"),
            nrc=payload.get("nrc"),
            code=str(payload.get("codigo") or payload.get("code") or "").strip(),
            section=payload.get("seccion") or payload.get("section"),
            title=str(payload.get("asignatura") or payload.get("title") or "").strip(),
            grade=payload.get("nota") or payload.get("grade"),
            final_grade=payload.get("nota_final") or payload.get("final_grade"),
            midterm_grade=payload.get("nota_parcial") or payload.get("midterm_grade"),
            term_description=payload.get("periodo") or payload.get("term_description"),
            level_description=payload.get("nivel") or payload.get("level_description"),
            campus=payload.get("campus"),
            study_path=payload.get("plan_estudios") or payload.get("study_path"),
            attempted_hours=payload.get("horas_intentadas") or payload.get("attempted_hours"),
            earned_hours=payload.get("horas_ganadas") or payload.get("earned_hours"),
            gpa_hours=payload.get("horas_gpa") or payload.get("gpa_hours"),
            quality_points=payload.get("puntos_calidad") or payload.get("quality_points"),
            components_available=bool(
                payload.get("componentes_disponibles")
                if "componentes_disponibles" in payload
                else payload.get("components_available")
            ),
            components=[
                GradeComponent.from_dict(component)
                for component in payload.get("componentes") or payload.get("components") or []
            ],
        )


@dataclass(frozen=True)
class GradeSnapshot:
    term: AcademicTerm
    level: AcademicLevel
    courses: list[Course]

    @property
    def label(self) -> str:
        return f"{self.term.description} | {self.level.description}"

    def to_dict(self) -> dict:
        return {
            "term_code": self.term.code,
            "term_description": self.term.description,
            "level_code": self.level.code,
            "level_description": self.level.description,
            "courses_count": len(self.courses),
            "courses": [course.to_dict() for course in self.courses],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GradeSnapshot":
        return cls(
            term=AcademicTerm.from_dict(payload),
            level=AcademicLevel.from_dict(payload),
            courses=[Course.from_dict(course) for course in payload.get("courses") or []],
        )


@dataclass(frozen=True)
class AcademicHistory:
    snapshots: list[GradeSnapshot]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def courses_count(self) -> int:
        return sum(len(snapshot.courses) for snapshot in self.snapshots)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "snapshots_count": len(self.snapshots),
            "courses_count": self.courses_count,
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AcademicHistory":
        return cls(
            generated_at=str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat()),
            snapshots=[GradeSnapshot.from_dict(snapshot) for snapshot in payload.get("snapshots") or []],
        )


@dataclass(frozen=True)
class AttendanceAbsenceDetail:
    meeting_date: str
    hours: Optional[str]
    status: Optional[str]

    def to_dict(self) -> dict:
        return {
            "fecha": self.meeting_date,
            "horas": self.hours,
            "estado": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AttendanceAbsenceDetail":
        return cls(
            meeting_date=str(payload.get("fecha") or payload.get("meeting_date") or "").strip(),
            hours=payload.get("horas") or payload.get("hours"),
            status=payload.get("estado") or payload.get("status"),
        )


@dataclass(frozen=True)
class AttendanceSection:
    term_code: str
    subject_code: str
    course_number: str
    course_reference_number: Optional[str]
    section: Optional[str]
    session_indicator: Optional[str]
    section_title: str
    subject_description: Optional[str]
    schedule: list[str]
    time: Optional[str]
    section_meeting_id: Optional[str]
    missed: int
    percentage: Optional[float]
    total_sessions: Optional[int]
    sessions_attended: Optional[int]
    class_cancelled: Optional[int]
    absence_notified_count: Optional[int]
    absences: list[AttendanceAbsenceDetail] = field(default_factory=list)

    @property
    def course_code(self) -> str:
        return " ".join(part for part in (self.subject_code, self.course_number) if part)

    def to_dict(self) -> dict:
        return {
            "periodo": self.term_code,
            "materia": self.subject_code,
            "curso": self.course_number,
            "codigo": self.course_code,
            "nrc": self.course_reference_number,
            "seccion": self.section,
            "sesion": self.session_indicator,
            "titulo": self.section_title,
            "descripcion_materia": self.subject_description,
            "horario": self.schedule,
            "hora": self.time,
            "section_meeting_id": self.section_meeting_id,
            "ausencias": self.missed,
            "porcentaje": self.percentage,
            "sesiones_totales": self.total_sessions,
            "sesiones_presente": self.sessions_attended,
            "clases_anuladas": self.class_cancelled,
            "ausencias_notificadas": self.absence_notified_count,
            "detalle_ausencias": [absence.to_dict() for absence in self.absences],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AttendanceSection":
        return cls(
            term_code=str(payload.get("periodo") or payload.get("term_code") or "").strip(),
            subject_code=str(payload.get("materia") or payload.get("subject_code") or "").strip(),
            course_number=str(payload.get("curso") or payload.get("course_number") or "").strip(),
            course_reference_number=payload.get("nrc") or payload.get("course_reference_number"),
            section=payload.get("seccion") or payload.get("section"),
            session_indicator=payload.get("sesion") or payload.get("session_indicator"),
            section_title=str(payload.get("titulo") or payload.get("section_title") or "").strip(),
            subject_description=payload.get("descripcion_materia") or payload.get("subject_description"),
            schedule=list(payload.get("horario") or payload.get("schedule") or []),
            time=payload.get("hora") or payload.get("time"),
            section_meeting_id=payload.get("section_meeting_id"),
            missed=int(payload.get("ausencias") if payload.get("ausencias") is not None else payload.get("missed") or 0),
            percentage=(
                float(payload.get("porcentaje") if payload.get("porcentaje") is not None else payload.get("percentage"))
                if (payload.get("porcentaje") if payload.get("porcentaje") is not None else payload.get("percentage")) not in (None, "")
                else None
            ),
            total_sessions=(
                int(payload.get("sesiones_totales") if payload.get("sesiones_totales") is not None else payload.get("total_sessions"))
                if (payload.get("sesiones_totales") if payload.get("sesiones_totales") is not None else payload.get("total_sessions")) not in (None, "")
                else None
            ),
            sessions_attended=(
                int(payload.get("sesiones_presente") if payload.get("sesiones_presente") is not None else payload.get("sessions_attended"))
                if (payload.get("sesiones_presente") if payload.get("sesiones_presente") is not None else payload.get("sessions_attended")) not in (None, "")
                else None
            ),
            class_cancelled=(
                int(payload.get("clases_anuladas") if payload.get("clases_anuladas") is not None else payload.get("class_cancelled"))
                if (payload.get("clases_anuladas") if payload.get("clases_anuladas") is not None else payload.get("class_cancelled")) not in (None, "")
                else None
            ),
            absence_notified_count=(
                int(payload.get("ausencias_notificadas") if payload.get("ausencias_notificadas") is not None else payload.get("absence_notified_count"))
                if (payload.get("ausencias_notificadas") if payload.get("ausencias_notificadas") is not None else payload.get("absence_notified_count")) not in (None, "")
                else None
            ),
            absences=[
                AttendanceAbsenceDetail.from_dict(absence)
                for absence in payload.get("detalle_ausencias") or payload.get("absences") or []
            ],
        )


@dataclass(frozen=True)
class AttendanceSnapshot:
    term_code: str
    sections: list[AttendanceSection]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "term_code": self.term_code,
            "sections_count": len(self.sections),
            "sections": [section.to_dict() for section in self.sections],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AttendanceSnapshot":
        return cls(
            generated_at=str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat()),
            term_code=str(payload.get("term_code") or payload.get("periodo") or "").strip(),
            sections=[
                AttendanceSection.from_dict(section)
                for section in payload.get("sections") or payload.get("secciones") or []
            ],
        )
