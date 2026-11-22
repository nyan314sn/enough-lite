from pathlib import Path
F = Path(__file__).resolve().parents[3] / "app/agents/adviser.py"
s = F.read_text(encoding="utf-8")
a = s.index("def saving_used(ctx: RunCtx) -> dict:")
b = s.index("def assumptions(ctx: RunCtx) -> list[str]:")
s = s[:a] + '''def saving_assumed(p) -> bool:
    """The 401(k) or IRA saving is an assumption (10% of pay), not the person's own figure."""
    return p.sources.get("save_rate") != "you said" and not p.saving.given()


def saving_used(ctx: RunCtx) -> dict:
    """The yearly saving the plan uses until retirement, in its parts (costs.saving_now, the same figure the answers
    panel shows as 'Yearly saving'). assumed: the 401(k) or IRA part is assumed, not given."""
    p = ctx.profile
    return {**costs.saving_now(p), "assumed": saving_assumed(p), "field": "Yearly saving"}


''' + s[b:]
F.write_text(s, encoding="utf-8")
print("ok")
