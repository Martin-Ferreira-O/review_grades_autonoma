from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from uac_grades.domain.models import AcademicHistory, AttendanceSnapshot


class SqliteHistoryStore:
    def __init__(self, database_path: Path):
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @property
    def database_path(self) -> Path:
        return self._database_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS history_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_runs_created_at ON history_runs (created_at DESC)"
            )

    def save(self, history: AcademicHistory) -> int:
        payload_json = json.dumps(history.to_dict(), ensure_ascii=False)
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO history_runs (created_at, payload_json) VALUES (?, ?)",
                (history.generated_at, payload_json),
            )
            return int(cursor.lastrowid)

    def load_latest(self) -> AcademicHistory | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM history_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if row is None:
            return None

        return AcademicHistory.from_dict(json.loads(str(row["payload_json"])))

    def runs_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM history_runs").fetchone()
        return int(row["total"] if row else 0)


class SqliteAttendanceStore:
    def __init__(self, database_path: Path):
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @property
    def database_path(self) -> Path:
        return self._database_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS attendance_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    term_code TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_runs_created_at ON attendance_runs (created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_attendance_runs_term_code ON attendance_runs (term_code)"
            )

    def save(self, snapshot: AttendanceSnapshot) -> int:
        payload_json = json.dumps(snapshot.to_dict(), ensure_ascii=False)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO attendance_runs (created_at, term_code, payload_json)
                VALUES (?, ?, ?)
                """,
                (snapshot.generated_at, snapshot.term_code, payload_json),
            )
            return int(cursor.lastrowid)

    def load_latest(self) -> AttendanceSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM attendance_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if row is None:
            return None

        return AttendanceSnapshot.from_dict(json.loads(str(row["payload_json"])))

    def runs_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM attendance_runs").fetchone()
        return int(row["total"] if row else 0)
