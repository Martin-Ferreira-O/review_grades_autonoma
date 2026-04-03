import json

from uac_grades.domain.models import GradeSnapshot


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
