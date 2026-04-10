from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ComparisonIdentity:
    display_name: str
    sync_token: str
    last_synced_at: str | None = None


@dataclass(frozen=True)
class ComparisonAssessmentPayload:
    assessment_name: str
    canonical_assessment_key: str
    weight: float
    grade: float | None
    grade_text: str
    must_pass: bool
    order_index: int


@dataclass(frozen=True)
class ComparisonCoursePayload:
    canonical_course_key: str
    course_code: str
    course_title: str
    term_code: str
    term_label: str
    section: str | None
    status: str
    current_grade: float | None
    final_grade: float | None
    comparison_grade: float | None
    assessments: list[ComparisonAssessmentPayload] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonSyncPayload:
    participant_name: str
    claim_code: str | None
    sync_token: str | None
    courses: list[ComparisonCoursePayload] = field(default_factory=list)
