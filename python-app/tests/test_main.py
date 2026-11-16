from app.main import app


def test_health():
    client = app.test_client()
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_greet_title_cases_name():
    client = app.test_client()
    res = client.get("/api/greet?name=somchai")
    assert res.status_code == 200
    assert res.get_json() == {"greeting": "Hello, Somchai!"}
