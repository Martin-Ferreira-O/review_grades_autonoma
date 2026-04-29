from __future__ import annotations

import argparse
import asyncio

import uvicorn

from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence import SqliteHistoryStore
from uac_grades.infrastructure.presenters import ConsoleHistoryPresenter
from uac_grades.interfaces.api import create_app
from uac_grades.interfaces.banner_fetch import fetch_banner_history


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
    sqlite_store = SqliteHistoryStore(settings.storage.sqlite_path)
    presenter = ConsoleHistoryPresenter()
    stored_history = sqlite_store.load_latest()

    if full_refresh or stored_history is None:
        print("📚 Modo completo: se recargará todo el historial académico")
    else:
        print("♻️  Modo incremental: se actualizará solo el periodo actual")

    try:
        result = await fetch_banner_history(
            settings, history_store=sqlite_store, full_refresh=full_refresh
        )
        presenter.present(result.history)

        if result.first_fetch:
            print("\n✅ Notas cargadas.")
        elif result.new_grades:
            print(f"\n✅ {len(result.new_grades)} nota(s) nueva(s) o actualizada(s):")
            for grade in result.new_grades:
                print(f"  - {grade.course_title}: {grade.evaluation} = {grade.grade}")
        else:
            print("\n✅ No hubo notas nuevas.")

        print(f"\n💾 Historial JSON guardado en {result.json_path}")
        print(
            f"🗄️  Historial persistido en {result.database_path} (run #{result.run_id})"
        )

    except Exception as error:
        print(f"\n❌ Error: {error}")
        raise


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
