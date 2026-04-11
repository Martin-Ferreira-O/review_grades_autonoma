from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from uac_grades.application.services.comparison_dashboard import build_comparison_dashboard_context
from uac_grades.domain import ComparisonAssessmentPayload, ComparisonCoursePayload, ComparisonSyncPayload
from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence.comparison_sqlite_store import ComparisonSqliteStore

TEMPLATES_DIR = Path(__file__).with_name("templates")
STATIC_DIR = Path(__file__).with_name("static")


def _static_version() -> str:
    mtimes = [str(path.stat().st_mtime_ns) for path in STATIC_DIR.rglob("*") if path.is_file()]
    if not mtimes:
        return "dev"
    return max(mtimes)


class ComparisonAssessmentRequest(BaseModel):
    assessment_name: str
    canonical_assessment_key: str
    weight: float
    grade: float | None
    grade_text: str
    must_pass: bool
    order_index: int


class ComparisonCourseRequest(BaseModel):
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
    assessments: list[ComparisonAssessmentRequest] = Field(default_factory=list)


class ComparisonSyncRequest(BaseModel):
    participant_name: str
    claim_code: str | None = None
    sync_token: str | None = None
    courses: list[ComparisonCourseRequest] = Field(default_factory=list)


def _load_invites(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Invalid comparison invite file: {path}") from error
    if not isinstance(raw, dict):
        raise RuntimeError(f"Invalid comparison invite file: {path}")
    return {str(name): str(code) for name, code in raw.items()}


def create_comparison_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load(require_credentials=False)
    store = ComparisonSqliteStore(settings.comparison.sqlite_path)
    invites_path = getattr(
        settings.comparison,
        "invites_path",
        settings.comparison.sqlite_path.parent / "comparison_claim_invites.json",
    )
    store.sync_claim_invites(_load_invites(invites_path))
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="UA Comparison Dashboard")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/api/comparison/dashboard")
    async def comparison_dashboard_data(
        participant: str | None = None,
        selected_course: str | None = None,
        selected_semester: str | None = None,
        selected_assessment: str | None = None,
    ) -> dict:
        return build_comparison_dashboard_context(
            store.load_dashboard_rows(),
            highlight_participant=participant,
            selected_course=selected_course,
            selected_semester=selected_semester,
            selected_assessment=selected_assessment,
        )

    @app.get("/", response_class=HTMLResponse)
    async def comparison_dashboard(
        request: Request,
        participant: str | None = None,
        selected_course: str | None = None,
        selected_semester: str | None = None,
        selected_assessment: str | None = None,
    ):
        context = {"request": request, "static_version": _static_version()}
        context.update(
            build_comparison_dashboard_context(
                store.load_dashboard_rows(),
                highlight_participant=participant,
                selected_course=selected_course,
                selected_semester=selected_semester,
                selected_assessment=selected_assessment,
            )
        )
        return templates.TemplateResponse(request=request, name="comparison_dashboard.html", context=context)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "sqlite_path": str(settings.comparison.sqlite_path),
        }

    @app.post("/api/comparison/sync")
    async def sync(payload: ComparisonSyncRequest) -> dict:
        courses = [
            ComparisonCoursePayload(
                canonical_course_key=course.canonical_course_key,
                course_code=course.course_code,
                course_title=course.course_title,
                term_code=course.term_code,
                term_label=course.term_label,
                section=course.section,
                status=course.status,
                current_grade=course.current_grade,
                final_grade=course.final_grade,
                comparison_grade=course.comparison_grade,
                assessments=[
                    ComparisonAssessmentPayload(
                        assessment_name=assessment.assessment_name,
                        canonical_assessment_key=assessment.canonical_assessment_key,
                        weight=assessment.weight,
                        grade=assessment.grade,
                        grade_text=assessment.grade_text,
                        must_pass=assessment.must_pass,
                        order_index=assessment.order_index,
                    )
                    for assessment in course.assessments
                ],
            )
            for course in payload.courses
        ]

        sync_payload = ComparisonSyncPayload(
            participant_name=payload.participant_name.strip(),
            claim_code=payload.claim_code,
            sync_token=payload.sync_token,
            courses=courses,
        )

        try:
            issued_sync_token = None
            state = "updated"
            if sync_payload.claim_code and not sync_payload.sync_token:
                identity = store.claim_and_replace_snapshot(
                    display_name=sync_payload.participant_name,
                    claim_code=str(sync_payload.claim_code),
                    courses=sync_payload.courses,
                )
                issued_sync_token = identity.sync_token
                sync_payload = ComparisonSyncPayload(
                    participant_name=identity.display_name,
                    claim_code=None,
                    sync_token=identity.sync_token,
                    courses=sync_payload.courses,
                )
                synced_at = identity.last_synced_at
                state = "linked"
            else:
                store.replace_participant_snapshot(sync_payload)
                synced_at = store.load_identity(
                    display_name=sync_payload.participant_name,
                    sync_token=str(sync_payload.sync_token),
                ).last_synced_at
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error

        return {
            "participant_name": sync_payload.participant_name,
            "state": state,
            "issued_sync_token": issued_sync_token,
            "synced_courses": len(sync_payload.courses),
            "synced_assessments": sum(len(course.assessments) for course in sync_payload.courses),
            "synced_at": synced_at,
        }

    return app
