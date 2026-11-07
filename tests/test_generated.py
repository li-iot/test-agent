import pytest
from sut.buggy_app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_login_returns_200(client):
    resp = client.post(
        "/login",
        json={"username": "testuser", "password": "testpass"},
    )
    assert resp.status_code == 200


def test_login_returns_json(client):
    resp = client.post(
        "/login",
        json={"username": "testuser", "password": "testpass"},
    )
    data = resp.get_json()
    assert data is not None


def test_login_success_flag(client):
    resp = client.post(
        "/login",
        json={"username": "testuser", "password": "testpass"},
    )
    data = resp.get_json()
    assert data.get("success") is True


def test_login_missing_fields(client):
    resp = client.post("/login", json={})
    assert resp.status_code in (400, 401, 422)


def test_login_wrong_password(client):
    resp = client.post(
        "/login",
        json={"username": "testuser", "password": "wrongpass"},
    )
    assert resp.status_code in (401, 403)


def test_get_user_returns_200(client):
    resp = client.get("/user/1")
    assert resp.status_code == 200


def test_get_user_returns_json(client):
    resp = client.get("/user/1")
    data = resp.get_json()
    assert data is not None


def test_get_user_has_id(client):
    resp = client.get("/user/1")
    data = resp.get_json()
    assert "id" in data


def test_get_nonexistent_user(client):
    resp = client.get("/user/999999")
    assert resp.status_code == 404


def test_get_user_invalid_id(client):
    resp = client.get("/user/abc")
    assert resp.status_code in (400, 404)