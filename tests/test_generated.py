import pytest
from sut.buggy_app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_add_positive_integers(client):
    resp = client.get("/add?a=2&b=3")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("result") == 5


def test_add_zero_and_positive(client):
    resp = client.get("/add?a=0&b=7")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("result") == 7


def test_add_negative_numbers(client):
    resp = client.get("/add?a=-4&b=-6")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("result") == -10


def test_add_mixed_sign(client):
    resp = client.get("/add?a=-5&b=8")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("result") == 3


def test_add_large_numbers(client):
    resp = client.get("/add?a=1000000&b=2345678")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("result") == 3345678


def test_add_both_zero(client):
    resp = client.get("/add?a=0&b=0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("result") == 0


def test_add_same_numbers(client):
    resp = client.get("/add?a=42&b=42")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("result") == 84


def test_add_result_not_negative_one(client):
    resp = client.get("/add?a=2&b=3")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("result") != -1