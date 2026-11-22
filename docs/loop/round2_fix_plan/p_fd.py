from pathlib import Path
F = Path(__file__).resolve().parents[3] / "app/agents/adviser.py"
s = F.read_text(encoding="utf-8")
old = '''    finding = {"headline": plan["needs"]["line"], "details": [plan["wants"]["line"], plan["wishes"]["line"]],'''
new = '''    finding = {"headline": plan["headline"].split(". ")[0].rstrip(".") + ".", "details": short_details(plan),'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''def guard_lines(ctx: RunCtx, out: AdviserOut) -> AdviserOut:'''
new = '''def _first_sentence(t: str) -> str:
    t = (t or "").strip()
    i = t.find(". ")
    return t if i < 0 else t[:i + 1]


def short_details(plan: dict) -> list[str]:
    """The adviser's finding for the team panel: two short sentences at most (the basics, then the goal)."""
    return [x for x in (_first_sentence(plan["needs"]["line"]), _first_sentence(plan["wishes"]["line"])) if x][:2]


def guard_lines(ctx: RunCtx, out: AdviserOut) -> AdviserOut:'''
assert s.count(old) == 1
s = s.replace(old, new)
F.write_text(s, encoding="utf-8")
print("ok")
