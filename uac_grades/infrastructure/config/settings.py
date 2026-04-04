from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from uac_grades.domain.models import Credentials

from .dotenv_loader import load_dotenv_file


def _bool_value(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no"}


def _env(name: str, legacy_name: str, default: str) -> str:
    return os.getenv(name, os.getenv(legacy_name, default))


def _require_env(name: str, legacy_name: str, dotenv_path: Path) -> str:
    value = os.getenv(name, os.getenv(legacy_name, "")).strip()
    if not value:
        raise RuntimeError(f"Falta la variable de entorno {name}. Revisa {dotenv_path}.")
    return value


def _migrate_legacy_path(target: Path, legacy: Path) -> Path:
    if target.exists() or not legacy.exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(target))
    return target


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
    sqlite_path: Path


@dataclass(frozen=True)
class WebSettings:
    host: str
    port: int


@dataclass(frozen=True)
class Settings:
    dotenv_path: Path
    credentials: Credentials
    urls: UrlSettings
    browser: BrowserSettings
    target: TargetSelection
    storage: StorageSettings
    web: WebSettings

    @classmethod
    def load(cls, dotenv_path: Path | None = None) -> "Settings":
        dotenv_path = dotenv_path or Path(".env")
        load_dotenv_file(dotenv_path)

        auth_dir = Path(_env("UA_AUTH_DIR", "UAC_AUTH_DIR", ".auth"))
        output_dir = Path(_env("UA_OUTPUT_DIR", "UAC_OUTPUT_DIR", "data"))
        user_data_dir = _migrate_legacy_path(auth_dir / "ua_profile", auth_dir / "uac_profile")
        sqlite_path = _migrate_legacy_path(
            Path(_env("UA_SQLITE_PATH", "UAC_SQLITE_PATH", str(output_dir / "ua_grades.sqlite3"))),
            output_dir / "uac_grades.sqlite3",
        )

        return cls(
            dotenv_path=dotenv_path,
            credentials=Credentials(
                username=_require_env("UA_USUARIO", "UAC_USUARIO", dotenv_path),
                password=_require_env("UA_CONTRASENA", "UAC_CONTRASENA", dotenv_path),
                totp_secret=_require_env("UA_TOTP_SECRET", "UAC_TOTP_SECRET", dotenv_path),
            ),
            urls=UrlSettings(
                sso=_env("UA_URL_SSO", "UAC_URL_SSO", "https://autoservicio8oci.uautonoma.cl/ssomanager/c/SSB"),
                grades=_env(
                    "UA_URL_NOTAS",
                    "UAC_URL_NOTAS",
                    "https://autoserviciooci.uautonoma.cl/StudentSelfService/ssb/studentGrades",
                ),
            ),
            browser=BrowserSettings(
                keep_session=_bool_value(_env("UA_MANTENER_SESION", "UAC_MANTENER_SESION", "true"), True),
                wait_2fa_seconds=int(_env("UA_ESPERA_2FA", "UAC_ESPERA_2FA", "60")),
                headless=_bool_value(_env("UA_HEADLESS", "UAC_HEADLESS", "false"), False),
                slow_mo=int(_env("UA_SLOW_MO", "UAC_SLOW_MO", "400")),
                viewport_width=int(_env("UA_VIEWPORT_WIDTH", "UAC_VIEWPORT_WIDTH", "1280")),
                viewport_height=int(_env("UA_VIEWPORT_HEIGHT", "UAC_VIEWPORT_HEIGHT", "900")),
                locale=_env("UA_LOCALE", "UAC_LOCALE", "es-CL"),
                timezone_id=_env("UA_TIMEZONE", "UAC_TIMEZONE", "America/Santiago"),
                page_size=int(_env("UA_PAGE_SIZE", "UAC_PAGE_SIZE", "200")),
            ),
            target=TargetSelection(
                term_code=_env("UA_TARGET_TERM_CODE", "UAC_TARGET_TERM_CODE", "202510").strip(),
                term_description=_env(
                    "UA_TARGET_TERM_DESCRIPTION",
                    "UAC_TARGET_TERM_DESCRIPTION",
                    "Primer Semestre - 2025",
                ).strip(),
                level_code=_env("UA_TARGET_LEVEL_CODE", "UAC_TARGET_LEVEL_CODE", "PR").strip(),
                level_description=_env("UA_TARGET_LEVEL_DESCRIPTION", "UAC_TARGET_LEVEL_DESCRIPTION", "Pregrado").strip(),
            ),
            storage=StorageSettings(
                output_dir=output_dir,
                auth_dir=auth_dir,
                user_data_dir=user_data_dir,
                storage_state_path=auth_dir / "storage_state.json",
                sqlite_path=sqlite_path,
            ),
            web=WebSettings(
                host=_env("UA_WEB_HOST", "UAC_WEB_HOST", "127.0.0.1").strip(),
                port=int(_env("UA_WEB_PORT", "UAC_WEB_PORT", "8000")),
            ),
        )
