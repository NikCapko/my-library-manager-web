import os
import pytest

os.environ.setdefault("LIBRARY_DB", ":memory:")
os.environ.setdefault("LIBRARY_PATH", "/tmp")

from app import create_app
from app.db import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("LIBRARY_DB", str(db_path))
    # перезагружаем конфиг, чтобы DB_FILE подхватился
    import importlib
    import app.config
    importlib.reload(app.config)
    import app.db
    importlib.reload(app.db)
    from app import create_app as create
    app = create()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_empty(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Библиотека" in r.data


def test_update_status(client):
    r = client.get("/update_status")
    assert r.status_code == 200
    assert r.get_json()["running"] is False
