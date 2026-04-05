from __future__ import annotations

from typing import Callable

from playwright.async_api import Page

from uac_grades.infrastructure.banner.http_client import BannerHttpClient
from uac_grades.infrastructure.browser.playwright_context import PlaywrightBrowserSession
from uac_grades.infrastructure.config.settings import Settings
from uac_grades.infrastructure.persistence.debug_store import DebugArtifactStore
from uac_grades.infrastructure.persistence.session_store import SessionStateStore

from .totp import TotpCodeProvider


class MicrosoftAuthenticator:
    def __init__(
        self,
        settings: Settings,
        debug_store: DebugArtifactStore,
        session_store: SessionStateStore,
        totp_provider: TotpCodeProvider,
        http_client: BannerHttpClient | None = None,
        browser_factory: Callable[[Settings], PlaywrightBrowserSession] | None = None,
    ):
        self._settings = settings
        self._debug_store = debug_store
        self._session_store = session_store
        self._totp_provider = totp_provider
        self._http_client = http_client or BannerHttpClient(settings, session_store)
        self._browser_factory = browser_factory or PlaywrightBrowserSession
        self._session_updated = False

    async def ensure_session(self) -> None:
        print("🔐 Comprobando sesión reutilizable...")
        self._session_updated = False

        if await self._http_client.probe_grades_session():
            print("  ✓ Sesión reutilizada desde storage_state.json")
            return

        print("  → La sesión guardada no está disponible. Iniciando renovación...")
        await self._renew_session_with_browser()

        if not await self._http_client.probe_grades_session():
            raise RuntimeError("No fue posible validar la sesión HTTP tras la renovación")

        self._session_updated = True
        print("  ✓ Sesión renovada y lista para próximas ejecuciones")

    async def persist_session(self) -> None:
        if not self._session_updated:
            return

        print(f"💾 Estado de sesión actualizado en {self._session_store.path}")
        self._session_updated = False

    async def _renew_session_with_browser(self) -> None:
        browser = self._browser_factory(self._settings)
        await browser.start()

        try:
            page = browser.page
            await page.goto(self._settings.urls.grades, wait_until="networkidle", timeout=30000)

            if await self._grades_page_available(page):
                print("  ✓ Sesión recuperada desde el perfil persistente del browser")
                await self._session_store.save(browser.context)
                return

            print("  → La sesión guardada no está disponible. Iniciando login...")
            await self._login(page)
            await page.goto(self._settings.urls.grades, wait_until="networkidle", timeout=30000)

            if not await self._grades_page_available(page, timeout=10000):
                raise RuntimeError("No fue posible abrir la página de notas tras iniciar sesión")

            await self._session_store.save(browser.context)
        finally:
            await browser.close()

    async def _wait_visible(self, page: Page, selector: str, timeout: int = 10000) -> bool:
        try:
            await page.locator(selector).first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    async def _grades_page_available(self, page: Page, timeout: int = 5000) -> bool:
        if "microsoftonline.com" in page.url.lower():
            return False

        try:
            await page.locator("#term").first.wait_for(state="attached", timeout=timeout)
            return True
        except Exception:
            return False

    async def _login(self, page: Page) -> None:
        print("🌐 Iniciando flujo SSO de la UA...")
        await page.goto(self._settings.urls.sso, wait_until="networkidle", timeout=30000)
        print(f"  → URL actual: {page.url}")

        if "microsoftonline.com" not in page.url:
            print("  ⏳ Esperando redirección a Microsoft...")
            try:
                await page.wait_for_url("**/microsoftonline.com/**", timeout=15000)
            except Exception:
                print(f"  ⚠️  No redirigió a Microsoft. URL actual: {page.url}")
                path = await self._debug_store.save_screenshot(page, "debug_antes_microsoft.png")
                print(f"      Screenshot guardado en {path.name}")

        print(f"  → En Microsoft: {page.url}")

        if await self._wait_visible(page, 'input[type="email"], input[name="loginfmt"]'):
            await page.fill('input[type="email"], input[name="loginfmt"]', self._settings.credentials.username)
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1500)
            print("  ✓ Email ingresado")
        else:
            print("  → Campo de email no encontrado (puede que ya haya sesión activa)")

        if await self._wait_visible(page, 'input[type="password"], input[name="passwd"]'):
            await page.fill('input[type="password"], input[name="passwd"]', self._settings.credentials.password)
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1500)
            print("  ✓ Contraseña ingresada")

        if await self._wait_visible(page, 'a[data-value="PhoneAppOTP"]', timeout=5000):
            print("  → Pantalla de selección de método 2FA — eligiendo código TOTP...")
            await page.click('a[data-value="PhoneAppOTP"]')
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)

        totp_selectors = [
            'input[name="otc"]',
            '#idTxtBx_SAOTCC_OTC',
            'input[placeholder*="código"]',
            'input[placeholder*="code"]',
            'input[aria-label*="código"]',
            'input[autocomplete="one-time-code"]',
        ]

        totp_found = False
        for selector in totp_selectors:
            if await self._wait_visible(page, selector, timeout=5000):
                code = self._totp_provider.current_code()
                print(f"  🔑 Código TOTP generado: {code}")
                await page.fill(selector, code)
                await page.keyboard.press("Enter")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                print("  ✓ Código TOTP ingresado")
                totp_found = True
                break

        if not totp_found:
            print("  ⚠️  Campo TOTP no encontrado automáticamente.")
            print(
                "      "
                f"Tienes {self._settings.browser.wait_2fa_seconds}s para completar el 2FA manualmente en el browser..."
            )
            path = await self._debug_store.save_screenshot(page, "debug_2fa.png")
            print(f"      Screenshot guardado en {path.name}")
            try:
                await page.wait_for_url("**/uautonoma.cl/**", timeout=self._settings.browser.wait_2fa_seconds * 1000)
            except Exception:
                print("  ⚠️  Tiempo agotado esperando el 2FA")

        await self._respond_keep_session(page)
        await page.wait_for_timeout(2000)
        print(f"\n✅ Login completado — URL actual: {page.url}\n")

    async def _respond_keep_session(self, page: Page) -> None:
        selector_yes = "#idSIButton9"
        selector_no = "#idBtn_Back"

        try:
            await page.locator(f"{selector_yes}, {selector_no}").first.wait_for(state="visible", timeout=5000)
        except Exception:
            return

        if self._settings.browser.keep_session and await self._wait_visible(page, selector_yes, timeout=1500):
            await page.click(selector_yes)
            await page.wait_for_load_state("networkidle")
            print("  ✓ 'Mantener sesión' → Sí")
            return

        if await self._wait_visible(page, selector_no, timeout=1500):
            await page.click(selector_no)
            await page.wait_for_load_state("networkidle")
            print("  ✓ 'Mantener sesión' → No")
