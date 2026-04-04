from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from uac_grades.application.services import build_dashboard_context
from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence import SqliteHistoryStore

TEMPLATES_DIR = Path(__file__).with_name("templates")
STATIC_DIR = Path(__file__).with_name("static")


def _static_version() -> str:
    mtimes = [str(path.stat().st_mtime_ns) for path in STATIC_DIR.rglob("*") if path.is_file()]
    if not mtimes:
        return "dev"
    return max(mtimes)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    store = SqliteHistoryStore(settings.storage.sqlite_path)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="UA Grades Dashboard")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "sqlite_path": str(store.database_path)}

    @app.get("/api/history")
    async def api_history() -> dict:
        history = store.load_latest()
        if history is None:
            raise HTTPException(status_code=404, detail="Aun no existe un historial guardado en SQLite")
        return history.to_dict()

    @app.get("/api/analytics")
    async def api_analytics() -> dict:
        history = store.load_latest()
        if history is None:
            raise HTTPException(status_code=404, detail="Aun no existe un historial guardado en SQLite")
        context = build_dashboard_context(history)
        return {
            "generated_at": context["generated_at"],
            "latest_term_label": context["latest_term_label"],
            "cards": context["cards"],
            "term_summaries": context["term_summaries"],
        }

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        history = store.load_latest()
        context = {
            "request": request,
            "has_history": history is not None,
            "sqlite_path": str(store.database_path),
            "static_version": _static_version(),
        }

        if history is not None:
            context.update(build_dashboard_context(history))

        return templates.TemplateResponse(request=request, name="dashboard.html", context=context)

    return app
