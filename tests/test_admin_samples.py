"""The admin sample households: /api/samples and every profile passes pipeline.prepare."""
from collections import Counter

from fastapi.testclient import TestClient

from app import pipeline
from app.main import app

client = TestClient(app)
TIERS = {"comfortable", "average", "struggling"}


def samples():
    r = client.get("/api/samples")
    assert r.status_code == 200
    return r.json()


def test_at_least_fifteen_five_per_tier():
    s = samples()
    assert len(s) >= 15
    counts = Counter(h["tier"] for h in s)
    assert set(counts) == TIERS
    assert all(counts[t] == 5 for t in TIERS)


def test_shape_and_unique_ids():
    s = samples()
    assert len({h["id"] for h in s}) == len(s)
    for h in s:
        assert h["name"] and h["description"] and isinstance(h["profile"], dict)


def test_every_profile_passes_prepare():
    for h in samples():
        p = pipeline.prepare(h["profile"])
        assert p.age == h["profile"]["age"], h["id"]


def test_struggling_covers_the_hard_cases():
    s = [h["profile"] for h in samples() if h["tier"] == "struggling"]
    assert any(p.get("home", {}).get("owns") is False and 50 <= p["age"] < 60 for p in s)       # renter in the 50s
    assert any(p.get("children") and not p.get("has_partner") for p in s)                      # single parent
    assert any(p["age"] >= 65 and not p.get("pay_per_year") for p in s)                        # retired
    assert any(p.get("debts") for p in s)                                                      # debt


def test_each_has_a_complete_page_one_state():
    for h in samples():
        i = h["intake"]
        assert i["missing"] == [] and i["fields"] and i["question"] is None, h["id"]
        pipeline.prepare(i["profile"])
