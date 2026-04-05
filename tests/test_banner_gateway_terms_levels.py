import json
import tempfile
import unittest
from pathlib import Path
from typing import cast

import httpx

from uac_grades.domain.models import Credentials
from uac_grades.infrastructure.banner import BannerGateway, BannerHttpClient
from uac_grades.infrastructure.browser.playwright_context import PlaywrightBrowserSession
from uac_grades.infrastructure.config.settings import (
    BrowserSettings,
    Settings,
    StorageSettings,
    TargetSelection,
    UrlSettings,
    WebSettings,
)
from uac_grades.infrastructure.persistence import DebugArtifactStore, SessionStateStore


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "banner"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _settings(temp_dir: Path) -> Settings:
    return Settings(
        dotenv_path=temp_dir / ".env",
        credentials=Credentials(username="user@example.com", password="secret", totp_secret="totp"),
        urls=UrlSettings(
            sso="https://autoservicio8oci.uautonoma.cl/ssomanager/c/SSB",
            grades="https://autoserviciooci.uautonoma.cl/StudentSelfService/ssb/studentGrades",
        ),
        browser=BrowserSettings(
            capture_banner_contract=False,
            keep_session=True,
            wait_2fa_seconds=60,
            headless=False,
            slow_mo=0,
            viewport_width=1280,
            viewport_height=900,
            locale="es-CL",
            timezone_id="America/Santiago",
            page_size=200,
        ),
        target=TargetSelection(
            term_code="202510",
            term_description="Primer Semestre - 2025",
            level_code="PR",
            level_description="Pregrado",
        ),
        storage=StorageSettings(
            output_dir=temp_dir / "data",
            auth_dir=temp_dir / ".auth",
            user_data_dir=temp_dir / ".auth" / "ua_profile",
            storage_state_path=temp_dir / ".auth" / "storage_state.json",
            sqlite_path=temp_dir / "data" / "ua_grades.sqlite3",
        ),
        web=WebSettings(host="127.0.0.1", port=8000),
    )


def _write_storage_state(path: Path) -> SessionStateStore:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "JSESSIONID",
                        "value": "abc123",
                        "domain": "autoserviciooci.uautonoma.cl",
                        "path": "/StudentSelfService",
                    }
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )
    return SessionStateStore(path)


class _UnusedBrowser:
    page = None

    def __init__(self, context=None):
        self.context = context


class _FakeBrowserContext:
    def __init__(self, payload: dict):
        self._payload = payload

    async def storage_state(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self._payload), encoding="utf-8")


class BannerGatewayTermsLevelsTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_terms_uses_http_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)
            terms_fixture = _load_fixture("terms")

            def handler(request: httpx.Request) -> httpx.Response:
                self.assertEqual(request.method, terms_fixture["request"]["method"])
                self.assertEqual(request.url.path, terms_fixture["request"]["path"])
                self.assertEqual(dict(request.url.params), terms_fixture["request"]["query"])
                self.assertEqual(request.headers["accept"], terms_fixture["request"]["headers"]["accept"])
                return httpx.Response(200, json=terms_fixture["response"]["body"], request=request)

            http_client = BannerHttpClient(settings, store, transport=httpx.MockTransport(handler))
            gateway = BannerGateway(
                settings=settings,
                browser=cast(PlaywrightBrowserSession, _UnusedBrowser()),
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                http_client=http_client,
            )

            terms = await gateway._fetch_terms()

            self.assertEqual(
                terms,
                [
                    {"code": "202610", "description": "Primer Semestre - 2026"},
                    {"code": "202520", "description": "Segundo Semestre - 2025"},
                    {"code": "202510", "description": "Primer Semestre - 2025"},
                ],
            )

    async def test_fetch_levels_uses_http_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)
            levels_fixture = _load_fixture("levels")

            def handler(request: httpx.Request) -> httpx.Response:
                self.assertEqual(request.method, levels_fixture["request"]["method"])
                self.assertEqual(request.url.path, levels_fixture["request"]["path"])
                self.assertEqual(dict(request.url.params), levels_fixture["request"]["query"])
                self.assertEqual(request.headers["accept"], levels_fixture["request"]["headers"]["accept"])
                return httpx.Response(200, json=levels_fixture["response"]["body"], request=request)

            http_client = BannerHttpClient(settings, store, transport=httpx.MockTransport(handler))
            gateway = BannerGateway(
                settings=settings,
                browser=cast(PlaywrightBrowserSession, _UnusedBrowser()),
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                http_client=http_client,
            )

            levels = await gateway._fetch_levels("202610")

            self.assertEqual(levels, [{"code": "PR", "description": "Pregrado"}])

    async def test_fetch_term_and_level_keeps_target_selection_logic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)
            terms_fixture = _load_fixture("terms")
            levels_fixture = _load_fixture("levels")

            def handler(request: httpx.Request) -> httpx.Response:
                if request.url.path == "/StudentSelfService/studentGrades/term":
                    return httpx.Response(200, json=terms_fixture["response"]["body"], request=request)
                if request.url.path == "/StudentSelfService/studentGrades/level":
                    return httpx.Response(200, json=levels_fixture["response"]["body"], request=request)
                raise AssertionError(f"Unexpected path {request.url.path}")

            http_client = BannerHttpClient(settings, store, transport=httpx.MockTransport(handler))
            gateway = BannerGateway(
                settings=settings,
                browser=cast(PlaywrightBrowserSession, _UnusedBrowser()),
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                http_client=http_client,
            )

            term, level = await gateway._fetch_term_and_level()

            self.assertEqual(term, {"code": "202510", "description": "Primer Semestre - 2025"})
            self.assertEqual(level, {"code": "PR", "description": "Pregrado"})

    async def test_fetch_terms_syncs_storage_state_from_live_browser_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            session_store = SessionStateStore(settings.storage.storage_state_path)
            terms_fixture = _load_fixture("terms")
            browser_context = _FakeBrowserContext(
                {
                    "cookies": [
                        {
                            "name": "JSESSIONID",
                            "value": "fresh-cookie",
                            "domain": "autoserviciooci.uautonoma.cl",
                            "path": "/StudentSelfService",
                        }
                    ],
                    "origins": [],
                }
            )

            def handler(request: httpx.Request) -> httpx.Response:
                self.assertIn("JSESSIONID=fresh-cookie", request.headers.get("cookie", ""))
                return httpx.Response(200, json=terms_fixture["response"]["body"], request=request)

            http_client = BannerHttpClient(settings, session_store, transport=httpx.MockTransport(handler))
            gateway = BannerGateway(
                settings=settings,
                browser=cast(PlaywrightBrowserSession, _UnusedBrowser(context=browser_context)),
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                session_store=session_store,
                http_client=http_client,
            )

            terms = await gateway._fetch_terms()

            self.assertTrue(session_store.exists())
            self.assertEqual(terms[0]["code"], "202610")


if __name__ == "__main__":
    unittest.main()
