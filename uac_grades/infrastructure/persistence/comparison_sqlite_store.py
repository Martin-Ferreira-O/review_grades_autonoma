from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from uac_grades.domain import ComparisonSyncPayload


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ComparisonSqliteStore:
    def __init__(self, database_path: Path):
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_name TEXT NOT NULL UNIQUE,
                    sync_token_hash TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    latest_synced_at TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS claim_invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_name TEXT NOT NULL UNIQUE,
                    claim_code_hash TEXT NOT NULL,
                    claimed_at TEXT,
                    participant_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_id INTEGER NOT NULL,
                    received_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_version TEXT NOT NULL,
                    courses_count INTEGER NOT NULL,
                    assessments_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_course_key TEXT NOT NULL UNIQUE,
                    course_code TEXT NOT NULL,
                    course_title TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS participant_course_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    term_code TEXT NOT NULL,
                    term_label TEXT NOT NULL,
                    section TEXT,
                    status TEXT NOT NULL,
                    current_grade REAL,
                    final_grade REAL,
                    comparison_grade REAL,
                    components_available INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS participant_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_attempt_id INTEGER NOT NULL,
                    canonical_assessment_key TEXT NOT NULL,
                    assessment_name TEXT NOT NULL,
                    weight REAL NOT NULL,
                    grade REAL,
                    grade_text TEXT NOT NULL,
                    must_pass INTEGER NOT NULL,
                    order_index INTEGER NOT NULL
                );
                """
            )

    def sync_claim_invites(self, invites: dict[str, str]) -> None:
        with self._connect() as connection:
            for display_name, claim_code in invites.items():
                connection.execute(
                    """
                    INSERT INTO claim_invites (display_name, claim_code_hash, claimed_at, participant_id)
                    VALUES (?, ?, NULL, NULL)
                    ON CONFLICT(display_name) DO UPDATE SET claim_code_hash = excluded.claim_code_hash
                    """,
                    (display_name, _hash_token(claim_code)),
                )

    def claim_identity(self, *, display_name: str, claim_code: str) -> str:
        sync_token = secrets.token_urlsafe(24)
        claim_code_hash = _hash_token(claim_code)
        sync_token_hash = _hash_token(sync_token)
        with self._connect() as connection:
            invite = connection.execute(
                "SELECT id, claimed_at FROM claim_invites WHERE display_name = ? AND claim_code_hash = ?",
                (display_name, claim_code_hash),
            ).fetchone()
            if invite is None or invite["claimed_at"] is not None:
                raise PermissionError("claim_invite_invalid")
            cursor = connection.execute(
                "INSERT INTO participants (display_name, sync_token_hash, claimed_at) VALUES (?, ?, datetime('now'))",
                (display_name, sync_token_hash),
            )
            connection.execute(
                "UPDATE claim_invites SET claimed_at = datetime('now'), participant_id = ? WHERE id = ?",
                (int(cursor.lastrowid), int(invite["id"])),
            )
        return sync_token

    def _participant_id_for_token(self, *, display_name: str, sync_token: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM participants WHERE display_name = ? AND sync_token_hash = ?",
                (display_name, _hash_token(sync_token)),
            ).fetchone()
        if row is None:
            raise PermissionError("sync_token_invalid")
        return int(row["id"])

    def replace_participant_snapshot(self, payload: ComparisonSyncPayload) -> None:
        if not payload.sync_token:
            raise PermissionError("sync_token_required")

        participant_id = self._participant_id_for_token(
            display_name=payload.participant_name,
            sync_token=payload.sync_token,
        )

        with self._connect() as connection:
            attempt_ids = connection.execute(
                "SELECT id FROM participant_course_attempts WHERE participant_id = ?",
                (participant_id,),
            ).fetchall()
            for attempt_row in attempt_ids:
                connection.execute(
                    "DELETE FROM participant_assessments WHERE course_attempt_id = ?",
                    (int(attempt_row["id"]),),
                )
            connection.execute("DELETE FROM participant_course_attempts WHERE participant_id = ?", (participant_id,))

            assessments_count = 0
            for course in payload.courses:
                connection.execute(
                    "INSERT OR IGNORE INTO courses (canonical_course_key, course_code, course_title) VALUES (?, ?, ?)",
                    (course.canonical_course_key, course.course_code, course.course_title),
                )
                course_row = connection.execute(
                    "SELECT id FROM courses WHERE canonical_course_key = ?",
                    (course.canonical_course_key,),
                ).fetchone()
                attempt_cursor = connection.execute(
                    """
                    INSERT INTO participant_course_attempts (
                        participant_id, course_id, term_code, term_label, section, status, current_grade, final_grade, comparison_grade, components_available
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        participant_id,
                        int(course_row["id"]),
                        course.term_code,
                        course.term_label,
                        course.section,
                        course.status,
                        course.current_grade,
                        course.final_grade,
                        course.comparison_grade,
                        1 if course.assessments else 0,
                    ),
                )
                course_attempt_id = int(attempt_cursor.lastrowid)
                for assessment in course.assessments:
                    assessments_count += 1
                    connection.execute(
                        """
                        INSERT INTO participant_assessments (
                            course_attempt_id, canonical_assessment_key, assessment_name, weight, grade, grade_text, must_pass, order_index
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            course_attempt_id,
                            assessment.canonical_assessment_key,
                            assessment.assessment_name,
                            assessment.weight,
                            assessment.grade,
                            assessment.grade_text,
                            1 if assessment.must_pass else 0,
                            assessment.order_index,
                        ),
                    )

            connection.execute(
                "UPDATE participants SET latest_synced_at = datetime('now') WHERE id = ?",
                (participant_id,),
            )
            connection.execute(
                "INSERT INTO sync_runs (participant_id, received_at, status, payload_version, courses_count, assessments_count) VALUES (?, datetime('now'), 'ok', 'v1', ?, ?)",
                (participant_id, len(payload.courses), assessments_count),
            )
