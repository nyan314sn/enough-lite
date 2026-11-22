"""GET /api/admin/model-compare: serves the saved comparison summary; a plain 404 when the file is missing."""
from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_returns_rows_and_recommendation():
    r = client.get("/api/admin/model-compare")
    assert r.status_code == 200
    d = r.json()
    assert d["models"] == ["Claude Haiku 5.5", "gpt-6-luna"]
    assert len(d["rows"]) >= 10
    assert {"metric", "haiku", "gpt", "n", "winner"} <= set(d["rows"][0])
    assert d["recommendation"] and d["caveats"] and d["date"] and d["cost_usd"] > 0


def test_404_with_plain_message_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "MODEL_COMPARE_PATH", tmp_path / "none.json")
    r = client.get("/api/admin/model-compare")
    assert r.status_code == 404
    assert "comparison" in r.json()["detail"].lower()
