"""Importación de registros desde CSV con validación fila a fila.

Cada fila válida se guarda; cada fila errónea se informa con su número de fila (la cabecera es la fila 1),
sin interrumpir el resto. Con `dry_run=True` se valida todo y no se guarda nada.
"""
import csv
import io
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Find, Relation, Site, Unit
from app.schemas import ImportErrorItem, ImportReport

UnitKind = Literal["deposit", "cut", "structure"]


class SiteRow(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    municipality: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def decimal_comma(cls, v):
        return v.replace(",", ".") if isinstance(v, str) else v


class UnitRow(BaseModel):
    site_code: str
    number: int = Field(gt=0)
    kind: UnitKind
    description: str | None = None
    period: str | None = None


class RelationRow(BaseModel):
    site_code: str
    upper: int = Field(gt=0)
    lower: int = Field(gt=0)


class FindRow(BaseModel):
    inventory_code: str = Field(min_length=1, max_length=40)
    site_code: str
    unit_number: int | None = Field(default=None, gt=0)
    category: str = Field(min_length=1, max_length=60)
    material: str = Field(min_length=1, max_length=60)
    description: str | None = None
    found_on: date | None = None


ROW_MODELS: dict[str, type[BaseModel]] = {
    "sites": SiteRow,
    "units": UnitRow,
    "relations": RelationRow,
    "finds": FindRow,
}
KINDS = tuple(ROW_MODELS)


class CsvFormatError(ValueError):
    """El fichero no se puede interpretar (codificación, cabecera o columnas)."""


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):  # Excel en español suele guardar en cp1252
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvFormatError("No se puede leer la codificación del fichero")


def _read_rows(raw: bytes, model: type[BaseModel]) -> list[tuple[int, dict[str, str | None]]]:
    text = _decode(raw)
    first_line = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    headers = [h.strip() for h in (reader.fieldnames or [])]
    reader.fieldnames = headers
    required = {name for name, field in model.model_fields.items() if field.is_required()}
    missing = required - set(headers)
    if missing:
        raise CsvFormatError(f"Faltan columnas obligatorias: {', '.join(sorted(missing))}")

    rows = []
    for number, row in enumerate(reader, start=2):
        clean = {k: (v.strip() or None) if isinstance(v, str) else None for k, v in row.items() if k}
        if any(v is not None for v in clean.values()):  # se ignoran las filas vacías
            rows.append((number, clean))
    return rows


class _Context:
    """Búsquedas con caché para no repetir consultas dentro de una misma importación."""

    def __init__(self, db: Session):
        self.db = db
        self._sites: dict[str, Site | None] = {}
        self._units: dict[tuple[int, int], Unit | None] = {}

    def site(self, code: str) -> Site | None:
        if code not in self._sites:
            self._sites[code] = self.db.scalar(select(Site).where(Site.code == code))
        return self._sites[code]

    def unit(self, site: Site, number: int) -> Unit | None:
        key = (site.id, number)
        if key not in self._units:
            self._units[key] = self.db.scalar(
                select(Unit).where(Unit.site_id == site.id, Unit.number == number)
            )
        return self._units[key]


def _insert_site(ctx: _Context, row: SiteRow) -> bool:
    if ctx.site(row.code):
        return False
    site = Site(**row.model_dump())
    ctx.db.add(site)
    ctx.db.flush()
    ctx._sites[row.code] = site
    return True


def _insert_unit(ctx: _Context, row: UnitRow) -> bool:
    site = ctx.site(row.site_code)
    if site is None:
        raise ValueError(f"El yacimiento «{row.site_code}» no existe")
    if ctx.unit(site, row.number):
        return False
    unit = Unit(site_id=site.id, **row.model_dump(exclude={"site_code"}))
    ctx.db.add(unit)
    ctx.db.flush()
    ctx._units[(site.id, row.number)] = unit
    return True


def _insert_relation(ctx: _Context, row: RelationRow) -> bool:
    site = ctx.site(row.site_code)
    if site is None:
        raise ValueError(f"El yacimiento «{row.site_code}» no existe")
    if row.upper == row.lower:
        raise ValueError("Una UE no puede cubrirse a sí misma")
    upper, lower = ctx.unit(site, row.upper), ctx.unit(site, row.lower)
    if upper is None or lower is None:
        missing = row.upper if upper is None else row.lower
        raise ValueError(f"La UE {missing} no existe en {row.site_code}")
    exists = ctx.db.scalar(
        select(Relation.id).where(Relation.upper_id == upper.id, Relation.lower_id == lower.id)
    )
    if exists:
        return False
    ctx.db.add(Relation(upper_id=upper.id, lower_id=lower.id))
    ctx.db.flush()
    return True


def _insert_find(ctx: _Context, row: FindRow) -> bool:
    site = ctx.site(row.site_code)
    if site is None:
        raise ValueError(f"El yacimiento «{row.site_code}» no existe")
    if ctx.db.scalar(select(Find.id).where(Find.inventory_code == row.inventory_code)):
        return False
    unit_id = None
    if row.unit_number is not None:
        unit = ctx.unit(site, row.unit_number)
        if unit is None:
            raise ValueError(f"La UE {row.unit_number} no existe en {row.site_code}")
        unit_id = unit.id
    ctx.db.add(Find(site_id=site.id, unit_id=unit_id, **row.model_dump(exclude={"site_code", "unit_number"})))
    ctx.db.flush()
    return True


_INSERTERS = {
    "sites": _insert_site,
    "units": _insert_unit,
    "relations": _insert_relation,
    "finds": _insert_find,
}


def import_csv(db: Session, kind: str, raw: bytes, dry_run: bool = False) -> ImportReport:
    if kind not in ROW_MODELS:
        raise CsvFormatError(f"Tipo desconocido «{kind}». Usa: {', '.join(KINDS)}")
    model = ROW_MODELS[kind]
    ctx = _Context(db)
    inserted = skipped = 0
    errors: list[ImportErrorItem] = []

    for number, data in _read_rows(raw, model):
        try:
            row = model.model_validate(data)
            with db.begin_nested():  # un error en una fila no invalida las anteriores
                if _INSERTERS[kind](ctx, row):
                    inserted += 1
                else:
                    skipped += 1
        except ValidationError as exc:
            detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            errors.append(ImportErrorItem(row=number, message=detail))
        except ValueError as exc:
            errors.append(ImportErrorItem(row=number, message=str(exc)))

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return ImportReport(kind=kind, dry_run=dry_run, inserted=inserted, skipped=skipped, errors=errors)
