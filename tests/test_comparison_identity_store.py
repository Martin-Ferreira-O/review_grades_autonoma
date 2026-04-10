import tempfile
import unittest
from pathlib import Path

from uac_grades.infrastructure.persistence.comparison_identity_store import ComparisonIdentityStore


class ComparisonIdentityStoreTests(unittest.TestCase):
    def test_save_and_load_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ComparisonIdentityStore(Path(temp_dir) / "comparison_identity.json")

            self.assertIsNone(store.load())

            store.save(
                display_name="Martin A.",
                sync_token="token-123",
                last_synced_at="2026-04-09T18:00:00+00:00",
            )
            identity = store.load()

        self.assertIsNotNone(identity)
        self.assertEqual(identity.display_name, "Martin A.")
        self.assertEqual(identity.sync_token, "token-123")
        self.assertEqual(identity.last_synced_at, "2026-04-09T18:00:00+00:00")
