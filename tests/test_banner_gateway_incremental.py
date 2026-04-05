import json
import unittest
from pathlib import Path
from typing import cast

import httpx

from uac_grades.domain.models import Credentials
from uac_grades.infrastructure.banner import BannerGateway, BannerHttpClient
from uac_grades.infrastructure.config.settings import (
    BrowserSettings,
    Settings,
    StorageSettings,
    TargetSelection,
    UrlSettings,
    WebSettings,
)
from uac_grades.infrastructure.persistence import DebugArtifactStore


class _FakeClientContext:
    def __init__(self):
        self._client = type("Client", (), {"cookies": httpx.Cookies()})()

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _FakeHttpClient:
    def create_client(self):
        return _FakeClientContext()


class _RecordingGateway(BannerGateway):
    def __init__(self, settings: Settings):
        super().__init__(
            settings=settings,
            debug_store=DebugArtifactStore(settings.storage.output_dir),
            http_client=cast(BannerHttpClient, _FakeHttpClient()),
        )
        self.requested_terms: list[str] = []

    async def _open_grades_page(self, client) -> None:
        return None

    async def _save_final_debug_artifacts(self, client) -> None:
        return None

    async def _fetch_terms(self, client=None) -> list[dict]:
        return [
            {"code": "202520", "description": "Segundo Semestre - 2025"},
            {"code": "202610", "description": "Primer Semestre - 2026"},
            {"code": "202410", "description": "Primer Semestre - 2024"},
        ]

    async def _fetch_levels(self, term_code: str, client=None) -> list[dict]:
        self.requested_terms.append(term_code)
        return [{"code": "PR", "description": "Pregrado"}]

    async def _fetch_courses(self, term_code: str, level_code: str, client=None) -> list:
        self.requested_terms.append(term_code)
        if term_code == "202610":
            return []
        return [
            {
                "id": f"COURSE-{term_code}",
                "courseReferenceNumber": "12345",
                "subjectCode": "TEST",
                "courseNumber": "0101",
                "courseTitle": f"Curso {term_code}",
                "termCode": term_code,
                "termDescription": f"Term {term_code}",
                "levelDescription": "Pregrado",
                "hasComponent": "N",
                "gradeDetailDisplayInd": "N",
            }
        ]

    async def _enrich_courses_with_components(self, courses: list, client=None) -> list:
        return courses


def _settings() -> Settings:
    root = Path("/tmp/ua_grades_incremental_test")
    return Settings(
        dotenv_path=root / ".env",
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
            output_dir=root / "data",
            auth_dir=root / ".auth",
            user_data_dir=root / ".auth" / "ua_profile",
            storage_state_path=root / ".auth" / "storage_state.json",
            sqlite_path=root / "data" / "ua_grades.sqlite3",
        ),
        web=WebSettings(host="127.0.0.1", port=8000),
    )


class BannerGatewayIncrementalTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_current_term_history_skips_future_empty_term_and_uses_latest_with_courses(self) -> None:
        gateway = _RecordingGateway(_settings())

        history = await gateway.fetch_current_term_history()

        self.assertEqual([snapshot.term.code for snapshot in history.snapshots], ["202520"])
        self.assertEqual(gateway.requested_terms, ["202610", "202610", "202520", "202520"])


if __name__ == "__main__":
    unittest.main()
