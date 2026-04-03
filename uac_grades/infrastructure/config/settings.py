from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from uac_grades.domain.models import Credentials

from .dotenv_loader import load_dotenv_file, require_env


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no"}


@dataclass(frozen=True)
class UrlSettings:
    sso: str
    grades: str


@dataclass(frozen=True)
class BrowserSettings:
    keep_session: bool
    wait_2fa_seconds: int
    headless: bool
    slow_mo: int
    viewport_width: int
    viewport_height: int
    locale: str
    timezone_id: str
    page_size: int


@dataclass(frozen=True)
class TargetSelection:
    term_code: str
    term_description: str
    level_code: str
    level_description: str


@dataclass(frozen=True)
class StorageSettings:
    output_dir: Path
    auth_dir: Path
    user_data_dir: Path
    storage_state_path: Path


@dataclass(frozen=True)
class Settings:
    dotenv_path: Path
    credentials: Credentials
    urls: UrlSettings
    browser: BrowserSettings
    target: TargetSelection
    storage: StorageSettings

    @classmethod
    def load(cls, dotenv_path: Path | None = None) -> "Settings":
        dotenv_path = dotenv_path or Path(".env")
        load_dotenv_file(dotenv_path)

        auth_dir = Path(os.getenv("UAC_AUTH_DIR", ".auth"))
        output_dir = Path(os.getenv("UAC_OUTPUT_DIR", "."))

        return cls(
            dotenv_path=dotenv_path,
            credentials=Credentials(
                username=require_env("UAC_USUARIO", dotenv_path),
                password=require_env("UAC_CONTRASENA", dotenv_path),
                totp_secret=require_env("UAC_TOTP_SECRET", dotenv_path),
            ),
            urls=UrlSettings(
                sso=os.getenv("UAC_URL_SSO", "https://autoservicio8oci.uautonoma.cl/ssomanager/c/SSB"),
                grades=os.getenv("UAC_URL_NOTAS", "https://autoserviciooci.uautonoma.cl/StudentSelfService/ssb/studentGrades"),
            ),
            browser=BrowserSettings(
                keep_session=_bool_env("UAC_MANTENER_SESION", True),
                wait_2fa_seconds=int(os.getenv("UAC_ESPERA_2FA", "60")),
                headless=_bool_env("UAC_HEADLESS", False),
                slow_mo=int(os.getenv("UAC_SLOW_MO", "400")),
                viewport_width=int(os.getenv("UAC_VIEWPORT_WIDTH", "1280")),
                viewport_height=int(os.getenv("UAC_VIEWPORT_HEIGHT", "900")),
                locale=os.getenv("UAC_LOCALE", "es-CL"),
                timezone_id=os.getenv("UAC_TIMEZONE", "America/Santiago"),
                page_size=int(os.getenv("UAC_PAGE_SIZE", "200")),
            ),
            target=TargetSelection(
                term_code=os.getenv("UAC_TARGET_TERM_CODE", "202510").strip(),
                term_description=os.getenv("UAC_TARGET_TERM_DESCRIPTION", "Primer Semestre - 2025").strip(),
                level_code=os.getenv("UAC_TARGET_LEVEL_CODE", "PR").strip(),
                level_description=os.getenv("UAC_TARGET_LEVEL_DESCRIPTION", "Pregrado").strip(),
            ),
            storage=StorageSettings(
                output_dir=output_dir,
                auth_dir=auth_dir,
                user_data_dir=auth_dir / "uac_profile",
                storage_state_path=auth_dir / "storage_state.json",
            ),
        )
