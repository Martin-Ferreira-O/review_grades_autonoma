from __future__ import annotations

import argparse
import asyncio

import uvicorn

from uac_grades.application.use_cases import FetchAcademicHistoryUseCase
from uac_grades.infrastructure.auth import MicrosoftAuthenticator, TotpCodeProvider
from uac_grades.infrastructure.banner import BannerGateway
from uac_grades.infrastructure.browser import PlaywrightBrowserSession
from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence import (
    DebugArtifactStore,
    JsonHistoryExporter,
    SessionStateStore,
    SqliteHistoryStore,
)
from uac_grades.infrastructure.presenters import ConsoleHistoryPresenter
from uac_grades.interfaces.api import create_app


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UA grades: extraccion y dashboard local")
    subparsers = parser.add_subparsers(dest="command")

    fetch_parser = subparsers.add_parser("fetch", help="Extrae el historial completo desde Banner")
    fetch_parser.add_argument("--no-pause", action="store_true", help="No espera Enter al finalizar")

    serve_parser = subparsers.add_parser("serve", help="Inicia el dashboard web local")
    serve_parser.add_argument("--host", default=None, help="Host para el servidor web")
    serve_parser.add_argument("--port", type=int, default=None, help="Puerto para el servidor web")

    return parser


async def _run_fetch(*, pause: bool) -> None:
    settings = Settings.load()
    debug_store = DebugArtifactStore(settings.storage.output_dir)
    exporter = JsonHistoryExporter(settings.storage.output_dir)
    sqlite_store = SqliteHistoryStore(settings.storage.sqlite_path)
    presenter = ConsoleHistoryPresenter()

    async with PlaywrightBrowserSession(settings) as browser:
        authenticator = MicrosoftAuthenticator(
            settings=settings,
            browser=browser,
            debug_store=debug_store,
            session_store=SessionStateStore(settings.storage.storage_state_path),
            totp_provider=TotpCodeProvider(settings.credentials.totp_secret),
        )
        gateway = BannerGateway(settings=settings, browser=browser, debug_store=debug_store)
        use_case = FetchAcademicHistoryUseCase(auth=authenticator, grades=gateway)

        try:
            history = await use_case.execute()
            presenter.present(history)

            json_path = exporter.export(history)
            run_id = sqlite_store.save(history)
            print(f"\n💾 Historial JSON guardado en {json_path}")
            print(f"🗄️  Historial persistido en {sqlite_store.database_path} (run #{run_id})")

        except Exception as error:
            print(f"\n❌ Error: {error}")
            screenshot_path = await debug_store.save_screenshot(browser.page, "error_final.png")
            print(f"📸 Screenshot guardado en {screenshot_path.name}")
            raise

        finally:
            if pause and not settings.browser.headless:
                input("\nPresiona Enter para cerrar el browser...")


def _run_server(host: str | None, port: int | None) -> None:
    settings = Settings.load()
    app = create_app(settings)
    uvicorn.run(app, host=host or settings.web.host, port=port or settings.web.port)


def run() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command in (None, "fetch"):
        asyncio.run(_run_fetch(pause=not getattr(args, "no_pause", False)))
        return

    if args.command == "serve":
        _run_server(args.host, args.port)
        return

    parser.error(f"Comando no soportado: {args.command}")
