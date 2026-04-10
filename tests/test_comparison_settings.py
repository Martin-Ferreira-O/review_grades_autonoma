import tempfile
import unittest
from pathlib import Path

from uac_grades.infrastructure.config import Settings
from uac_grades.interfaces.cli.runner import _build_parser


class ComparisonSettingsTests(unittest.TestCase):
    def test_load_reads_comparison_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dotenv_path = root / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "UA_USUARIO=test@cloud.uautonoma.cl",
                        "UA_CONTRASENA=secret",
                        "UA_TOTP_SECRET=totp-secret",
                        "UA_COMPARISON_BASE_URL=http://127.0.0.1:9100",
                        f"UA_COMPARISON_IDENTITY_PATH={root / 'data' / 'comparison_identity.json'}",
                        f"UA_COMPARISON_SQLITE_PATH={root / 'data' / 'comparison_dashboard.sqlite3'}",
                        f"UA_COMPARISON_INVITES_PATH={root / 'data' / 'comparison_claim_invites.json'}",
                        "UA_COMPARISON_WEB_HOST=0.0.0.0",
                        "UA_COMPARISON_WEB_PORT=9100",
                    ]
                ),
                encoding="utf-8",
            )

            settings = Settings.load(dotenv_path)

        self.assertEqual(settings.comparison.base_url, "http://127.0.0.1:9100")
        self.assertEqual(settings.comparison.host, "0.0.0.0")
        self.assertEqual(settings.comparison.port, 9100)
        self.assertEqual(settings.comparison.identity_path.name, "comparison_identity.json")
        self.assertEqual(settings.comparison.sqlite_path.name, "comparison_dashboard.sqlite3")
        self.assertEqual(settings.comparison.invites_path.name, "comparison_claim_invites.json")

    def test_parser_supports_serve_comparison(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["serve-comparison", "--host", "0.0.0.0", "--port", "9100"])

        self.assertEqual(args.command, "serve-comparison")
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.port, 9100)
