from typing import Protocol

from uac_grades.domain.models import AcademicHistory, GradeSnapshot


class GradeSnapshotPort(Protocol):
    async def fetch_grade_snapshot(self) -> GradeSnapshot:
        """Return the current grade snapshot from the source system."""
        raise NotImplementedError


class AcademicHistoryPort(Protocol):
    async def fetch_academic_history(self) -> AcademicHistory:
        """Return the complete academic history from the source system."""
        raise NotImplementedError

    async def fetch_current_term_history(self) -> AcademicHistory:
        """Return only the latest/current term history from the source system."""
        raise NotImplementedError
