from typing import Protocol

from uac_grades.domain.models import GradeSnapshot


class GradeSnapshotPort(Protocol):
    async def fetch_grade_snapshot(self) -> GradeSnapshot:
        """Return the current grade snapshot from the source system."""
