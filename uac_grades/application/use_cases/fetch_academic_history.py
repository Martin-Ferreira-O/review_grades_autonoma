from uac_grades.application.ports import AcademicHistoryPort, AuthPort
from uac_grades.domain.models import AcademicHistory


class FetchAcademicHistoryUseCase:
    def __init__(self, auth: AuthPort, grades: AcademicHistoryPort):
        self._auth = auth
        self._grades = grades

    async def execute(self) -> AcademicHistory:
        await self._auth.ensure_session()
        history = await self._grades.fetch_academic_history()
        await self._auth.persist_session()
        return history
