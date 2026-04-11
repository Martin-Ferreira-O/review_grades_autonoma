from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from uac_grades.application.services import build_comparison_sync_payload, build_dashboard_context
from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.comparison import ComparisonSyncClient
from uac_grades.infrastructure.persistence import ComparisonIdentityStore, SqliteHistoryStore

TEMPLATES_DIR = Path(__file__).with_name("templates")
STATIC_DIR = Path(__file__).with_name("static")


def _static_version() -> str:
    mtimes = [str(path.stat().st_mtime_ns) for path in STATIC_DIR.rglob("*") if path.is_file()]
    if not mtimes:
        return "dev"
    return max(mtimes)


def _downstream_error_detail(error: httpx.HTTPStatusError):
    try:
        payload = error.response.json()
    except ValueError:
        payload = error.response.text.strip()

    if isinstance(payload, dict) and "detail" in payload:
        return payload["detail"]
    if payload:
        return payload
    return f"Comparison sync failed with status {error.response.status_code}"


def create_app(
    settings: Settings | None = None,
    *,
    history_store=None,
    comparison_client=None,
    identity_store=None,
) -> FastAPI:
    settings = settings or Settings.load()
    store = history_store or SqliteHistoryStore(settings.storage.sqlite_path)
    comparison_client = comparison_client or ComparisonSyncClient(base_url=settings.comparison.base_url)
    identity_store = identity_store or ComparisonIdentityStore(settings.comparison.identity_path)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="UA Grades Dashboard")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "sqlite_path": str(store.database_path)}

    @app.get("/comparison/sync", response_class=HTMLResponse)
    async def comparison_sync_page(request: Request):
        identity = identity_store.load()
        comparison_dashboard_url = settings.comparison.base_url
        if identity is not None:
            comparison_dashboard_url = f"{settings.comparison.base_url}?participant={quote(identity.display_name)}"

        return templates.TemplateResponse(
            request=request,
            name="comparison_sync.html",
            context={
                "request": request,
                "display_name": identity.display_name if identity else "",
                "is_linked": identity is not None,
                "last_synced_at": identity.last_synced_at if identity else None,
                "comparison_base_url": settings.comparison.base_url,
                "comparison_dashboard_url": comparison_dashboard_url,
                "static_version": _static_version(),
            },
        )

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

    @app.get("/api/comparison/link-status")
    async def comparison_link_status() -> dict:
        identity = identity_store.load()
        return {
            "linked": identity is not None,
            "display_name": identity.display_name if identity else None,
            "comparison_base_url": settings.comparison.base_url,
            "last_synced_at": identity.last_synced_at if identity else None,
        }

    @app.post("/api/comparison/sync")
    async def comparison_sync(request: Request) -> dict:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            parsed_form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
            payload = {key: values[-1] if values else "" for key, values in parsed_form.items()}

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload de sincronizacion invalido")

        history = store.load_latest()
        if history is None:
            raise HTTPException(status_code=404, detail="Aun no existe historial local para sincronizar")

        identity = identity_store.load()
        sync_payload = build_comparison_sync_payload(
            history,
            participant_name=str(payload.get("participant_name") or (identity.display_name if identity else "")).strip(),
            claim_code=payload.get("claim_code") if identity is None else None,
            sync_token=identity.sync_token if identity else None,
        )
        try:
            response = await comparison_client.sync(
                {
                    "participant_name": sync_payload.participant_name,
                    "claim_code": sync_payload.claim_code,
                    "sync_token": sync_payload.sync_token,
                    "courses": [asdict(course) for course in sync_payload.courses],
                }
            )
        except httpx.HTTPStatusError as error:
            raise HTTPException(status_code=error.response.status_code, detail=_downstream_error_detail(error)) from error
        except httpx.RequestError as error:
            raise HTTPException(status_code=502, detail="No se pudo conectar con el servicio de comparacion") from error

        issued_sync_token = response.get("issued_sync_token")
        sync_token_to_save = issued_sync_token or (identity.sync_token if identity else None)
        if sync_token_to_save:
            identity_store.save(
                display_name=sync_payload.participant_name,
                sync_token=str(sync_token_to_save),
                last_synced_at=response.get("synced_at"),
            )
        return response

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        history = store.load_latest()
        context = {
            "request": request,
            "has_history": history is not None,
            "sqlite_path": str(store.database_path),
            "static_version": _static_version(),
            "comparison_base_url": settings.comparison.base_url,
        }

        if history is not None:
            context.update(build_dashboard_context(history))

        return templates.TemplateResponse(request=request, name="dashboard.html", context=context)

    return app
