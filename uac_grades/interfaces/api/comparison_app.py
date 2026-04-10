from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

from uac_grades.domain import ComparisonAssessmentPayload, ComparisonCoursePayload, ComparisonSyncPayload
from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence.comparison_sqlite_store import ComparisonSqliteStore


def _load_invites(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
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

    app = FastAPI(title="UA Comparison Dashboard")

    @app.get("/")
    async def index() -> dict:
        return {
            "status": "comparison-ready",
            "base_url": settings.comparison.base_url,
        }

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "sqlite_path": str(settings.comparison.sqlite_path),
        }

    @app.post("/api/comparison/sync")
    async def sync(payload: dict) -> dict:
        courses = []
        for course in payload.get("courses", []):
            assessments = [
                ComparisonAssessmentPayload(**assessment)
                for assessment in course.get("assessments", [])
            ]
            courses.append(
                ComparisonCoursePayload(
                    assessments=assessments,
                    **{key: value for key, value in course.items() if key != "assessments"},
                )
            )

        sync_payload = ComparisonSyncPayload(
            participant_name=str(payload.get("participant_name") or "").strip(),
            claim_code=payload.get("claim_code"),
            sync_token=payload.get("sync_token"),
            courses=courses,
        )

        try:
            issued_sync_token = None
            state = "updated"
            if sync_payload.claim_code and not sync_payload.sync_token:
                issued_sync_token = store.claim_identity(
                    display_name=sync_payload.participant_name,
                    claim_code=str(sync_payload.claim_code),
                )
                sync_payload = ComparisonSyncPayload(
                    participant_name=sync_payload.participant_name,
                    claim_code=None,
                    sync_token=issued_sync_token,
                    courses=sync_payload.courses,
                )
                state = "linked"
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
