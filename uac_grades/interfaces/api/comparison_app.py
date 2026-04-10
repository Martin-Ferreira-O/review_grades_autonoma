from __future__ import annotations

from fastapi import FastAPI

from uac_grades.infrastructure.config import Settings


def create_comparison_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load(require_credentials=False)

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

    return app
