"""Page 1: every figure in "What we have so far" can be edited in place, and an edit is checked and tagged "you said"."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import pipeline
from app.agents import intake, intake_fields
from app.main import app
from app.schemas import Profile

KEYS = set(json.loads((Path(__file__).resolve().parent.parent / "web" / "src" / "panelKeys.json").read_text()))
client = TestClient(app)


def run(text, profile):
    return asyncio.run(intake.run(text, profile, use_ai=False))


def test_every_field_the_panel_can_show_is_in_the_list_the_web_tests_check():
    """web/src/panelKeys.json is what vitest runs editorFor over; a new field must be added there (and given an editor)."""
    seen = set()
    for h in client.get("/api/samples").json():
        seen |= {("college_*" if f["key"].startswith("college_") else f["key"]) for f in h["intake"]["fields"]}
        seen |= {("college_*" if f.key.startswith("college_") else f.key) for f in intake_fields.fields(Profile.model_validate(h["profile"]))}
    for p in (Profile(), Profile(age=40), Profile(age=40, has_partner=True, partner_age=38)):
        seen |= {f.key for f in intake_fields.fields(p)}
    assert seen <= KEYS, sorted(seen - KEYS)


def base(**kw):
    p = {"age": 45, "state": "CT", "retire_age": 65, "pay_per_year": 120000, "spending_per_year": 70000, "risk": "balanced",
         "savings_known": True, "savings": {"pretax": 200000, "roth": 0, "taxable": 50000, "cash": 20000}}
    p.update(kw)
    return p


def src(r, k):
    return r.profile["sources"].get(k)


def test_state_edit_is_tagged_you_said_and_announces_old_to_new():
    r = run("Updated your state: Texas. (was Connecticut)", base(state="TX", sources={"state": "assumed"}))
    assert r.profile["state"] == "TX"
    assert src(r, "state") == "you said"
    assert "Your state is now Texas, was Connecticut" in r.reply
    row = next(f for f in r.fields if f.key == "state")
    assert row.source == "you said" and row.display == "Texas"


def test_a_state_that_is_not_a_state_is_dropped():
    r = run("Updated your state: Atlantis.", base(state="ZZ"))
    assert r.profile.get("state") is None


def test_debts_added_on_the_page_count_and_are_the_persons_own():
    debts = [{"kind": "student", "balance": 30000, "rate": 0.05, "monthly_payment": 400, "assumed": []}]
    r = run("Updated your other debts: Student loan $30,000.", base(debts=debts))
    row = next(f for f in r.fields if f.key == "debts")
    assert row.source == "you said" and "Student loan" in row.display
    assert src(r, "debts") == "you said"


def test_ages_out_of_range_are_dropped_not_moved():
    r = run("Updated your age: 150.", base(age=150))
    assert r.profile.get("age") is None
    assert "did not keep age" in r.reply
    r = run("Updated your retirement age: 20.", base(retire_age=20))
    assert r.profile.get("retire_age") != 20 and "did not keep retire age" in r.reply


def test_insurance_and_goal_edits_tag_their_group():
    r = run("Updated your life insurance: term life, $500,000 cover.", base(insurance={"life_kind": "term", "life_face": 500000, "life_premium": 900}))
    assert src(r, "insurance") == "you said"
    r = run("Updated your big planned costs: Boat $40,000.", base(goals={"big_costs": [{"label": "Boat", "amount": 40000, "year": 2030}]}))
    assert src(r, "goals") == "you said"
    assert pipeline.prepare(r.profile).goals.big_costs[0].amount == 40000
