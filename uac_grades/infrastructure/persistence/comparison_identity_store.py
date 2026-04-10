from __future__ import annotations

import json
from pathlib import Path

from uac_grades.domain import ComparisonIdentity


class ComparisonIdentityStore:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> ComparisonIdentity | None:
        if not self._path.exists():
            return None

        payload = json.loads(self._path.read_text(encoding="utf-8"))
        return ComparisonIdentity(
            display_name=str(payload["display_name"]),
            sync_token=str(payload["sync_token"]),
            last_synced_at=payload.get("last_synced_at"),
        )

    def save(self, *, display_name: str, sync_token: str, last_synced_at: str | None = None) -> None:
        self._path.write_text(
            json.dumps(
                {
                    "display_name": display_name,
                    "sync_token": sync_token,
                    "last_synced_at": last_synced_at,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
