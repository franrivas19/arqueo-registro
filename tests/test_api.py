def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_matrix_levels(seeded):
    m = seeded.get("/api/sites/EJ-001/matrix").json()
    assert m["levels"] == [[1], [2], [3, 4], [5], [6]]


def test_matrix_cycle_returns_409(seeded):
    seeded.post("/api/import/relations", files={"file": ("r.csv", b"site_code,upper,lower\nEJ-001,6,1\n")})
    assert seeded.get("/api/sites/EJ-001/matrix").status_code == 409


def test_unknown_site_404(client):
    assert client.get("/api/sites/NOPE/units").status_code == 404


def test_finds_filters_and_pagination(seeded):
    r = seeded.get("/api/finds", params={"site": "EJ-001", "category": "Cerámica"}).json()
    assert r["total"] == 2
    page = seeded.get("/api/finds", params={"limit": 2, "offset": 4}).json()
    assert page["total"] == 6 and len(page["items"]) == 2


def test_geojson_and_export(seeded):
    g = seeded.get("/api/sites.geojson").json()
    assert g["type"] == "FeatureCollection" and len(g["features"]) == 2
    assert g["features"][0]["geometry"]["coordinates"][0] < 0  # lon, lat
    assert seeded.get("/api/export").json()["license"] == "CC-BY-4.0"
