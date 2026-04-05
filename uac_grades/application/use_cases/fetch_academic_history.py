from uac_grades.application.ports import AcademicHistoryPort, AuthPort
from uac_grades.domain.models import AcademicHistory


def _sort_snapshots(snapshots):
    return sorted(snapshots, key=lambda snapshot: (snapshot.term.code, snapshot.level.code))


def merge_academic_history(previous_history: AcademicHistory, refreshed_history: AcademicHistory) -> AcademicHistory:
    if not refreshed_history.snapshots:
        return previous_history

    refreshed_term_codes = {snapshot.term.code for snapshot in refreshed_history.snapshots}
    kept_snapshots = [
        snapshot
        for snapshot in previous_history.snapshots
        if snapshot.term.code not in refreshed_term_codes
    ]
    return AcademicHistory(
        snapshots=_sort_snapshots([*kept_snapshots, *refreshed_history.snapshots]),
        generated_at=refreshed_history.generated_at,
    )


class FetchAcademicHistoryUseCase:
    def __init__(self, auth: AuthPort, grades: AcademicHistoryPort):
        self._auth = auth
        self._grades = grades

    async def execute(
        self,
        *,
        previous_history: AcademicHistory | None = None,
        full_refresh: bool = False,
    ) -> AcademicHistory:
        await self._auth.ensure_session()
        if full_refresh or previous_history is None:
            history = await self._grades.fetch_academic_history()
        else:
            refreshed_history = await self._grades.fetch_current_term_history()
            history = merge_academic_history(previous_history, refreshed_history)
        await self._auth.persist_session()
        return history
