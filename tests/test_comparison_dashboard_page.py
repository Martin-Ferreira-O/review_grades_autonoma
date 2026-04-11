import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from uac_grades.infrastructure.config import Settings
from uac_grades.interfaces.api import create_comparison_app


class ComparisonDashboardPageTests(unittest.TestCase):
    def test_dashboard_renders_core_tabs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dotenv_path = root / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "UA_USUARIO=test@cloud.uautonoma.cl",
                        "UA_CONTRASENA=secret",
                        "UA_TOTP_SECRET=totp-secret",
                        f"UA_COMPARISON_SQLITE_PATH={root / 'comparison.sqlite3'}",
                    ]
                ),
                encoding="utf-8",
            )
            settings = Settings.load(dotenv_path)
            client = TestClient(create_comparison_app(settings))

            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ramo", response.text)
        self.assertIn("Semestre", response.text)
        self.assertIn("Historico", response.text)
        self.assertIn("Aun no hay datos sincronizados", response.text)

    def test_dashboard_preserves_active_tab_across_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dotenv_path = root / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "UA_USUARIO=test@cloud.uautonoma.cl",
                        "UA_CONTRASENA=secret",
                        "UA_TOTP_SECRET=totp-secret",
                        f"UA_COMPARISON_SQLITE_PATH={root / 'comparison.sqlite3'}",
                    ]
                ),
                encoding="utf-8",
            )
            settings = Settings.load(dotenv_path)
            client = TestClient(create_comparison_app(settings))

            response = client.get("/", params={"active_tab": "semester"})

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-active-tab="semester"', response.text)
        self.assertIn('id="comparison-tab-semester"', response.text)
        self.assertIn('id="comparison-tab-semester" type="button" role="tab" tabindex="0"', response.text)
        self.assertIn('aria-selected="true">Semestre</button>', response.text)
        self.assertIn('id="comparison-tab-course" type="button" role="tab" tabindex="-1"', response.text)
        self.assertIn('name="active_tab" value="semester"', response.text)


if __name__ == "__main__":
    unittest.main()
