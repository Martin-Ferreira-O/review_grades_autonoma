from __future__ import annotations

from uac_grades.domain.models import AcademicHistory, GradeSnapshot
from uac_grades.infrastructure.browser.playwright_context import PlaywrightBrowserSession
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
    _JSON_HEADERS = {"Accept": "application/json, text/javascript, */*; q=0.01"}

    def __init__(
        self,
        settings: Settings,
        browser: PlaywrightBrowserSession,
        debug_store: DebugArtifactStore,
        session_store: SessionStateStore | None = None,
        http_client: BannerHttpClient | None = None,
    ):
        self._settings = settings
        self._browser = browser
        self._debug_store = debug_store
        self._session_store = session_store or SessionStateStore(settings.storage.storage_state_path)
        self._http_client = http_client or BannerHttpClient(
            settings,
            self._session_store,
        )

    async def fetch_grade_snapshot(self) -> GradeSnapshot:
        await self._open_grades_page()
        term_raw, level_raw = await self._fetch_term_and_level()
        print("\n  → Semestre seleccionado automáticamente:")
        print(f"     Periodo: {term_raw['code']} | {term_raw['description']}")
        print(f"     Nivel:   {level_raw['code']} | {level_raw['description']}")

        courses_raw = await self._fetch_courses(term_raw["code"], level_raw["code"])
        courses_raw = await self._enrich_courses_with_components(courses_raw)

        await self._save_final_debug_artifacts()

        return build_snapshot(term_raw, level_raw, courses_raw)

    async def fetch_academic_history(self) -> AcademicHistory:
        await self._open_grades_page()
        terms = await self._fetch_terms()
        snapshots: list[GradeSnapshot] = []

        for term_index, term in enumerate(terms, 1):
            print(f"\n📚 Periodo [{term_index}/{len(terms)}] {term['code']} | {term['description']}")
            levels = await self._fetch_levels(term["code"])

            for level in levels:
                print(f"  → Nivel {level['code']} | {level['description']}")
                courses_raw = await self._fetch_courses(term["code"], level["code"])

                if not courses_raw:
                    print("    · Sin cursos para este nivel")
                    continue

                courses_raw = await self._enrich_courses_with_components(courses_raw)
                snapshots.append(build_snapshot(term, level, courses_raw))

        await self._save_final_debug_artifacts()

        return build_academic_history(snapshots)

    async def _open_grades_page(self) -> None:
        page = self._browser.page

        print("📋 Navegando a calificaciones...")
        await page.goto(self._settings.urls.grades, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        print(f"  → URL: {page.url}")

        await self._debug_store.save_page_state(page, "debug_notas.png", "debug_notas_inicial.html")
        print("  💾 debug_notas.png y debug_notas_inicial.html guardados")

    async def _save_final_debug_artifacts(self) -> None:
        page = self._browser.page
        await self._debug_store.save_page_state(page, "debug_notas_final.png", "debug_notas_final.html")
        print("  💾 debug_notas_final.png y debug_notas_final.html guardados")

    async def _fetch_term_and_level(self) -> tuple[dict, dict]:
        terms = await self._fetch_terms()
        term = pick_target_option(
            terms,
            "periodo",
            target_code=self._settings.target.term_code,
            target_description=self._settings.target.term_description,
        )

        levels = await self._fetch_levels(term["code"])
        level = pick_target_option(
            levels,
            "nivel",
            target_code=self._settings.target.level_code,
            target_description=self._settings.target.level_description,
            fallback_first=True,
        )

        return term, level

    async def _fetch_terms(self) -> list[dict]:
        await self._sync_http_session_from_browser()
        terms = await self._http_client.get_json(
            self._TERM_ENDPOINT,
            params={"page": 1, "max": 200},
            headers=self._JSON_HEADERS,
        )
        return list_valid_options(terms)

    async def _fetch_levels(self, term_code: str) -> list[dict]:
        await self._sync_http_session_from_browser()
        levels = await self._http_client.get_json(
            self._LEVEL_ENDPOINT,
            params={"term": term_code, "page": 1, "max": 50},
            headers=self._JSON_HEADERS,
        )
        return list_valid_options(levels)

    async def _sync_http_session_from_browser(self) -> None:
        context = getattr(self._browser, "context", None)
        if context is None:
            return

        await self._session_store.save(context)

    async def _fetch_courses(self, term_code: str, level_code: str) -> list:
        page = self._browser.page
        return await page.evaluate(
            """
            async ({ termCode, levelCode, pageSize }) => {
                const app = window.studentGrades;
                if (!app || !app.courseWork || !app.courseWork.courseWorkDesktopView) {
                    throw new Error("studentGrades.courseWork no está inicializado");
                }

                const collection = app.courseWork.courseWorkDesktopView.collection;
                if (!collection) {
                    throw new Error("La colección de cursos no está disponible");
                }

                app.selectedValueModel.set(
                    { termCode: termCode, levelCode: levelCode, studyPathCode: null },
                    { silent: true }
                );

                collection.page = 1;
                collection.pageMaxSize = pageSize;
                collection.reset([], { silent: true });

                await new Promise((resolve, reject) => {
                    let settled = false;

                    const cleanup = () => {
                        collection.off("fetched", onFetched);
                        collection.off("error", onError);
                    };

                    const onFetched = () => {
                        if (settled) {
                            return;
                        }
                        settled = true;
                        cleanup();
                        resolve();
                    };

                    const onError = (_collection, error) => {
                        if (settled) {
                            return;
                        }
                        settled = true;
                        cleanup();
                        reject(error || new Error("Error al obtener cursos"));
                    };

                    collection.once("fetched", onFetched);
                    collection.once("error", onError);

                    try {
                        const request = collection.fetch();
                        if (request && typeof request.then === "function") {
                            request.then(onFetched).catch(onError);
                        }
                    } catch (error) {
                        onError(null, error);
                    }
                });

                return collection.toJSON();
            }
            """,
            {
                "termCode": term_code,
                "levelCode": level_code,
                "pageSize": self._settings.browser.page_size,
            },
        )

    async def _fetch_course_components(self, course: dict) -> list:
        page = self._browser.page
        return await page.evaluate(
            """
            async ({ termCode, crn, pageSize }) => {
                const app = window.studentGrades;
                if (!app || !app.courseDetails || !app.courseDetails.componentDetailsView) {
                    throw new Error("studentGrades.courseDetails.componentDetailsView no está inicializado");
                }

                const collection = app.courseDetails.componentDetailsView.collection;
                if (!collection) {
                    throw new Error("La colección de componentes no está disponible");
                }

                app.selectedValueModel.set(
                    { selectedTermCode: termCode, crn: crn },
                    { silent: true }
                );

                collection.page = 1;
                collection.pageMaxSize = pageSize;
                collection.sortColumn = "name";
                collection.sortDirection = "asc";
                collection.reset([], { silent: true });

                await new Promise((resolve, reject) => {
                    collection.fetch({
                        success: () => resolve(),
                        error: (_collection, error) => reject(error || new Error("Error al obtener componentes")),
                    });
                });

                return collection.toJSON();
            }
            """,
            {
                "termCode": course.get("termCode"),
                "crn": course.get("courseReferenceNumber"),
                "pageSize": self._settings.browser.page_size,
            },
        )

    async def _fetch_subcomponents(self, course: dict, component: dict) -> list:
        page = self._browser.page
        return await page.evaluate(
            """
            async ({ termCode, crn, componentId }) => {
                const app = window.studentGrades;
                const programDetails = window.programDetails;
                if (!app || !app.courseDetails || !app.courseDetails.subComponentDetailsCollection) {
                    throw new Error("studentGrades.courseDetails.subComponentDetailsCollection no está inicializado");
                }
                if (!programDetails) {
                    throw new Error("programDetails no está disponible");
                }

                const componentCollection = app.courseDetails.componentDetailsView.collection;
                const collection = app.courseDetails.subComponentDetailsCollection;

                app.selectedValueModel.set(
                    { selectedTermCode: termCode, crn: crn },
                    { silent: true }
                );

                componentCollection.sortColumn = componentCollection.sortColumn || "name";
                componentCollection.sortDirection = componentCollection.sortDirection || "asc";
                programDetails.selectedComponentId = componentId;
                collection.reset([], { silent: true });

                await new Promise((resolve, reject) => {
                    collection.fetch({
                        success: () => resolve(),
                        error: (_collection, error) => reject(error || new Error("Error al obtener subcomponentes")),
                    });
                });

                return collection.toJSON();
            }
            """,
            {
                "termCode": course.get("termCode"),
                "crn": course.get("courseReferenceNumber"),
                "componentId": component.get("componentId"),
            },
        )

    async def _enrich_courses_with_components(self, courses: list) -> list:
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
                components = await self._fetch_course_components(course)
                for component in components:
                    component["subcomponents"] = []
                    if banner_flag_to_bool(component.get("hasSubComponents")) and component.get("componentId"):
                        component["subcomponents"] = await self._fetch_subcomponents(course, component)

                enriched_course["components"] = components
            except Exception as error:
                print(f"  ⚠️  No se pudieron obtener componentes de {build_course_label(course)}: {error}")

            enriched_courses.append(enriched_course)

        return enriched_courses
