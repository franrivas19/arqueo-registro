from datetime import date

from pydantic import BaseModel, ConfigDict


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    kind: str
    description: str | None = None
    period: str | None = None


class FindOut(BaseModel):
    inventory_code: str
    site_code: str
    unit_number: int | None = None
    category: str
    material: str
    description: str | None = None
    found_on: date | None = None


class FindPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[FindOut]


class MatrixOut(BaseModel):
    site_code: str
    nodes: list[UnitOut]
    edges: list[dict[str, int]]
    levels: list[list[int]]


class ImportErrorItem(BaseModel):
    row: int
    message: str


class ImportReport(BaseModel):
    kind: str
    dry_run: bool
    inserted: int
    skipped: int
    errors: list[ImportErrorItem]
