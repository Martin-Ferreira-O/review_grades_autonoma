from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from uac_grades.domain.models import AcademicHistory, AttendanceSnapshot
from uac_grades.infrastructure.auth import MicrosoftAuthenticator, TotpCodeProvider
from uac_grades.infrastructure.banner import BannerGateway, BannerHttpClient
from uac_grades.infrastructure.banner.contract_capture import BannerHttpContractCapture
from uac_grades.infrastructure.config import Settings
from uac_grades.infrastructure.persistence import (
    DebugArtifactStore,
    SessionStateStore,
    SqliteAttendanceStore,
    SqliteHistoryStore,
)


class HistoryStore(Protocol):
    database_path: Path

    def load_latest(self) -> AcademicHistory | None:
        ...


class AttendanceStore(Protocol):
    database_path: Path

    def load_latest(self) -> AttendanceSnapshot | None:
        ...

    def save(self, snapshot: AttendanceSnapshot) -> int:
        ...


@dataclass(frozen=True)
class AttendanceFetchResult:
    snapshot: AttendanceSnapshot
    first_fetch: bool
    run_id: int
    database_path: Path


async def fetch_banner_attendance(
    settings: Settings,
    *,
    history_store: HistoryStore | None = None,
    attendance_store: AttendanceStore | None = None,
) -> AttendanceFetchResult:
    debug_store = DebugArtifactStore(settings.storage.output_dir)
    history_store = history_store or SqliteHistoryStore(settings.storage.sqlite_path)
    attendance_store = attendance_store or SqliteAttendanceStore(settings.storage.sqlite_path)
    session_store = SessionStateStore(settings.storage.storage_state_path)
    contract_capture = (
        BannerHttpContractCapture(debug_store)
        if settings.browser.capture_banner_contract
        else None
    )
    http_client = BannerHttpClient(
        settings, session_store, contract_capture=contract_capture
    )

    authenticator = MicrosoftAuthenticator(
        settings=settings,
        debug_store=debug_store,
        session_store=session_store,
        totp_provider=TotpCodeProvider(settings.credentials.totp_secret),
        http_client=http_client,
    )
    gateway = BannerGateway(
        settings=settings, debug_store=debug_store, http_client=http_client
    )
    history = history_store.load_latest()
    if history is None or not history.snapshots:
        raise RuntimeError("Primero debes cargar notas para identificar el semestre actual")

    latest_snapshot = history.snapshots[-1]
    stored_snapshot = attendance_store.load_latest()

    try:
        await authenticator.ensure_session()
        snapshot = await gateway.fetch_attendance_snapshot(latest_snapshot.term.code)
        await authenticator.persist_session()
        run_id = attendance_store.save(snapshot)
        return AttendanceFetchResult(
            snapshot=snapshot,
            first_fetch=stored_snapshot is None,
            run_id=run_id,
            database_path=attendance_store.database_path,
        )
    finally:
        if contract_capture is not None:
            await contract_capture.stop()
