import tempfile
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


if __name__ == "__main__":
    unittest.main()
