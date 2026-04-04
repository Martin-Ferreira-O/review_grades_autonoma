# UA Grades

Herramienta personal para extraer el historial academico desde Banner, persistirlo en SQLite y visualizarlo en un dashboard web local.

## Modos disponibles

- `python main.py fetch`: inicia sesion, recorre todos los periodos disponibles y guarda JSON + SQLite.
- `python main.py serve`: levanta el dashboard local en `http://127.0.0.1:8000`.

## Variables principales

Parte de `.env.example` y copia a `.env`.

- `UA_USUARIO`
- `UA_CONTRASENA`
- `UA_TOTP_SECRET`
- `UA_OUTPUT_DIR`
- `UA_SQLITE_PATH`
- `UA_WEB_HOST`
- `UA_WEB_PORT`

## Uso local

1. `python -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python main.py fetch`
5. `python main.py serve`

## Uso con Docker

1. Copia `.env.example` a `.env`
2. `docker compose build`
3. `docker compose run --rm app python main.py fetch`
4. `docker compose up`

El dashboard queda disponible en `http://localhost:8000`.

Para `fetch` dentro de Docker conviene usar `UA_HEADLESS=true`. Si Microsoft cambia la pantalla de 2FA y necesitas intervenir manualmente, ejecuta `python main.py fetch` fuera del contenedor.
