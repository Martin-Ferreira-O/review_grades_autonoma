import json
import tempfile
import unittest
from pathlib import Path

import httpx

from uac_grades.domain.models import Credentials
from uac_grades.infrastructure.banner import BannerHttpClient
from uac_grades.infrastructure.config.settings import (
    BrowserSettings,
    ComparisonSettings,
    Settings,
    StorageSettings,
    TargetSelection,
    UrlSettings,
    WebSettings,
)
from uac_grades.infrastructure.persistence import SessionStateStore


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
        comparison=ComparisonSettings(
            base_url="http://127.0.0.1:9100",
            identity_path=temp_dir / "data" / "comparison_identity.json",
            sqlite_path=temp_dir / "data" / "comparison_dashboard.sqlite3",
            invites_path=temp_dir / "data" / "comparison_claim_invites.json",
            host="127.0.0.1",
            port=9100,
        ),
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
                    },
                    {
                        "name": "CASTGC",
                        "value": "ticket123",
                        "domain": "eisoci.uautonoma.cl",
                        "path": "/cas",
                    },
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )
    return SessionStateStore(path)


class BannerHttpClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_probe_grades_session_returns_false_when_storage_state_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            client = BannerHttpClient(settings, SessionStateStore(settings.storage.storage_state_path))

            self.assertFalse(await client.probe_grades_session())

    async def test_probe_grades_session_returns_true_for_authenticated_grades_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)

            def handler(request: httpx.Request) -> httpx.Response:
                html = "<html><body><input id=\"term\" /><div id=\"studentGradesContainer\"></div></body></html>"
                return httpx.Response(200, text=html, request=request)

            client = BannerHttpClient(settings, store, transport=httpx.MockTransport(handler))

            self.assertTrue(await client.probe_grades_session())

    async def test_probe_grades_session_returns_false_after_redirect_to_login(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)

            def handler(request: httpx.Request) -> httpx.Response:
                if request.url.host == "autoserviciooci.uautonoma.cl":
                    return httpx.Response(
                        302,
                        headers={"location": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"},
                        request=request,
                    )

                return httpx.Response(200, text="<html><body>Sign in</body></html>", request=request)

            client = BannerHttpClient(settings, store, transport=httpx.MockTransport(handler))

            self.assertFalse(await client.probe_grades_session())

    async def test_get_json_uses_relative_paths_and_loaded_cookies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)

            def handler(request: httpx.Request) -> httpx.Response:
                self.assertEqual(request.url.path, "/StudentSelfService/studentGrades/term")
                self.assertEqual(request.url.params["page"], "1")
                self.assertIn("JSESSIONID=abc123", request.headers.get("cookie", ""))
                return httpx.Response(200, json={"ok": True}, request=request)

            client = BannerHttpClient(settings, store, transport=httpx.MockTransport(handler))
            payload = await client.get_json("/StudentSelfService/studentGrades/term", params={"page": 1})

            self.assertEqual(payload, {"ok": True})


if __name__ == "__main__":
    unittest.main()
