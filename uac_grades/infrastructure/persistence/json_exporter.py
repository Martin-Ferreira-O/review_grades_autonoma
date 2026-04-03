from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from uac_grades.domain.models import GradeSnapshot


class JsonSnapshotExporter:
    def __init__(self, output_dir: Path):
        self._output_dir = output_dir

    def export(self, snapshot: GradeSnapshot) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self._output_dir / f"notas_{timestamp}.json"
        path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path
