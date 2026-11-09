from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app import config
from app.database import Base, engine, get_db
from app.importer import KINDS, CsvFormatError, import_csv
from app.matrix import CycleError, compute_levels
from app.models import Find, Relation, Site, Unit
from app.schemas import FindOut, FindPage, ImportReport, MatrixOut, SiteOut, UnitOut

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Registro arqueológico abierto",
    description="Mini-proyecto de ejemplo: registro de yacimientos, unidades estratigráficas y hallazgos "
    "con importación CSV y salida JSON/GeoJSON.",
    version="0.1.0",
)


def _site_or_404(db: Session, code: str) -> Site:
    site = db.scalar(select(Site).where(Site.code == code))
    if site is None:
        raise HTTPException(404, f"Yacimiento «{code}» no encontrado")
    return site


def _find_out(f: Find) -> FindOut:
    return FindOut(
        inventory_code=f.inventory_code,
        site_code=f.site.code,
        unit_number=f.unit.number if f.unit else None,
        category=f.category,
        material=f.material,
        description=f.description,
        found_on=f.found_on,
    )


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(select(1))
    return {"status": "ok"}


@app.get("/api/sites", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db)):
    return db.scalars(select(Site).order_by(Site.code)).all()


@app.get("/api/sites.geojson")
def sites_geojson(db: Session = Depends(get_db)) -> dict:
    sites = db.scalars(select(Site).where(Site.latitude.is_not(None), Site.longitude.is_not(None))).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.longitude, s.latitude]},
                "properties": {"code": s.code, "name": s.name, "municipality": s.municipality},
            }
            for s in sites
        ],
    }


@app.get("/api/sites/{code}/units", response_model=list[UnitOut])
def list_units(code: str, db: Session = Depends(get_db)):
    site = _site_or_404(db, code)
    return db.scalars(select(Unit).where(Unit.site_id == site.id).order_by(Unit.number)).all()


@app.get("/api/sites/{code}/matrix", response_model=MatrixOut)
def matrix(code: str, db: Session = Depends(get_db)):
    site = _site_or_404(db, code)
    units = db.scalars(select(Unit).where(Unit.site_id == site.id).order_by(Unit.number)).all()
    by_id = {u.id: u.number for u in units}
    relations = db.scalars(select(Relation).where(Relation.upper_id.in_(by_id))).all()
    edges = [(by_id[r.upper_id], by_id[r.lower_id]) for r in relations if r.lower_id in by_id]
    try:
        levels = compute_levels([u.number for u in units], edges)
    except CycleError as exc:
        raise HTTPException(409, str(exc)) from exc
    return MatrixOut(
        site_code=site.code,
        nodes=[UnitOut.model_validate(u) for u in units],
        edges=[{"upper": a, "lower": b} for a, b in sorted(edges)],
        levels=levels,
    )


@app.get("/api/finds", response_model=FindPage)
def list_finds(
    site: str | None = None,
    unit: int | None = None,
    category: str | None = None,
    material: str | None = None,
    found_from: date | None = None,
    found_to: date | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Find).options(joinedload(Find.site), joinedload(Find.unit))
    if site:
        query = query.join(Site, Find.site_id == Site.id).where(Site.code == site)
    if unit is not None:
        query = query.join(Unit, Find.unit_id == Unit.id).where(Unit.number == unit)
    if category:
        query = query.where(Find.category == category)
    if material:
        query = query.where(Find.material == material)
    if found_from:
        query = query.where(Find.found_on >= found_from)
    if found_to:
        query = query.where(Find.found_on <= found_to)

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(query.order_by(Find.inventory_code).limit(limit).offset(offset)).unique().all()
    return FindPage(total=total, limit=limit, offset=offset, items=[_find_out(f) for f in rows])


@app.get("/api/export")
def export_all(db: Session = Depends(get_db)) -> dict:
    """Volcado completo en JSON con la licencia de los datos (principio «reutilizable» de FAIR)."""
    finds = db.scalars(select(Find).options(joinedload(Find.site), joinedload(Find.unit))).unique().all()
    return {
        "license": config.DATA_LICENSE,
        "sites": [SiteOut.model_validate(s).model_dump() for s in db.scalars(select(Site)).all()],
        "finds": [_find_out(f).model_dump(mode="json") for f in finds],
    }


@app.post("/api/import/{kind}", response_model=ImportReport)
async def import_endpoint(
    kind: str,
    file: UploadFile = File(...),
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    if kind not in KINDS:
        raise HTTPException(404, f"Tipo desconocido «{kind}». Usa: {', '.join(KINDS)}")
    try:
        return import_csv(db, kind, await file.read(), dry_run=dry_run)
    except CsvFormatError as exc:
        raise HTTPException(422, str(exc)) from exc
