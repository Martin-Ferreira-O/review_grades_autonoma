import json
import re

from uac_grades.domain.models import AcademicHistory, Course, GradeSnapshot


def _course_grade_value(course: Course) -> float | None:
    for candidate in (course.final_grade, course.grade, course.midterm_grade):
        if candidate in (None, ""):
            continue

        match = re.search(r"-?\d+(?:[\.,]\d+)?", str(candidate))
        if match is None:
            continue

        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            continue

    return None


class ConsoleSnapshotPresenter:
    def present(self, snapshot: GradeSnapshot) -> None:
        if not snapshot.courses:
            print("\n⚠️  No se encontraron cursos para el semestre seleccionado.")
            return

        print("\n" + "=" * 60)
        print("📚 JSON DE NOTAS DEL SEMESTRE")
        print("=" * 60)
        print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
        print("\n" + "=" * 60)


class ConsoleHistoryPresenter:
    def present(self, history: AcademicHistory) -> None:
        if not history.snapshots:
            print("\n⚠️  No se encontraron periodos con cursos en el historial académico.")
            return

        print("\n" + "=" * 72)
        print("🎓 RESUMEN DE HISTORIAL ACADÉMICO")
        print("=" * 72)
        print(f"Periodos encontrados: {len(history.snapshots)}")
        print(f"Cursos totales: {history.courses_count}")
        print(f"Generado en: {history.generated_at}")

        for snapshot in history.snapshots:
            grades = [grade for grade in (_course_grade_value(course) for course in snapshot.courses) if grade is not None]
            average_text = f"{sum(grades) / len(grades):.2f}" if grades else "s/d"
            print(f"- {snapshot.label}: {len(snapshot.courses)} cursos | promedio {average_text}")

        print("=" * 72)
