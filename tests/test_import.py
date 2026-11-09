from app.importer import import_csv
from app.matrix import CycleError, compute_levels

import pytest


def test_import_reports_row_errors_and_keeps_valid_rows(db_session):
    csv = b"code,name,latitude,longitude\nA,Uno,37.1,-3.5\nB,,1,1\nC,Tres,95,0\nD,Cuatro,\"37,2\",\"-3,6\"\n"
    r = import_csv(db_session, "sites", csv)
    assert r.inserted == 2
    assert sorted(e.row for e in r.errors) == [3, 4]


def test_semicolon_and_cp1252(db_session):
    csv = "code;name\nX;Peña\n".encode("cp1252")
    r = import_csv(db_session, "sites", csv)
    assert r.inserted == 1 and not r.errors


def test_reimport_is_idempotent(seeded):
    from tests.conftest import SAMPLE
    r = seeded.post("/api/import/sites", files={"file": ("s.csv", (SAMPLE / "sites.csv").read_bytes())})
    assert r.json()["inserted"] == 0 and r.json()["skipped"] == 2


def test_dry_run_saves_nothing(client):
    csv = b"code,name\nZ,Zeta\n"
    r = client.post("/api/import/sites?dry_run=true", files={"file": ("s.csv", csv)})
    assert r.json()["inserted"] == 1
    assert client.get("/api/sites").json() == []


def test_missing_column_is_422(client):
    r = client.post("/api/import/sites", files={"file": ("s.csv", b"code\nA\n")})
    assert r.status_code == 422


def test_levels_and_cycle():
    assert compute_levels([1, 2, 3], [(1, 2), (2, 3)]) == [[1], [2], [3]]
    with pytest.raises(CycleError):
        compute_levels([1, 2], [(1, 2), (2, 1)])
