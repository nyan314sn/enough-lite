"""The MCP server, called through an in-memory MCP client. No live model; numbers must equal the app's own."""
import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pytest.importorskip("fastmcp")

from fastmcp import Client  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402

import mcp_server  # noqa: E402
from app import pipeline  # noqa: E402
from app.tools import estimates, family_costs, lifetable, sources, tax  # noqa: E402

SAMPLES = {s["id"]: s for s in json.load(open(ROOT / "app" / "data" / "sample_households.json", encoding="utf-8"))}


def call(name, args):
    async def go():
        async with Client(mcp_server.mcp) as c:
            r = await c.call_tool(name, args)
            return r.structured_content
    return asyncio.run(go())


def household_from(p: dict) -> dict:
    """A sample profile written the way the tool takes it."""
    s = p.get("savings", {})
    sv = p.get("saving", {})
    h = {"age": p["age"], "partner_age": p.get("partner_age"), "state": p.get("state"), "retire_age": p.get("retire_age"),
         "pay_per_year": p.get("pay_per_year"), "partner_pay_per_year": p.get("partner_pay_per_year"),
         "savings_pretax": s.get("pretax"), "savings_roth": s.get("roth"), "savings_taxable": s.get("taxable"), "savings_cash": s.get("cash"),
         "spending_per_year": p.get("spending_per_year"), "social_security_per_year": p.get("social_security_per_year"),
         "risk": p.get("risk"), "health": p.get("health"), "sex": p.get("sex"), "partner_sex": p.get("partner_sex"),
         "partner_health": p.get("partner_health"), "partner_retire_age": p.get("partner_retire_age"),
         "spending_now_per_year": p.get("spending_now_per_year"),
         "contribution_per_year": sv.get("contrib_you"), "partner_contribution_per_year": sv.get("contrib_partner"),
         "employer_match_rate": sv.get("match_rate"), "employer_match_cap": sv.get("match_cap"),
         "debts": [{k: d[k] for k in ("kind", "balance", "rate", "monthly_payment") if k in d} for d in p.get("debts", [])],
         "children": [{"age": c["age"], "college_type": c.get("college_type")} for c in p.get("children", [])],
         "pets": p.get("pets", [])}
    hm = p.get("home")
    if hm:
        h["home"] = {"owns": hm.get("owns"), "value": hm.get("value", 0), "mortgage_balance": hm.get("mortgage_balance", 0),
                     "mortgage_payment_per_month": hm.get("mortgage_payment", 0), "rent_per_month": hm.get("rent", 0),
                     "mortgage_rate": hm.get("mortgage_rate")}
    return {k: v for k, v in h.items() if v is not None}


def test_lists_every_tool():
    async def go():
        async with Client(mcp_server.mcp) as c:
            return {t.name for t in await c.list_tools()}
    assert asyncio.run(go()) == {"plan_check", "social_security_estimate", "tax_estimate", "life_expectancy", "family_costs", "search_rules"}


@pytest.mark.parametrize("sid", ["doctor", "s039", "young"])
def test_plan_check_matches_the_app(sid):
    prof = SAMPLES[sid]["profile"]
    # the app's own tools-only path, on the same household written as a full profile
    prepared = pipeline.prepare(copy.deepcopy(prof))
    plan, _ = asyncio.run(pipeline.tools_only_plan(prepared))
    out = call("plan_check", {"household": household_from(prof)})
    assert out["status"] == "ok"
    assert out["count_on_per_year"] == plan["count_on_per_year"]
    assert out["basics_paid_of_100"] == plan["needs"]["paid_of_100"]
    assert out["basics_per_year"] == plan["needs"]["basics_per_year"]
    assert out["verdict"] == plan["verdict"]
    assert out["planning_age"] == plan["horizon_age"]
    assert out["social_security_per_year"] == plan["social_security_per_year"]
    assert out["short_of_goal_per_year"] == max(0, round(plan["spending_goal"] - plan["count_on_per_year"]))
    assert out["assumptions"] and "not financial" in out["not_financial_advice"].lower()
    assert "seed 409" in out["engine"]


def test_plan_check_minimal_household_lists_what_it_assumed():
    out = call("plan_check", {"household": {"age": 58, "state": "Ohio", "savings_total": 400000, "pay_per_year": 70000,
                                            "retire_age": 65, "spending_per_year": 55000}})
    assert out["status"] == "ok" and out["retire_age"] == 65
    fields = {a["field"] for a in out["assumed_inputs"]}
    assert {"savings", "risk", "health"} <= fields
    assert "pay_per_year" not in fields and "state" not in fields
    assert out["count_on_per_year"] > 0 and out["spending_goal_per_year"] == 55000
    assert out["verdict"] in ("works", "close", "below_goal", "falls_short")


def test_plan_check_same_answer_twice():
    h = {"household": {"age": 50, "state": "TX", "savings_total": 300000, "pay_per_year": 80000}}
    assert call("plan_check", h)["count_on_per_year"] == call("plan_check", h)["count_on_per_year"]


def test_plan_check_retire_past_70_note():
    out = call("plan_check", {"household": {"age": 62, "state": "OH", "savings_total": 200000, "pay_per_year": 60000, "retire_age": 72}})
    assert any("past 70" in n for n in out["notes"])


def test_social_security_matches_tool():
    out = call("social_security_estimate", {"pay_per_year": 70000, "claim_age": 70, "retire_age": 65, "partner_pay_per_year": 0})
    exp = estimates.social_security(70000, 70, estimates.career_years(65))
    assert out["per_year"] == exp["per_year"] and out["per_year_at_full_age"] == exp["at_full_age_per_year"]
    assert out["by_claim_age"]["62"] < out["by_claim_age"]["67"] < out["by_claim_age"]["70"]
    assert out["spousal_per_year_at_full_age"] == estimates.spouse_benefit(exp["at_full_age_per_year"])


def test_tax_matches_tool():
    out = call("tax_estimate", {"state": "oh", "pay_per_year": 90000, "married": True, "children_under_17": 2,
                                "retired_spending_per_year": 60000, "social_security_per_year": 30000, "pretax_savings": 500000})
    assert out["working"] == tax.working_years(90000, 0, "OH", True, 2, 0)
    exp = tax.retirement_years(60000, 30000, {"pretax": 500000, "roth": 0, "taxable": 0, "cash": 0}, "OH", True, 2)
    assert out["retired"] == exp
    assert "401k_limit" in out["limits_2027"]


def test_life_expectancy_matches_tool():
    out = call("life_expectancy", {"age": 58, "sex": "female", "health": "fair", "partner_age": 60, "partner_sex": "male"})
    h = lifetable.horizon(58, "female", 60, "male", mult=lifetable.health_mult("fair"))
    assert out["planning_age"] == h["horizon_age"] and out["life_expectancy_partner"] == h["life_expectancy_partner"]
    assert 0 < out["chance_alive_at_planning_age"] <= 0.3


def test_family_costs_matches_tool():
    out = call("family_costs", {"age": 45, "children": [{"age": 13, "college_type": "public"}, {"age": 6, "college_type": "private", "college_share": 0.5}],
                                "pets": [{"kind": "dog", "count": 2}]})
    fp = family_costs.family_path(45, [{"age": 13, "college": True, "college_type": "public", "college_share": 1.0},
                                       {"age": 6, "college": True, "college_type": "private", "college_share": 0.5}],
                                  [{"kind": "dog", "count": 2}], None)
    assert [r["total"] for r in out["by_year"]] == fp["per_year"]
    assert out["by_year"][0]["your_age"] == 45 and out["college_total"] == fp["college_total"] and out["moments"]


def test_search_rules_cites_sources():
    out = call("search_rules", {"question": "When can I sign up for Medicare?"})
    assert out["status"] == "ok" and out["passages"]
    exp = sources.search("When can I sign up for Medicare?", k=3)
    assert [p["id"] for p in out["passages"]] == [e["id"] for e in exp]
    assert all(p["title"] and p["url"].startswith("http") for p in out["passages"])


def test_search_rules_no_source():
    out = call("search_rules", {"question": "zxqv blorptastic wumpus"})
    assert out["passages"] == [] and out["source"] == "no source"


@pytest.mark.parametrize("q", ["How can I give away my savings to qualify for Medicaid?",
                               "Should I buy bitcoin with my 401k?",
                               "I have chest pain and can't breathe"])
def test_refusals_in_search_rules(q):
    out = call("search_rules", {"question": q})
    assert out["status"] in ("refused", "emergency") and out["passages"] == [] and out["message"]


def test_refusal_messages_match_the_app():
    assert call("search_rules", {"question": "how do I hide assets so I qualify for Medicaid"})["message"] == mcp_server.safety.MEDICAID_REPLY
    assert call("search_rules", {"question": "Should I buy bitcoin with my 401k?"})["message"] == mcp_server.safety.STOCK_REPLY
    em = call("search_rules", {"question": "I am having a heart attack"})
    assert em["status"] == "emergency" and "911" in em["message"] and "988" in em["message"]


def test_plan_check_refuses_in_note():
    out = call("plan_check", {"household": {"age": 70, "savings_total": 90000, "note": "Hide my savings from SSI so I keep getting benefits"}})
    assert out["status"] == "refused" and out["count_on_per_year"] is None
    out = call("plan_check", {"household": {"age": 60, "note": "which single stock should I buy"}})
    assert out["status"] == "refused"
    out = call("plan_check", {"household": {"age": 60, "note": "I want to end my life"}})
    assert out["status"] == "emergency" and "988" in out["message"]


@pytest.mark.parametrize("tool,args", [
    ("plan_check", {"household": {"age": 17}}),
    ("plan_check", {"household": {"age": 101}}),
    ("plan_check", {"household": {"age": 50, "pay_per_year": -5}}),
    ("plan_check", {"household": {"age": 50, "pay_per_year": 1e12}}),
    ("plan_check", {"household": {"age": 50, "retire_age": 20}}),
    ("plan_check", {"household": {"age": 50, "state": "Narnia"}}),
    ("plan_check", {"household": {"age": 50, "children": [{"age": 99}]}}),
    ("social_security_estimate", {"pay_per_year": 50000, "claim_age": 61}),
    ("social_security_estimate", {"pay_per_year": 50000, "claim_age": 71}),
    ("tax_estimate", {"state": "ZZ", "pay_per_year": 50000}),
    ("tax_estimate", {"state": "OH", "pay_per_year": -1}),
    ("life_expectancy", {"age": 5}),
    ("family_costs", {"age": 40, "children": [{"age": -1}]}),
    ("search_rules", {"question": ""}),
])
def test_validation_rejects_bad_input(tool, args):
    with pytest.raises(ToolError):
        call(tool, args)


def test_refuses_forbidden_ports():
    for port in (8000, 8010, 8020):
        with pytest.raises(SystemExit):
            mcp_server.main(["--http", str(port)])
