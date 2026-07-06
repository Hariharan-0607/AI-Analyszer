import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_and_get_todo():
    create_resp = client.post("/todos/", json={"title": "Test todo", "description": "Demo"})
    assert create_resp.status_code == 201
    todo_id = create_resp.json()["id"]

    get_resp = client.get(f"/todos/{todo_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Test todo"
