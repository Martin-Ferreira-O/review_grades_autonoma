import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from uac_grades.infrastructure.config import Settings
from uac_grades.interfaces.cli import runner
from uac_grades.interfaces.cli.runner import _build_parser


class ComparisonSettingsTests(unittest.TestCase):
    def test_load_defaults_comparison_base_url_to_hosted_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dotenv_path = root / ".env"
            dotenv_path.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.load(dotenv_path, require_credentials=False)

        self.assertEqual(settings.credentials.username, "")
        self.assertEqual(settings.credentials.password, "")
        self.assertEqual(settings.credentials.totp_secret, "")
        self.assertEqual(
            settings.comparison.base_url, "https://serve-comparison.fly.dev"
        )

    def test_load_reads_client_side_comparison_settings_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dotenv_path = root / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "UA_USUARIO=test@cloud.uautonoma.cl",
                        "UA_CONTRASENA=secret",
                        "UA_TOTP_SECRET=totp-secret",
                        "UA_COMPARISON_BASE_URL=https://serve-comparison.fly.dev",
                        f"UA_COMPARISON_IDENTITY_PATH={root / 'data' / 'comparison_identity.json'}",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.load(dotenv_path)

        self.assertEqual(
            settings.comparison.base_url, "https://serve-comparison.fly.dev"
        )
        self.assertEqual(
            settings.comparison.identity_path.name, "comparison_identity.json"
        )
        self.assertFalse(hasattr(settings.comparison, "sqlite_path"))
        self.assertFalse(hasattr(settings.comparison, "invites_path"))
        self.assertFalse(hasattr(settings.comparison, "host"))
        self.assertFalse(hasattr(settings.comparison, "port"))

    def test_parser_does_not_support_serve_comparison(self) -> None:
        parser = _build_parser()

        with self.assertRaises(SystemExit) as error:
            parser.parse_args(["serve-comparison"])

        self.assertEqual(error.exception.code, 2)

    def test_main_without_command_starts_server(self) -> None:
        with patch("sys.argv", ["main.py"]), patch.object(
            runner, "_run_server"
        ) as run_server:
            runner.run()

        run_server.assert_called_once_with(host=None, port=None)

    def test_api_exports_only_local_app(self) -> None:
        import uac_grades.interfaces.api as api

        self.assertTrue(hasattr(api, "create_app"))
        self.assertFalse(hasattr(api, "create_comparison_app"))
