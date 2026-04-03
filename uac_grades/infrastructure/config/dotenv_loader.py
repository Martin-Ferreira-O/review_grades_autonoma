import os
from pathlib import Path


def load_dotenv_file(path: Path) -> None:
    """Carga un archivo .env simple sin dependencias externas."""

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key.startswith("export "):
            key = key[len("export "):].strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if key:
            os.environ.setdefault(key, value)


def require_env(name: str, dotenv_path: Path) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta la variable de entorno {name}. Revisa {dotenv_path}.")
    return value
