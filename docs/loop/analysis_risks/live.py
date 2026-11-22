"""Live check of the simplified "The analysis" (port 8100, ENOUGH_TEST_MODE=1): bus driver and retired couple, 1440 and 390 px.
Run: python docs/loop/analysis_simple/live.py [names...]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "round3_B"))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
import lib  # noqa: E402
from lib import auto, axe, build, overflow, say, sync_playwright  # noqa: E402

lib.URL = "http://localhost:8100/"
import live as old  # the households, from the first analysis check
lib.URL = "http://localhost:8100/"

log = lambda *a: print(*a, flush=True)


def build_plan(pg):
    """Build my plan, then the one check of the figures (Looks right, build my plan)."""
    pg.get_by_role("button", name="Build my plan", exact=True).first.click()
    ok = pg.get_by_role("button", name="Looks right, build my plan")
    try:
        ok.first.wait_for(state="visible", timeout=8000); ok.first.click()
    except Exception:
        pass
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=240000)
    pg.wait_for_timeout(500)


def run(p, name, w, whole=False):
    text, rules = old.H[name]
    b, pg = lib.new(p, w, 900 if w > 600 else 844)
    say(pg, text)
    auto(pg, rules, maxturns=16)
    build_plan(pg)
    log(f"[{name} {w}] headline:", pg.locator("[data-testid=plan-headline]").inner_text())
    if whole:
        pg.screenshot(path=os.path.join(HERE, f"{name}_{w}_whole_plan.png"), full_page=True)
    d = pg.locator("[data-testid=plan-analysis]")
    d.locator("summary").first.click(); pg.wait_for_timeout(400)
    pg.evaluate("document.querySelectorAll('.ask').forEach(e => { e.style.visibility = 'hidden'; })")   # the sticky ask bar covers the section in shots
    art = pg.locator("article.plan")
    log(f"[{name} {w}] plan page: svg charts {art.locator('svg[role=img]').count()}, tables {art.locator('table').count()}, "
        f"details-tables {art.locator('details.table-view').count()}")
    for tid in ("an-levers",):
        t = pg.locator(f"[data-testid={tid}]")
        log(f"[{name} {w}] {tid} rows:", t.locator("tbody tr").count() if t.count() else "hidden")
    log(f"[{name} {w}] risks:", [x.inner_text() for x in pg.locator('[data-testid=an-stresses] li').all()], 'amber', pg.locator('[data-at-risk=true]').count())
    log(f"[{name} {w}] sure:", pg.locator("[data-testid=an-sure]").inner_text())
    words = pg.evaluate(r"""() => { const c = document.querySelector('[data-testid=plan-analysis]').cloneNode(true);
      c.querySelectorAll('table, h4, summary, .an-legend, .sr-only, svg').forEach(e => e.remove());
      return c.textContent.trim().split(/\s+/).filter(Boolean).length; }""")
    log(f"[{name} {w}] visible words (no tables/labels):", words)
    svg = pg.locator("[data-testid=sources-chart]")
    svg.scroll_into_view_if_needed(); pg.wait_for_timeout(200)
    bb = svg.bounding_box()
    pg.mouse.move(bb["x"] + bb["width"] * 0.5, bb["y"] + bb["height"] / 2); pg.wait_for_timeout(250)
    log(f"[{name} {w}] hover:", pg.locator("[data-testid=sources-tip]").inner_text().replace("\n", " | ") if pg.locator("[data-testid=sources-tip]").count() else "NO TIP")
    pg.mouse.move(1, 1)
    d.scroll_into_view_if_needed()
    d.screenshot(path=os.path.join(HERE, f"{name}_{w}_analysis.png"))
    log(f"[{name} {w}] overflow {overflow(pg)} axe {axe(pg, name)} errors {pg.errors}")
    pg.evaluate("document.querySelectorAll('.ask').forEach(e => { e.style.visibility = ''; })")
    if w > 600:
        btn = pg.locator("[data-testid=an-levers] button")
        if btn.count():
            before = pg.locator(".log .bubble").count()
            btn.first.click(); pg.wait_for_timeout(15000)
            log(f"[{name} {w}] Try this: bubbles {before} -> {pg.locator('.log .bubble').count()}")
    b.close()


if __name__ == "__main__":
    names = sys.argv[1:] or ["bus", "retired_couple"]
    with sync_playwright() as p:
        for n in names:
            for w in (1440, 390):
                try:
                    run(p, n, w, whole=(n == names[0] and w == 1440))
                except Exception as e:
                    log(f"[{n} {w}] FAILED {type(e).__name__}: {e}")
