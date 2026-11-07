import json
from sut.buggy_app import app


def test_add_two_numbers():
    client = app.test_client()
    resp = client.get("/add?a=2&b=3")
    assert resp.status_code == 200
    data = json.loads(resp.get_data(as_text=True))
    assert data["result"] == 5, f"期望 5，实际 {data['result']}"
