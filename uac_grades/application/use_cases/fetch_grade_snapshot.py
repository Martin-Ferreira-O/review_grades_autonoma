from uac_grades.application.ports import AuthPort, GradeSnapshotPort
from uac_grades.domain.models import GradeSnapshot


class FetchGradeSnapshotUseCase:
    def __init__(self, auth: AuthPort, grades: GradeSnapshotPort):
        self._auth = auth
        self._grades = grades

    async def execute(self) -> GradeSnapshot:
        await self._auth.ensure_session()
        snapshot = await self._grades.fetch_grade_snapshot()
        await self._auth.persist_session()
        return snapshot
