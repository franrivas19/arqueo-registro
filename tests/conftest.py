import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


@pytest.fixture()
def db_session():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        # Receta oficial de SQLAlchemy: pysqlite no emite BEGIN y rompe SAVEPOINT/rollback sin esto.
        @event.listens_for(engine, "connect")
        def _no_autobegin(dbapi_conn, _):
            dbapi_conn.isolation_level = None

        @event.listens_for(engine, "begin")
        def _emit_begin(conn):
            conn.exec_driver_sql("BEGIN")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded(client):
    for kind in ("sites", "units", "relations", "finds"):
        r = client.post(f"/api/import/{kind}", files={"file": (f"{kind}.csv", (SAMPLE / f"{kind}.csv").read_bytes())})
        assert r.status_code == 200 and r.json()["errors"] == [], r.text
    return client
