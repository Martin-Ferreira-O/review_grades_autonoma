import tempfile
import sqlite3
import unittest
from pathlib import Path

from uac_grades.domain import ComparisonAssessmentPayload, ComparisonCoursePayload, ComparisonSyncPayload
from uac_grades.infrastructure.persistence.comparison_sqlite_store import ComparisonSqliteStore


class ComparisonSqliteStoreTests(unittest.TestCase):
    def test_claim_requires_matching_preassigned_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ComparisonSqliteStore(Path(temp_dir) / "comparison.sqlite3")
            store.sync_claim_invites({"Martin A.": "invite-123"})

            issued_token = store.claim_identity(display_name="Martin A.", claim_code="invite-123")

        self.assertTrue(issued_token)

    def test_revoked_invite_cannot_be_claimed_after_resync(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ComparisonSqliteStore(Path(temp_dir) / "comparison.sqlite3")
            store.sync_claim_invites({"Martin A.": "invite-123"})

            store.sync_claim_invites({})

            with self.assertRaises(PermissionError):
                store.claim_identity(display_name="Martin A.", claim_code="invite-123")

    def test_second_claim_attempt_returns_permission_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ComparisonSqliteStore(Path(temp_dir) / "comparison.sqlite3")
            store.sync_claim_invites({"Martin A.": "invite-123"})

            store.claim_identity(display_name="Martin A.", claim_code="invite-123")

            with self.assertRaises(PermissionError):
                store.claim_identity(display_name="Martin A.", claim_code="invite-123")

    def test_wrong_token_cannot_replace_other_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ComparisonSqliteStore(Path(temp_dir) / "comparison.sqlite3")
            store.sync_claim_invites({"Martin A.": "invite-123"})
            issued_token = store.claim_identity(display_name="Martin A.", claim_code="invite-123")

            payload = ComparisonSyncPayload(
                participant_name="Martin A.",
                claim_code=None,
                sync_token=issued_token,
                courses=[
                    ComparisonCoursePayload(
                        canonical_course_key="MAT101",
                        course_code="MAT101",
                        course_title="Calculo I",
                        term_code="202510",
                        term_label="Primer Semestre - 2025",
                        section="1",
                        status="closed",
                        current_grade=5.4,
                        final_grade=5.4,
                        comparison_grade=5.4,
                        assessments=[
                            ComparisonAssessmentPayload(
                                assessment_name="Solemne 1",
                                canonical_assessment_key="solemne-1",
                                weight=30.0,
                                grade=5.0,
                                grade_text="5.0",
                                must_pass=False,
                                order_index=1,
                            )
                        ],
                    )
                ],
            )
            store.replace_participant_snapshot(payload)

            with self.assertRaises(PermissionError):
                store.replace_participant_snapshot(
                    ComparisonSyncPayload(
                        participant_name="Martin A.",
                        claim_code=None,
                        sync_token="wrong-token",
                        courses=payload.courses,
                    )
                )

    def test_resync_replaces_previous_attempts_and_assessments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "comparison.sqlite3"
            store = ComparisonSqliteStore(database_path)
            store.sync_claim_invites({"Martin A.": "invite-123"})
            issued_token = store.claim_identity(display_name="Martin A.", claim_code="invite-123")

            store.replace_participant_snapshot(
                ComparisonSyncPayload(
                    participant_name="Martin A.",
                    claim_code=None,
                    sync_token=issued_token,
                    courses=[
                        ComparisonCoursePayload(
                            canonical_course_key="MAT101",
                            course_code="MAT101",
                            course_title="Calculo I",
                            term_code="202510",
                            term_label="Primer Semestre - 2025",
                            section="1",
                            status="closed",
                            current_grade=5.4,
                            final_grade=5.4,
                            comparison_grade=5.4,
                            assessments=[
                                ComparisonAssessmentPayload(
                                    assessment_name="Solemne 1",
                                    canonical_assessment_key="solemne-1",
                                    weight=30.0,
                                    grade=5.0,
                                    grade_text="5.0",
                                    must_pass=False,
                                    order_index=1,
                                ),
                                ComparisonAssessmentPayload(
                                    assessment_name="Solemne 2",
                                    canonical_assessment_key="solemne-2",
                                    weight=30.0,
                                    grade=6.0,
                                    grade_text="6.0",
                                    must_pass=False,
                                    order_index=2,
                                ),
                            ],
                        ),
                        ComparisonCoursePayload(
                            canonical_course_key="PHY101",
                            course_code="PHY101",
                            course_title="Fisica I",
                            term_code="202510",
                            term_label="Primer Semestre - 2025",
                            section="2",
                            status="closed",
                            current_grade=4.8,
                            final_grade=4.8,
                            comparison_grade=4.8,
                            assessments=[],
                        ),
                    ],
                )
            )

            store.replace_participant_snapshot(
                ComparisonSyncPayload(
                    participant_name="Martin A.",
                    claim_code=None,
                    sync_token=issued_token,
                    courses=[
                        ComparisonCoursePayload(
                            canonical_course_key="MAT101",
                            course_code="MAT101",
                            course_title="Calculo I",
                            term_code="202510",
                            term_label="Primer Semestre - 2025",
                            section="1",
                            status="closed",
                            current_grade=5.7,
                            final_grade=5.7,
                            comparison_grade=5.7,
                            assessments=[
                                ComparisonAssessmentPayload(
                                    assessment_name="Examen",
                                    canonical_assessment_key="exam",
                                    weight=40.0,
                                    grade=5.7,
                                    grade_text="5.7",
                                    must_pass=True,
                                    order_index=3,
                                )
                            ],
                        )
                    ],
                )
            )

            with sqlite3.connect(database_path) as connection:
                attempts_total = connection.execute(
                    "SELECT COUNT(*) FROM participant_course_attempts"
                ).fetchone()[0]
                assessments_total = connection.execute(
                    "SELECT COUNT(*) FROM participant_assessments"
                ).fetchone()[0]
                assessment_names = connection.execute(
                    "SELECT assessment_name FROM participant_assessments ORDER BY assessment_name"
                ).fetchall()

        self.assertEqual(attempts_total, 1)
        self.assertEqual(assessments_total, 1)
        self.assertEqual([row[0] for row in assessment_names], ["Examen"])


if __name__ == "__main__":
    unittest.main()
