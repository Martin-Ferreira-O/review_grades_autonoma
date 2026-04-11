# UA Grades

<p align="center">
  <strong>Historial academico desde Banner + SQLite + dashboard local</strong>
</p>

<p align="center">
  Herramienta personal para extraer tus notas desde Banner, consolidarlas en SQLite y visualizarlas en una web local con metricas, promedios y alertas por semestre.
</p>

<p align="center">
  <img src="./image.png" alt="Dashboard UA" width="100%" />
</p>

## Resumen

`UA Grades` automatiza el acceso a Banner y construye un historial academico local a partir de tus datos en Banner.

Con ese historial puedes:

- guardar un respaldo en JSON
- persistir la informacion en SQLite
- levantar un dashboard web local
- ver promedios por semestre
- detectar cursos fuertes, cursos mas debiles y periodos sin nota

## Caracteristicas

- Extraccion HTTP-first con `httpx`
- Login con Microsoft + `TOTP`
- Renovacion de sesion con `Playwright` solo cuando hace falta
- Historial consolidado de todos los semestres disponibles
- Persistencia local en `SQLite`
- Exportacion a `JSON`
- Dashboard local con metricas y graficos
- Soporte para ejecucion local o con `Docker`

## Flujo

1. `fetch`: intenta reutilizar la sesion guardada en `.auth/storage_state.json`.
2. Si ya existe historial local, actualiza solo el periodo actual y conserva intactos los semestres anteriores.
3. Si no existe historial local, o si usas `fetch --full`, recorre todos los periodos y rehace el historial completo.
4. Si la sesion expiro, abre `Playwright`, renueva login Microsoft + TOTP, actualiza la sesion y continua por HTTP.
5. Guarda el resultado en `JSON` y `SQLite`.
6. `serve`: levanta la web local leyendo desde SQLite.

## Comandos

```bash
python main.py fetch
python main.py fetch --full
python main.py serve
```

`fetch` actualiza solo el semestre actual cuando ya existe un historial guardado.

Usa `python main.py fetch --full` si quieres recargar todos los semestres manualmente.

Si la sesion HTTP sigue vigente, `fetch` no deberia abrir ningun browser.

El dashboard queda disponible en `http://127.0.0.1:8000`.

`python main.py serve` inicia el dashboard local que lee tu historial desde `SQLite`, muestra el resumen academico y ofrece dos entradas al flujo de comparacion: `Ir a dashboard de comparacion` y `Subir mis datos / Sync`.

## Uso local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py fetch
python main.py fetch --full
python main.py serve
```

## Uso con Docker

```bash
cp .env.example .env
docker compose build
docker compose run --rm app python main.py fetch
docker compose up
```

El dashboard queda disponible en `http://localhost:8000`.

Para `fetch` dentro de Docker conviene usar `UA_HEADLESS=true`. Esa opcion solo afecta el browser de renovacion. Si Microsoft cambia la pantalla de 2FA y necesitas intervenir manualmente, ejecuta `python main.py fetch` fuera del contenedor.

## Variables principales

Copia `.env.example` a `.env` y completa tus credenciales.

- `UA_USUARIO`
- `UA_CONTRASENA`
- `UA_TOTP_SECRET`
- `UA_MANTENER_SESION`
- `UA_HEADLESS`
- `UA_OUTPUT_DIR`
- `UA_SQLITE_PATH`
- `UA_WEB_HOST`
- `UA_WEB_PORT`
- `UA_COMPARISON_BASE_URL`
- `UA_COMPARISON_IDENTITY_PATH`
- `UA_CAPTURE_BANNER_CONTRACT`

## Comparacion y sync

Para usar comparacion solo necesitas levantar la app local:

```bash
python main.py serve
```

Configuracion relevante en `.env`:

- `UA_COMPARISON_BASE_URL`: URL del tablero remoto a donde apunta el dashboard local.
- `UA_COMPARISON_IDENTITY_PATH`: archivo local donde se guarda `display_name`, `sync_token` y fecha del ultimo sync.

El dashboard compartido ahora vive como un servicio hospedado en un repositorio y deployment separados. Este repositorio solo mantiene el cliente local que sincroniza tu snapshot y abre ese tablero externo.

Flujo de primera vinculacion:

1. La persona abre `Subir mis datos / Sync` desde el dashboard local.
2. En el primer envio completa `display_name` y `claim_code`.
3. El servicio remoto valida ese claim, crea o reemplaza el snapshot del participante y devuelve un `sync_token`.
4. La app local guarda ese `sync_token` en `UA_COMPARISON_IDENTITY_PATH` junto al nombre mostrado.
5. Los siguientes sync reutilizan ese token automaticamente, por lo que ya no vuelven a pedir `claim_code` y nadie mas puede actualizar los datos de ese participante sin el token correcto.

Consecuencias practicas del flujo:

- El primer enlace solo funciona si `display_name` coincide exactamente con el nombre visible preasignado para ese `claim_code`.
- Un `claim_code` invalido en el primer enlace es rechazado por el servidor remoto.
- Un `sync_token` incorrecto tambien es rechazado cuando alguien intenta actualizar un participante ya vinculado.
- Cuando ya existe vinculacion, el dashboard local construye el link al tablero remoto con `?participant=<display_name>` para resaltar tu posicion al abrir la vista compartida.

## Sesion y autenticacion

- `.auth/storage_state.json` es la sesion reutilizable principal del flujo HTTP.
- `.auth/ua_profile/` conserva el perfil persistente de Chromium usado solo cuando hay que renovar la sesion.
- `UA_HEADLESS` y `UA_SLOW_MO` solo afectan ese flujo de renovacion.
- `UA_MANTENER_SESION=true` responde automaticamente la pantalla de Microsoft "Mantener sesion iniciada".

## Captura de contrato Banner

Si necesitas refrescar fixtures o diagnosticar cambios de Banner, puedes capturar el contrato HTTP real con:

```bash
UA_CAPTURE_BANNER_CONTRACT=true python main.py fetch --full
```

Eso genera artifacts en `data/banner_contract/`, incluyendo `summary.json` y una captura por endpoint observado.

## Archivos generados

- `data/ua_grades.sqlite3`: base SQLite local
- `data/historial_notas_*.json`: exportaciones JSON
- `data/debug_notas_inicial.html` y `data/debug_notas_final.html`: HTMLs de debug del fetch HTTP
- `data/banner_contract/`: capturas del contrato HTTP cuando `UA_CAPTURE_BANNER_CONTRACT=true`
- `.auth/storage_state.json`: sesion HTTP reutilizable
- `.auth/ua_profile/`: perfil persistente del navegador usado para renovacion

## Como obtener `UA_TOTP_SECRET`

1. Inicia sesion en `https://myaccount.microsoft.com/uac/device-management`.
2. Activar la verificacion de 2 pasos con una aplicacion de Authenticator.
3. Escanea el codigo QR con la aplicacion `Ente Auth`.
4. Obtiene el secreto TOTP desde los detalles del metodo y agregalo a `.env` junto al correo y la contrasena.

## Notas

- El proyecto esta pensado para uso personal y local.
- La web no scrapea en cada refresh; consume el ultimo historial guardado en SQLite.
- Si quieres actualizar tus datos, vuelve a ejecutar `python main.py fetch`.
- Los screenshots del browser solo se generan en problemas de login o renovacion, no en el fetch HTTP normal.
