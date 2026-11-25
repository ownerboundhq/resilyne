from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app


def test_stream_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURAVALE_DB", str(tmp_path / "test.db"))
    async def available():
        return ["test-model"]
    async def stream(history, selected):
        assert selected == "test-model"
        yield "hello"
        yield " world"
    with patch("app.main.installed_models", available), patch("app.main.stream_model", stream), TestClient(app) as client:
        result = client.post("/api/chat", json={"message":"Hi","model":"test-model"})
        assert result.status_code == 200
        import json
        events = [json.loads(line) for line in result.text.splitlines()]
        cid = events[0]["id"]
        assert events[-1]["type"] == "done"
        assert client.get("/api/conversations/"+cid).json()["messages"][-1]["content"] == "hello world"
        assert client.delete("/api/conversations/"+cid).status_code == 200
        assert client.get("/api/conversations/"+cid).status_code == 404
