import json
import tempfile
import unittest
from pathlib import Path

import httpx

from uac_grades.domain.models import Credentials
from uac_grades.infrastructure.banner import BannerGateway, BannerHttpClient
from uac_grades.infrastructure.config.settings import (
    BrowserSettings,
    ComparisonSettings,
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
        comparison=ComparisonSettings(
            base_url="http://127.0.0.1:9100",
            identity_path=temp_dir / "data" / "comparison_identity.json",
            sqlite_path=temp_dir / "data" / "comparison_dashboard.sqlite3",
            invites_path=temp_dir / "data" / "comparison_claim_invites.json",
            host="127.0.0.1",
            port=9100,
        ),
    )


def _write_storage_state(path: Path, *, cookie_value: str = "abc123") -> SessionStateStore:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "JSESSIONID",
                        "value": cookie_value,
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


class BannerGatewayCoursesTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_courses_uses_http_contract_and_returns_data_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)
            courses_fixture = _load_fixture("courses")

            def handler(request: httpx.Request) -> httpx.Response:
                self.assertEqual(request.method, courses_fixture["request"]["method"])
                self.assertEqual(request.url.path, courses_fixture["request"]["path"])
                self.assertEqual(dict(request.url.params), courses_fixture["request"]["query"])
                self.assertEqual(request.headers["accept"], courses_fixture["request"]["headers"]["accept"])
                self.assertEqual(
                    request.headers["x-requested-with"],
                    courses_fixture["request"]["headers"]["x-requested-with"],
                )
                return httpx.Response(200, json=courses_fixture["response"]["body"], request=request)

            http_client = BannerHttpClient(settings, store, transport=httpx.MockTransport(handler))
            gateway = BannerGateway(
                settings=settings,
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                http_client=http_client,
            )

            courses = await gateway._fetch_courses("202610", "PR")

            self.assertEqual(courses, courses_fixture["response"]["body"]["data"])


if __name__ == "__main__":
    unittest.main()
