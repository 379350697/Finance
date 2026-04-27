from fastapi.testclient import TestClient

from app.main import app


def test_create_ask_session():
    client = TestClient(app)
    response = client.post("/api/ask-stock/sessions", json={"title": "测试会话"})

    assert response.status_code in {200, 201}
    assert "id" in response.json()
