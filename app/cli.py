"""Carga los CSV de ejemplo: python -m app.cli seed [directorio]"""
import sys
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.importer import KINDS, import_csv


def seed(directory: Path) -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for kind in KINDS:  # el orden importa: yacimientos, UE, relaciones, hallazgos
            report = import_csv(db, kind, (directory / f"{kind}.csv").read_bytes())
            print(f"{kind}: {report.inserted} nuevos, {report.skipped} ya existían, {len(report.errors)} errores")
            for e in report.errors:
                print(f"  fila {e.row}: {e.message}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "seed":
        sys.exit("Uso: python -m app.cli seed [directorio]")
    seed(Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/sample"))
