import unittest

from uac_grades.application.use_cases.fetch_academic_history import FetchAcademicHistoryUseCase, merge_academic_history
from uac_grades.domain.models import AcademicHistory, AcademicLevel, AcademicTerm, Course, GradeSnapshot


def _snapshot(term_code: str, title: str, *, generated_at: str | None = None) -> GradeSnapshot:
    return GradeSnapshot(
        term=AcademicTerm(code=term_code, description=f"Term {term_code}"),
        level=AcademicLevel(code="PR", description="Pregrado"),
        courses=[
            Course(
                course_id=None,
                nrc=None,
                code=f"COURSE-{term_code}",
                section=None,
                title=title,
                grade=None,
                final_grade=None,
                midterm_grade=None,
                term_description=None,
                level_description=None,
                campus=None,
                study_path=None,
                attempted_hours=None,
                earned_hours=None,
                gpa_hours=None,
                quality_points=None,
                components_available=False,
            )
        ],
    )


class _FakeAuth:
    def __init__(self):
        self.ensure_calls = 0
        self.persist_calls = 0

    async def ensure_session(self) -> None:
        self.ensure_calls += 1

    async def persist_session(self) -> None:
        self.persist_calls += 1


class _FakeGrades:
    def __init__(self, *, full_history: AcademicHistory, current_history: AcademicHistory):
        self.full_history = full_history
        self.current_history = current_history
        self.full_calls = 0
        self.current_calls = 0

    async def fetch_academic_history(self) -> AcademicHistory:
        self.full_calls += 1
        return self.full_history

    async def fetch_current_term_history(self) -> AcademicHistory:
        self.current_calls += 1
        return self.current_history


class MergeAcademicHistoryTests(unittest.TestCase):
    def test_merge_replaces_only_refreshed_term(self) -> None:
        previous = AcademicHistory(
            generated_at="2026-04-01T00:00:00+00:00",
            snapshots=[
                _snapshot("202410", "Old 202410"),
                _snapshot("202510", "Old 202510"),
            ],
        )
        refreshed = AcademicHistory(
            generated_at="2026-04-02T00:00:00+00:00",
            snapshots=[_snapshot("202510", "New 202510")],
        )

        merged = merge_academic_history(previous, refreshed)

        self.assertEqual([snapshot.term.code for snapshot in merged.snapshots], ["202410", "202510"])
        self.assertEqual(merged.snapshots[0].courses[0].title, "Old 202410")
        self.assertEqual(merged.snapshots[1].courses[0].title, "New 202510")
        self.assertEqual(merged.generated_at, "2026-04-02T00:00:00+00:00")

    def test_merge_preserves_previous_history_when_refresh_returns_no_snapshots(self) -> None:
        previous = AcademicHistory(
            generated_at="2026-04-01T00:00:00+00:00",
            snapshots=[_snapshot("202510", "Old 202510")],
        )
        refreshed = AcademicHistory(generated_at="2026-04-02T00:00:00+00:00", snapshots=[])

        merged = merge_academic_history(previous, refreshed)

        self.assertIs(merged, previous)


class FetchAcademicHistoryUseCaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_uses_incremental_refresh_when_previous_history_exists(self) -> None:
        previous = AcademicHistory(
            generated_at="2026-04-01T00:00:00+00:00",
            snapshots=[_snapshot("202410", "Old 202410"), _snapshot("202510", "Old 202510")],
        )
        refreshed = AcademicHistory(
            generated_at="2026-04-02T00:00:00+00:00",
            snapshots=[_snapshot("202510", "New 202510")],
        )
        auth = _FakeAuth()
        grades = _FakeGrades(full_history=AcademicHistory(snapshots=[]), current_history=refreshed)
        use_case = FetchAcademicHistoryUseCase(auth=auth, grades=grades)

        history = await use_case.execute(previous_history=previous, full_refresh=False)

        self.assertEqual(grades.full_calls, 0)
        self.assertEqual(grades.current_calls, 1)
        self.assertEqual([snapshot.courses[0].title for snapshot in history.snapshots], ["Old 202410", "New 202510"])
        self.assertEqual(auth.ensure_calls, 1)
        self.assertEqual(auth.persist_calls, 1)

    async def test_execute_uses_full_refresh_when_requested(self) -> None:
        full_history = AcademicHistory(
            generated_at="2026-04-03T00:00:00+00:00",
            snapshots=[_snapshot("202410", "Full 202410"), _snapshot("202510", "Full 202510")],
        )
        auth = _FakeAuth()
        grades = _FakeGrades(full_history=full_history, current_history=AcademicHistory(snapshots=[]))
        use_case = FetchAcademicHistoryUseCase(auth=auth, grades=grades)

        history = await use_case.execute(previous_history=AcademicHistory(snapshots=[]), full_refresh=True)

        self.assertIs(history, full_history)
        self.assertEqual(grades.full_calls, 1)
        self.assertEqual(grades.current_calls, 0)
