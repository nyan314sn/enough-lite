from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/agents/adviser.py"
s = f.read_text(encoding="utf-8")
rep = [
("""    for x in out:
        ctx.extra_facts += [x["paid_of_100"], x["count_on_per_year"]]
    return out[:3]""",
"""    for x in out:
        ctx.extra_facts += [x["paid_of_100"], x["count_on_per_year"]]
    for ch, _, _ in tries:
        ctx.extra_facts += [v for v in ch.values() if isinstance(v, (int, float))]
    return out[:3]"""),
("""    t0 = time.time()
    allowed = allowed_for_adviser(ctx)""",
"""    t0 = time.time()
    m0 = ctx.results["markets"]
    if ctx.options and not ctx.shock and verdict(m0) == "falls_short" and "starting_points" not in m0:
        m0["starting_points"] = await starting_points(ctx)
    allowed = allowed_for_adviser(ctx)"""),
# needs line built in code; guard lines
("""    if out is None:
        out = template(ctx)
    plan = assemble(ctx, out, source)""",
"""    if out is None:
        out = template(ctx)
    out = guard_lines(ctx, out)
    plan = assemble(ctx, out, source)"""),
("""def _build():""",
'''LITTLE_ROOM = re.compile(r"little room|not much room|thin|tight", re.I)
FALLS_SHORT = re.compile(r"falls? short|fell short|does not work|doesn't work", re.I)


def guard_lines(ctx: RunCtx, out: AdviserOut) -> AdviserOut:
    """Lines the code owns or checks: the needs line is built from basics paid of 100; a wants line that says there is
    little room when there is room, or a line that says "falls short" when the basics are safe, is replaced."""
    m, basics = ctx.results["markets"], ctx.results["family"]["basics"]["basics_per_year"]
    t = template(ctx)
    v = verdict(m)
    wants = out.wants_line
    if (LITTLE_ROOM.search(wants) and not wants_thin(m, basics)) or (FALLS_SHORT.search(wants) and v != "falls_short"):
        wants = t.wants_line
    wishes = out.wishes_line
    if FALLS_SHORT.search(wishes) and v in ("works", "close"):
        wishes = t.wishes_line
    return AdviserOut(needs_line=needs_line(m, basics), wants_line=wants, wishes_line=wishes, actions=out.actions)


def _build():'''),
("""    elif v != "works":
        wishes += " Your goal does not work on these numbers yet, so wishes wait.\"""",
"""    elif v == "close":
        wishes += " That is close to your goal; wishes wait until it is met."
    elif v != "works":
        wishes += " Your goal is above what lasts on these numbers, so wishes wait.\""""),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
