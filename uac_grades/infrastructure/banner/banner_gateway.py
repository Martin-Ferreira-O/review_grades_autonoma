from __future__ import annotations

import httpx

from uac_grades.domain.models import AcademicHistory, GradeSnapshot
from uac_grades.infrastructure.config.settings import Settings
from uac_grades.infrastructure.persistence.debug_store import DebugArtifactStore
from uac_grades.infrastructure.persistence.session_store import SessionStateStore

from .http_client import BannerHttpClient
from .mappers import (
    banner_flag_to_bool,
    build_academic_history,
    build_course_label,
    build_snapshot,
    course_has_component_details,
    list_valid_options,
    pick_target_option,
)


class BannerGateway:
    _TERM_ENDPOINT = "/StudentSelfService/studentGrades/term"
    _LEVEL_ENDPOINT = "/StudentSelfService/studentGrades/level"
    _COURSES_ENDPOINT = "/StudentSelfService/studentGrades/courses"
    _COMPONENTS_ENDPOINT = "/StudentSelfService/componentDetails/componentDetails"
    _SUBCOMPONENTS_ENDPOINT = "/StudentSelfService/componentDetails/subComponentDetails"
    _JSON_ACCEPT = "application/json, text/javascript, */*; q=0.01"
    _HTML_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    def __init__(
        self,
        settings: Settings,
        debug_store: DebugArtifactStore,
        session_store: SessionStateStore | None = None,
        http_client: BannerHttpClient | None = None,
    ):
        self._settings = settings
        self._debug_store = debug_store
        self._session_store = session_store or SessionStateStore(settings.storage.storage_state_path)
        self._http_client = http_client or BannerHttpClient(
            settings,
            self._session_store,
        )

    async def fetch_grade_snapshot(self) -> GradeSnapshot:
        async with self._http_client.create_client() as client:
            try:
                await self._open_grades_page(client)
                term_raw, level_raw = await self._fetch_term_and_level(client)
                print("\n  → Semestre seleccionado automáticamente:")
                print(f"     Periodo: {term_raw['code']} | {term_raw['description']}")
                print(f"     Nivel:   {level_raw['code']} | {level_raw['description']}")

                courses_raw = await self._fetch_courses(term_raw["code"], level_raw["code"], client)
                courses_raw = await self._enrich_courses_with_components(courses_raw, client)

                await self._save_final_debug_artifacts(client)

                return build_snapshot(term_raw, level_raw, courses_raw)
            finally:
                self._persist_http_session(client)

    async def fetch_academic_history(self) -> AcademicHistory:
        async with self._http_client.create_client() as client:
            try:
                await self._open_grades_page(client)
                terms = await self._fetch_terms(client)
                snapshots: list[GradeSnapshot] = []

                for term_index, term in enumerate(terms, 1):
                    snapshots.extend(await self._fetch_term_snapshots(term, client, index=term_index, total=len(terms)))

                await self._save_final_debug_artifacts(client)

                return build_academic_history(snapshots)
            finally:
                self._persist_http_session(client)

    async def fetch_current_term_history(self) -> AcademicHistory:
        async with self._http_client.create_client() as client:
            try:
                await self._open_grades_page(client)
                terms = self._sorted_terms_desc(await self._fetch_terms(client))

                for index, term in enumerate(terms, 1):
                    snapshots = await self._fetch_term_snapshots(term, client, index=index, total=len(terms), current_only=True)
                    if snapshots:
                        await self._save_final_debug_artifacts(client)
                        return build_academic_history(snapshots)

                await self._save_final_debug_artifacts(client)
                return build_academic_history([])
            finally:
                self._persist_http_session(client)

    async def _open_grades_page(self, client: httpx.AsyncClient) -> None:
        print("📋 Navegando a calificaciones...")
        response = await self._fetch_grades_page_response(client)
        print(f"  → URL: {response.url}")

        self._debug_store.write_text("debug_notas_inicial.html", response.text)
        print("  💾 debug_notas_inicial.html guardado")

    async def _save_final_debug_artifacts(self, client: httpx.AsyncClient) -> None:
        response = await self._fetch_grades_page_response(client)
        self._debug_store.write_text("debug_notas_final.html", response.text)
        print("  💾 debug_notas_final.html guardado")

    async def _fetch_grades_page_response(self, client: httpx.AsyncClient) -> httpx.Response:
        return await self._http_client.request(
            "GET",
            self._settings.urls.grades,
            headers=self._html_headers(),
            client=client,
        )

    async def _fetch_term_and_level(self, client: httpx.AsyncClient | None = None) -> tuple[dict, dict]:
        terms = await self._fetch_terms(client)
        term = pick_target_option(
            terms,
            "periodo",
            target_code=self._settings.target.term_code,
            target_description=self._settings.target.term_description,
        )

        levels = await self._fetch_levels(term["code"], client)
        level = pick_target_option(
            levels,
            "nivel",
            target_code=self._settings.target.level_code,
            target_description=self._settings.target.level_description,
            fallback_first=True,
        )

        return term, level

    async def _fetch_term_snapshots(
        self,
        term: dict,
        client: httpx.AsyncClient,
        *,
        index: int,
        total: int,
        current_only: bool = False,
    ) -> list[GradeSnapshot]:
        prefix = "Periodo actual" if current_only else "Periodo"
        print(f"\n📚 {prefix} [{index}/{total}] {term['code']} | {term['description']}")
        levels = await self._fetch_levels(term["code"], client)
        snapshots: list[GradeSnapshot] = []

        for level in levels:
            print(f"  → Nivel {level['code']} | {level['description']}")
            courses_raw = await self._fetch_courses(term["code"], level["code"], client)

            if not courses_raw:
                print("    · Sin cursos para este nivel")
                continue

            courses_raw = await self._enrich_courses_with_components(courses_raw, client)
            snapshots.append(build_snapshot(term, level, courses_raw))

        return snapshots

    def _sorted_terms_desc(self, terms: list[dict]) -> list[dict]:
        numeric_terms = [term for term in terms if str(term.get("code", "")).isdigit()]
        if len(numeric_terms) == len(terms):
            return sorted(terms, key=lambda term: str(term.get("code", "")), reverse=True)
        return sorted(terms, key=lambda term: str(term.get("code", "")), reverse=True)

    def _persist_http_session(self, client: httpx.AsyncClient) -> None:
        self._session_store.save_httpx_cookies(client.cookies)

    async def _fetch_terms(self, client: httpx.AsyncClient | None = None) -> list[dict]:
        terms = await self._http_client.get_json(
            self._TERM_ENDPOINT,
            params={"page": 1, "max": 200},
            headers=self._json_headers(),
            client=client,
        )
        return list_valid_options(terms)

    async def _fetch_levels(self, term_code: str, client: httpx.AsyncClient | None = None) -> list[dict]:
        levels = await self._http_client.get_json(
            self._LEVEL_ENDPOINT,
            params={"term": term_code, "page": 1, "max": 50},
            headers=self._json_headers(),
            client=client,
        )
        return list_valid_options(levels)

    def _html_headers(self) -> dict[str, str]:
        return {
            "Accept": self._HTML_ACCEPT,
            "Referer": self._settings.urls.grades,
        }

    def _json_headers(self) -> dict[str, str]:
        return {
            "Accept": self._JSON_ACCEPT,
            "Referer": self._settings.urls.grades,
        }

    def _ajax_headers(self) -> dict[str, str]:
        return {
            **self._json_headers(),
            "X-Requested-With": "XMLHttpRequest",
        }

    async def _fetch_courses(
        self,
        term_code: str,
        level_code: str,
        client: httpx.AsyncClient | None = None,
    ) -> list:
        payload = await self._http_client.get_json(
            self._COURSES_ENDPOINT,
            params={
                "termCode": term_code,
                "levelCode": level_code,
                "filterText": "",
                "pageOffset": 0,
                "pageMaxSize": self._settings.browser.page_size,
                "sortColumn": -1,
                "sortDirection": -1,
            },
            headers=self._ajax_headers(),
            client=client,
        )

        if not isinstance(payload, dict):
            raise RuntimeError("Banner no devolvio un payload valido para cursos")
        if payload.get("success") is not True:
            raise RuntimeError(f"Banner rechazo la consulta de cursos: {payload}")

        courses = payload.get("data", [])
        if not isinstance(courses, list):
            raise RuntimeError("Banner devolvio cursos con un formato invalido")

        return courses

    async def _fetch_course_components(self, course: dict, client: httpx.AsyncClient | None = None) -> list:
        payload = await self._http_client.get_json(
            self._COMPONENTS_ENDPOINT,
            params={
                "selectedTerm": course.get("termCode"),
                "selectedCrn": course.get("courseReferenceNumber"),
                "filterText": "",
                "pageOffset": 0,
                "pageMaxSize": self._settings.browser.page_size,
                "sortColumn": "name",
                "sortDirection": "asc",
            },
            headers=self._ajax_headers(),
            client=client,
        )

        if not isinstance(payload, dict):
            raise RuntimeError("Banner no devolvio un payload valido para componentes")
        if payload.get("success") is not True:
            raise RuntimeError(f"Banner rechazo la consulta de componentes: {payload}")

        components = payload.get("data", [])
        if not isinstance(components, list):
            raise RuntimeError("Banner devolvio componentes con un formato invalido")

        return components

    async def _fetch_subcomponents(
        self,
        course: dict,
        component: dict,
        client: httpx.AsyncClient | None = None,
    ) -> list:
        payload = await self._http_client.get_json(
            self._SUBCOMPONENTS_ENDPOINT,
            params={
                "selectedTerm": course.get("termCode"),
                "selectedCrn": course.get("courseReferenceNumber"),
                "selectedComponentId": component.get("componentId"),
                "sortColumn": "name",
                "sortDirection": "asc",
            },
            headers=self._ajax_headers(),
            client=client,
        )

        if not isinstance(payload, dict):
            raise RuntimeError("Banner no devolvio un payload valido para subcomponentes")
        if payload.get("success") is not True:
            raise RuntimeError(f"Banner rechazo la consulta de subcomponentes: {payload}")

        subcomponents = payload.get("data", [])
        if not isinstance(subcomponents, list):
            raise RuntimeError("Banner devolvio subcomponentes con un formato invalido")

        return subcomponents

    async def _enrich_courses_with_components(
        self,
        courses: list,
        client: httpx.AsyncClient | None = None,
    ) -> list:
        enriched_courses = []
        total = len(courses)

        for index, course in enumerate(courses, 1):
            enriched_course = dict(course)
            enriched_course["components"] = []

            if not course_has_component_details(course):
                enriched_courses.append(enriched_course)
                continue

            print(f"  → Obteniendo componentes [{index}/{total}] {build_course_label(course)}")

            try:
                components = await self._fetch_course_components(course, client)
                for component in components:
                    component["subcomponents"] = []
                    if banner_flag_to_bool(component.get("hasSubComponents")) and component.get("componentId"):
                        component["subcomponents"] = await self._fetch_subcomponents(course, component, client)

                enriched_course["components"] = components
            except Exception as error:
                print(f"  ⚠️  No se pudieron obtener componentes de {build_course_label(course)}: {error}")

            enriched_courses.append(enriched_course)

        return enriched_courses
