from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from uac_grades.domain.models import AcademicHistory, GradeSnapshot


def _write_payload(output_dir: Path, prefix: str, payload: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{prefix}_{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class JsonSnapshotExporter:
    def __init__(self, output_dir: Path):
        self._output_dir = output_dir

    def export(self, snapshot: GradeSnapshot) -> Path:
        return _write_payload(self._output_dir, "notas", snapshot.to_dict())


class JsonHistoryExporter:
    def __init__(self, output_dir: Path):
        self._output_dir = output_dir

    def export(self, history: AcademicHistory) -> Path:
        return _write_payload(self._output_dir, "historial_notas", history.to_dict())
