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


if __name__ == "__main__":
    unittest.main()
