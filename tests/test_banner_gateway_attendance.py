import json
import tempfile
import unittest
from pathlib import Path

import httpx

from uac_grades.domain.models import Credentials
from uac_grades.infrastructure.banner import BannerGateway, BannerHttpClient
from uac_grades.infrastructure.banner.mappers import build_attendance_snapshot
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
        credentials=Credentials(
            username="user@example.com", password="secret", totp_secret="totp"
        ),
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
            term_code="202610",
            term_description="Primer Semestre - 2026",
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
                    }
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )
    return SessionStateStore(path)


class BannerGatewayAttendanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_attendance_sections_uses_http_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)
            fixture = _load_fixture("attendance_sections")

            def handler(request: httpx.Request) -> httpx.Response:
                self.assertEqual(request.method, fixture["request"]["method"])
                self.assertEqual(request.url.path, fixture["request"]["path"])
                self.assertEqual(dict(request.url.params), fixture["request"]["query"])
                self.assertEqual(
                    request.headers["x-requested-with"],
                    fixture["request"]["headers"]["x-requested-with"],
                )
                return httpx.Response(
                    200, json=fixture["response"]["body"], request=request
                )

            gateway = BannerGateway(
                settings=settings,
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                http_client=BannerHttpClient(
                    settings, store, transport=httpx.MockTransport(handler)
                ),
            )

            sections = await gateway._fetch_attendance_sections()

            self.assertEqual(sections, fixture["response"]["body"]["data"])

    async def test_fetch_attendance_details_uses_http_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = _settings(temp_path)
            store = _write_storage_state(settings.storage.storage_state_path)
            fixture = _load_fixture("attendance_absence_details")

            def handler(request: httpx.Request) -> httpx.Response:
                self.assertEqual(request.method, fixture["request"]["method"])
                self.assertEqual(request.url.path, fixture["request"]["path"])
                self.assertEqual(dict(request.url.params), fixture["request"]["query"])
                self.assertEqual(
                    request.headers["x-requested-with"],
                    fixture["request"]["headers"]["x-requested-with"],
                )
                return httpx.Response(
                    200, json=fixture["response"]["body"], request=request
                )

            gateway = BannerGateway(
                settings=settings,
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                http_client=BannerHttpClient(
                    settings, store, transport=httpx.MockTransport(handler)
                ),
            )

            details = await gateway._fetch_attendance_details("292484")

            self.assertEqual(details, fixture["response"]["body"])

    def test_attendance_mapper_normalizes_and_filters_current_term(self) -> None:
        sections_fixture = _load_fixture("attendance_sections")
        details_fixture = _load_fixture("attendance_absence_details")
        sections_raw = [
            (section, details_fixture["response"]["body"])
            for section in sections_fixture["response"]["body"]["data"]
        ]

        snapshot = build_attendance_snapshot("202610", sections_raw)

        self.assertEqual(snapshot.term_code, "202610")
        self.assertEqual(len(snapshot.sections), 2)
        first = snapshot.sections[0]
        self.assertEqual(first.section_title, "Ingeniería de Software")
        self.assertEqual(first.subject_description, "INGENIERÍA CIVIL INFORMÁTICA")
        self.assertEqual(first.course_code, "CINF 00701")
        self.assertEqual(first.section_meeting_id, "292484")
        self.assertEqual(first.missed, 2)
        self.assertEqual(first.percentage, 75.0)
        self.assertEqual(first.total_sessions, 8)
        self.assertEqual(first.sessions_attended, 6)
        self.assertEqual(len(first.absences), 2)


if __name__ == "__main__":
    unittest.main()
