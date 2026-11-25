import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import store
from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["NEURAVALE_DB"] = str(Path(self.tmp.name) / "test.sqlite3")
        store.initialize()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_health_reports_state(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], ["ok", "degraded"])

    def test_conversation_roundtrip(self):
        cid = store.create_conversation("Hello")
        store.append_message(cid, "user", "Hello world")
        response = self.client.get(f"/api/conversations/{cid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["content"], "Hello world")

    def test_reject_empty_prompt(self):
        response = self.client.post("/api/chat", json={"message": " "})
        self.assertEqual(response.status_code, 422)

    def test_nonexistent_conversation(self):
        response = self.client.post("/api/chat", json={"message": "Hello", "conversation_id": "7652f491-6a5c-48c5-99c3-031ba50f3f53"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
