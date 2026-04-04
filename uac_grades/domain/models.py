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
