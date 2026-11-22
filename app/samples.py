"""Sample households for the admin screen (?admin): the file, and each profile as page 1 would hold it after a full chat."""
from __future__ import annotations

import json
from typing import Any

from . import config
from .agents import intake
from .schemas import Profile

GIVEN = ("age", "partner_age", "state", "pay_per_year", "partner_pay_per_year", "retire_age", "spending_now_per_year",
         "spending_per_year", "social_security_per_year", "risk", "health", "savings", "home", "children", "pets", "debts")


def as_answered(profile: dict) -> dict[str, Any]:
    """The intake state for a stored profile: every figure marked as the person's own, nothing left to ask. No model call."""
    p = Profile.model_validate(profile)
    for k in GIVEN:
        v = getattr(p, k)
        if v not in (None, [], {}) or k in ("children", "debts"):
            p.sources[k] = "you said"
    p.savings_known = True
    if p.has_partner or p.partner_age:
        p.sources["partner_pay_per_year"] = "you said"
    if p.retire_age is not None and p.age is not None and p.retire_age <= p.age:
        p.notes["retired"] = "yes"
    if p.home.owns:
        p.notes["mortgage"] = "yes" if p.home.mortgage_balance > 0 else "no"
        p.notes["mortgage_balance_said"] = p.notes["mortgage_payment_said"] = "yes"
    if "debts" not in p.offered:
        p.offered.append("debts")
    r = intake._respond(p, "This household was loaded from the admin list. Check any figure, change it, then build the plan.", None)
    out = r.model_dump()
    out["question"] = None
    return out


def load() -> list[dict[str, Any]]:
    items = json.loads((config.DATA_DIR / "sample_households.json").read_text(encoding="utf-8"))
    return [{**h, "intake": as_answered(h["profile"])} for h in items]
