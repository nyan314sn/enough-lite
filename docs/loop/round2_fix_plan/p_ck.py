from pathlib import Path
F = Path(__file__).resolve().parents[3] / "app/agents/adviser.py"
s = F.read_text(encoding="utf-8")
def sub(old, new):
    global s
    assert s.count(old) == 1, old[:50]
    s = s.replace(old, new)
sub('''    plan = assemble(ctx, out, source)
''', '''    plan = assemble(ctx, out, source)
    plan["consistency"] = one_figure_check(ctx, plan)
''')
sub('''def assemble(ctx: RunCtx, out: AdviserOut, source: str) -> dict:''', '''def one_figure_check(ctx: RunCtx, plan: dict) -> list[str]:
    """One figure everywhere: the plan's saving, spending now and Social Security agree with the answers panel (the
    completed profile) and with the simulation's inputs. Returns the disagreements (empty when all agree); a
    disagreement is also logged."""
    import logging
    p, bad = ctx.profile, []
    ms = ctx.results.get("money") or {}
    sv = plan.get("saving") or {}
    if (p.retire_age or 65) > (p.age or 45) and ms and sv.get("per_year") != ms.get("save_now"):
        bad.append(f"saving: plan {sv.get('per_year')} vs simulation {ms.get('save_now')}")
    if sv.get("per_year") != costs.saving_now(p)["per_year"]:
        bad.append(f"saving: plan {sv.get('per_year')} vs answers {costs.saving_now(p)['per_year']}")
    now = (plan.get("costs_by_age") or {}).get("now_per_year")
    if p.spending_now_per_year and now != round(p.spending_now_per_year):
        bad.append(f"spending now: plan {now} vs answers {round(p.spending_now_per_year)}")
    b = ss_basis(p, ctx.results["markets"])
    text = " ".join([plan.get("headline") or ""] + list(plan.get("assumptions") or []))
    if b["claim_age"] is not None and not b["same"]:
        if money(b["panel_per_year"]) not in text or money(b["plan_per_year"]) not in text:
            bad.append(f"social security: answers {b['panel_per_year']} and plan {b['plan_per_year']} are not both named")
    elif b["claim_age"] is not None and "Social Security of" in (plan.get("headline") or "") and money(b["panel_per_year"]) not in plan["headline"]:
        bad.append(f"social security: headline does not show the answers' {b['panel_per_year']}")
    if bad:
        logging.getLogger("enough.plan").warning("one-figure check: %s", "; ".join(bad))
    return bad


def assemble(ctx: RunCtx, out: AdviserOut, source: str) -> dict:''')
F.write_text(s, encoding="utf-8")
print("ok")
