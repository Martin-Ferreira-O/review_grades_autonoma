from __future__ import annotations

import argparse
import asyncio

import uvicorn

from uac_grades.application.use_cases import FetchAcademicHistoryUseCase
from uac_grades.infrastructure.auth import MicrosoftAuthenticator, TotpCodeProvider
from uac_grades.infrastructure.banner import BannerGateway, BannerHttpClient
from uac_grades.infrastructure.banner.contract_capture import BannerHttpContractCapture
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
    parser = argparse.ArgumentParser(
        description="UA grades: extraccion y dashboard local"
    )
    subparsers = parser.add_subparsers(dest="command")

    fetch_parser = subparsers.add_parser(
        "fetch", help="Extrae el historial desde Banner"
    )
    fetch_parser.add_argument(
        "--full",
        action="store_true",
        help="Recarga todos los semestres en lugar de solo el actual",
    )

    serve_parser = subparsers.add_parser("serve", help="Inicia el dashboard web local")
    serve_parser.add_argument("--host", default=None, help="Host para el servidor web")
    serve_parser.add_argument(
        "--port", type=int, default=None, help="Puerto para el servidor web"
    )

    return parser


async def _run_fetch(*, full_refresh: bool) -> None:
    settings = Settings.load()
    debug_store = DebugArtifactStore(settings.storage.output_dir)
    exporter = JsonHistoryExporter(settings.storage.output_dir)
    sqlite_store = SqliteHistoryStore(settings.storage.sqlite_path)
    presenter = ConsoleHistoryPresenter()
    session_store = SessionStateStore(settings.storage.storage_state_path)
    contract_capture = (
        BannerHttpContractCapture(debug_store)
        if settings.browser.capture_banner_contract
        else None
    )
    http_client = BannerHttpClient(
        settings, session_store, contract_capture=contract_capture
    )

    authenticator = MicrosoftAuthenticator(
        settings=settings,
        debug_store=debug_store,
        session_store=session_store,
        totp_provider=TotpCodeProvider(settings.credentials.totp_secret),
        http_client=http_client,
    )
    gateway = BannerGateway(
        settings=settings, debug_store=debug_store, http_client=http_client
    )
    use_case = FetchAcademicHistoryUseCase(auth=authenticator, grades=gateway)
    previous_history = None if full_refresh else sqlite_store.load_latest()

    if previous_history is None:
        print("📚 Modo completo: se recargará todo el historial académico")
    else:
        print("♻️  Modo incremental: se actualizará solo el periodo actual")

    try:
        history = await use_case.execute(
            previous_history=previous_history, full_refresh=full_refresh
        )
        presenter.present(history)

        json_path = exporter.export(history)
        run_id = sqlite_store.save(history)
        print(f"\n💾 Historial JSON guardado en {json_path}")
        print(
            f"🗄️  Historial persistido en {sqlite_store.database_path} (run #{run_id})"
        )

    except Exception as error:
        print(f"\n❌ Error: {error}")
        raise
    finally:
        if contract_capture is not None:
            summary_path = await contract_capture.stop()
            print(f"🧾 Contrato Banner capturado en {summary_path}")


def _run_server(host: str | None, port: int | None) -> None:
    settings = Settings.load()
    app = create_app(settings)
    uvicorn.run(app, host=host or settings.web.host, port=port or settings.web.port)


def run() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command in (None, "fetch"):
        asyncio.run(_run_fetch(full_refresh=getattr(args, "full", False)))
        return

    if args.command == "serve":
        _run_server(args.host, args.port)
        return

    parser.error(f"Comando no soportado: {args.command}")
