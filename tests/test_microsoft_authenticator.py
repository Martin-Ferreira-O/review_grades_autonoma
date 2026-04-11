import tempfile
import unittest
from pathlib import Path

from uac_grades.domain.models import Credentials
from uac_grades.infrastructure.auth import MicrosoftAuthenticator, TotpCodeProvider
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


class _FakeHttpClient:
    def __init__(self, probe_results: list[bool]):
        self._probe_results = list(probe_results)
        self.calls = 0

    async def probe_grades_session(self) -> bool:
        self.calls += 1
        if not self._probe_results:
            raise AssertionError(
                "probe_grades_session se llamó más veces de lo esperado"
            )
        return self._probe_results.pop(0)


class _FakeTotpProvider(TotpCodeProvider):
    def __init__(self):
        pass

    def current_code(self) -> str:
        return "123456"


class _RecordingAuthenticator(MicrosoftAuthenticator):
    def __init__(self, *, fail_renewal: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.renew_calls = 0
        self.fail_renewal = fail_renewal

    async def _renew_session_with_browser(self) -> None:
        self.renew_calls += 1
        if self.fail_renewal:
            raise RuntimeError("renewal failed")


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
        ),
    )


class MicrosoftAuthenticatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_session_skips_browser_when_http_session_is_valid(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            auth = _RecordingAuthenticator(
                settings=settings,
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                session_store=SessionStateStore(settings.storage.storage_state_path),
                totp_provider=_FakeTotpProvider(),
                http_client=_FakeHttpClient([True]),
            )

            await auth.ensure_session()

            self.assertEqual(auth.renew_calls, 0)

    async def test_ensure_session_renews_when_http_session_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            http_client = _FakeHttpClient([False, True])
            auth = _RecordingAuthenticator(
                settings=settings,
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                session_store=SessionStateStore(settings.storage.storage_state_path),
                totp_provider=_FakeTotpProvider(),
                http_client=http_client,
            )

            await auth.ensure_session()

            self.assertEqual(auth.renew_calls, 1)
            self.assertEqual(http_client.calls, 2)

    async def test_ensure_session_fails_when_http_validation_still_fails_after_renewal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _settings(Path(temp_dir))
            auth = _RecordingAuthenticator(
                settings=settings,
                debug_store=DebugArtifactStore(settings.storage.output_dir),
                session_store=SessionStateStore(settings.storage.storage_state_path),
                totp_provider=_FakeTotpProvider(),
                http_client=_FakeHttpClient([False, False]),
            )

            with self.assertRaisesRegex(RuntimeError, "validar la sesión HTTP"):
                await auth.ensure_session()

            self.assertEqual(auth.renew_calls, 1)


if __name__ == "__main__":
    unittest.main()
