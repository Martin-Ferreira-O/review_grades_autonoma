from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str
    totp_secret: str


@dataclass(frozen=True)
class AcademicTerm:
    code: str
    description: str


@dataclass(frozen=True)
class AcademicLevel:
    code: str
    description: str


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


@dataclass(frozen=True)
class GradeSnapshot:
    term: AcademicTerm
    level: AcademicLevel
    courses: list[Course]

    def to_dict(self) -> dict:
        return {
            "term_code": self.term.code,
            "term_description": self.term.description,
            "level_code": self.level.code,
            "level_description": self.level.description,
            "courses_count": len(self.courses),
            "courses": [course.to_dict() for course in self.courses],
        }
