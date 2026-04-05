import json
import tempfile
import unittest
from pathlib import Path

import httpx

from uac_grades.infrastructure.persistence import SessionStateStore


class SessionStateStoreTests(unittest.TestCase):
    def test_load_returns_storage_state_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "storage_state.json"
            payload = {
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
            path.write_text(json.dumps(payload), encoding="utf-8")

            store = SessionStateStore(path)

            self.assertEqual(store.load(), payload)

    def test_load_httpx_cookies_preserves_domain_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "storage_state.json"
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

            store = SessionStateStore(path)
            cookies = store.load_httpx_cookies()
            cookie_map = {(cookie.name, cookie.domain, cookie.path): cookie.value for cookie in cookies.jar}

            self.assertEqual(
                cookie_map[("JSESSIONID", "autoserviciooci.uautonoma.cl", "/StudentSelfService")],
                "abc123",
            )
            self.assertEqual(
                cookie_map[("CASTGC", "eisoci.uautonoma.cl", "/cas")],
                "ticket123",
            )

    def test_load_raises_clear_error_when_state_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "storage_state.json"
            store = SessionStateStore(path)

            with self.assertRaisesRegex(RuntimeError, "No existe estado de sesion"):
                store.load()

    def test_load_raises_clear_error_when_state_is_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "storage_state.json"
            path.write_text("{not-json}", encoding="utf-8")
            store = SessionStateStore(path)

            with self.assertRaisesRegex(RuntimeError, "no es JSON valido"):
                store.load()

    def test_save_httpx_cookies_updates_storage_state_with_rotated_cookie_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "storage_state.json"
            path.write_text(
                json.dumps(
                    {
                        "cookies": [
                            {
                                "name": "JSESSIONID",
                                "value": "old-cookie",
                                "domain": "autoserviciooci.uautonoma.cl",
                                "path": "/StudentSelfService",
                                "httpOnly": True,
                            }
                        ],
                        "origins": [],
                    }
                ),
                encoding="utf-8",
            )
            store = SessionStateStore(path)
            cookies = httpx.Cookies()
            cookies.set(
                "JSESSIONID",
                "new-cookie",
                domain="autoserviciooci.uautonoma.cl",
                path="/StudentSelfService",
            )

            store.save_httpx_cookies(cookies)

            payload = store.load()
            self.assertEqual(payload["cookies"][0]["value"], "new-cookie")
            self.assertTrue(payload["cookies"][0]["httpOnly"])


if __name__ == "__main__":
    unittest.main()
