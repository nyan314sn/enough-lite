import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))      # tests import each other by bare name


@pytest.fixture(autouse=True)
def no_live_ai(monkeypatch):
    """Tests never call the real model: no key unless a test sets one, and no run log."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")       # otherwise a real OpenAI key would switch the tests to OpenAI
    monkeypatch.delenv("ENOUGH_PROVIDER", raising=False)
    monkeypatch.setenv("ENOUGH_RUN_LOG", "0")
    monkeypatch.setenv("ENOUGH_TEST_MODE", "0")
    from app import llm, main
    llm.METER.reset()
    main.LIMITER.hits.clear()
    yield


DOCTOR = "I'm a doctor with 3 kids and a stay-at-home wife in Connecticut with 2 dogs"


@pytest.fixture
def doctor_profile():
    from app.agents import intake
    r = asyncio.run(intake.run(DOCTOR, {}, use_ai=False))
    for t in ["45 and 43", "About $750k", "5, 8, 12", "I own it with a mortgage"]:
        r = asyncio.run(intake.run(t, r.profile, use_ai=False))
    return r.profile


@pytest.fixture
def retiree_profile():
    return {"age": 67, "has_partner": False, "state": "OH", "retire_age": 67, "pay_per_year": 0,
            "savings": {"pretax": 400000, "roth": 0, "taxable": 0, "cash": 50000}, "savings_known": True,
            "home": {"owns": True}, "social_security_per_year": 25200, "spending_per_year": 48000, "risk": "careful",
            "sources": {"age": "you said", "social_security_per_year": "you said", "spending_per_year": "you said"}}
