from uac_grades.application.use_cases import FetchGradeSnapshotUseCase
from uac_grades.infrastructure.auth import MicrosoftAuthenticator, TotpCodeProvider
from uac_grades.infrastructure.banner import BannerGateway
from uac_grades.infrastructure.browser import PlaywrightBrowserSession
from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence import DebugArtifactStore, JsonSnapshotExporter, SessionStateStore
from uac_grades.infrastructure.presenters import ConsoleSnapshotPresenter


async def run() -> None:
    settings = Settings.load()
    debug_store = DebugArtifactStore(settings.storage.output_dir)
    exporter = JsonSnapshotExporter(settings.storage.output_dir)
    presenter = ConsoleSnapshotPresenter()

    async with PlaywrightBrowserSession(settings) as browser:
        authenticator = MicrosoftAuthenticator(
            settings=settings,
            browser=browser,
            debug_store=debug_store,
            session_store=SessionStateStore(settings.storage.storage_state_path),
            totp_provider=TotpCodeProvider(settings.credentials.totp_secret),
        )
        gateway = BannerGateway(settings=settings, browser=browser, debug_store=debug_store)
        use_case = FetchGradeSnapshotUseCase(auth=authenticator, grades=gateway)

        try:
            snapshot = await use_case.execute()
            presenter.present(snapshot)

            if snapshot.courses:
                path = exporter.export(snapshot)
                print(f"\n💾 Notas guardadas en {path.name}")

        except Exception as error:
            print(f"\n❌ Error: {error}")
            screenshot_path = await debug_store.save_screenshot(browser.page, "error_final.png")
            print(f"📸 Screenshot guardado en {screenshot_path.name}")
            raise

        finally:
            input("\nPresiona Enter para cerrar el browser...")
