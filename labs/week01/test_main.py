from fastapi.testclient import TestClient

from main import app  # Import your FastAPI app instance

client = TestClient(app)


def test_create_task():
    response = client.post("/tasks", json={"title": "Test Task"})
    assert response.status_code == 201
    data = response.json()
    assert data["task"]["title"] == "Test Task"
    assert data["task"]["done"] is False


def test_get_task():
    response = client.post("/tasks", json={"title": "Test Task"})
    assert response.status_code == 201
    data = response.json()
    task_id = data["id"]

    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["task"]["title"] == "Test Task"
    assert data["task"]["done"] is False


def test_update_task():
    response = client.post("/tasks", json={"title": "Test Task"})
    assert response.status_code == 201
    data = response.json()
    task_id = data["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"title": "Updated Task", "done": True}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"]["title"] == "Updated Task"
    assert data["task"]["done"] is True


def test_delete_task():
    response = client.post("/tasks", json={"title": "Test Task"})
    assert response.status_code == 201
    data = response.json()
    task_id = data["id"]

    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 204
