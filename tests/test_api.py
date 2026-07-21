"""API 端点接口测试。"""
import pytest
from fastapi.testclient import TestClient
from api.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_scenes(client):
    resp = client.get("/scenes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_run(client):
    resp = client.post("/run", json={"intersection_id": "1", "algorithm": "fixed_time"})
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "started"


def test_status(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
